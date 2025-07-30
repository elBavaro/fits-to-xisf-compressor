#!/usr/bin/env python3
import configparser
import os
import sys
import shutil
import time
from datetime import datetime, timedelta
from functools import partial
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np
from astropy.io import fits
from xisf import XISF

def convert_fits_to_xisf(fits_path, xisf_path, codec, shuffle, level, creator_app):
    """
    Read FITS data+header, reshape 2D→3D, cast headers to str, and write XISF.
    """
    data = fits.getdata(fits_path)
    header = fits.getheader(fits_path)

    # If grayscale (2D), add channel axis
    if data.ndim == 2:
        data = data[:, :, np.newaxis]

    # Build string-only FITSKeywords
    fits_keywords = {}
    for key in header:
        val = str(header[key])
        comment = header.comments[key] if key in header.comments else ""
        fits_keywords[key] = [{"value": val, "comment": comment}]
    image_metadata = {"FITSKeywords": fits_keywords}

    try:
        return XISF.write(
            xisf_path, data,
            creator_app=creator_app,
            image_metadata=image_metadata,
            xisf_metadata={},
            codec=codec, shuffle=shuffle, level=level
        )
    except Exception as e:
        msg = str(e)
        if "tuple index out of range" in msg:
            # fallback without metadata
            return XISF.write(
                xisf_path, data,
                creator_app=creator_app,
                codec=codec, shuffle=shuffle, level=level
            )
        else:
            raise

def str2bool(s):
    return str(s).lower() in ('1','yes','true','on')

def main():
    # Read config.ini next to this script
    base_dir = os.path.dirname(__file__)
    cfg = configparser.ConfigParser()
    cfg.read(os.path.join(base_dir, "config.ini"))
    sec = cfg["settings"]

    input_dir  = sec.get("input_dir")
    output_dir = sec.get("output_dir")
    codec      = sec.get("codec", "zlib")
    shuffle    = str2bool(sec.get("shuffle", "yes"))
    level      = sec.getint("level", 6)
    creator    = sec.get("creator_app", os.path.basename(__file__))
    workers    = sec.getint("workers", 4)
    skip_existing = str2bool(sec.get("skip_existing", "yes"))
    delete_older_than_days = sec.getint("delete_older_than_days", -1)

    if not os.path.isdir(input_dir):
        print(f"Error: input_dir '{input_dir}' is not a folder")
        sys.exit(1)
    os.makedirs(output_dir, exist_ok=True)

    # Prepare lists of tasks
    fits_tasks = []

    for root, dirs, files in os.walk(input_dir):
        rel = os.path.relpath(root, input_dir)
        dest_root = os.path.join(output_dir, rel)
        os.makedirs(dest_root, exist_ok=True)

        for fn in files:
            src = os.path.join(root, fn)
            if fn.lower().endswith(".fits"):
                dst = os.path.splitext(os.path.join(dest_root, fn))[0] + ".xisf"
                # Skip conversion if XISF file already exists
                if os.path.exists(dst) and skip_existing:
                    print(f"[⏭] Skipping {os.path.relpath(src,input_dir)} - XISF file already exists")
                    continue
                fits_tasks.append((src, dst))
            else:
                # copy everything else
                shutil.copy2(src, os.path.join(dest_root, fn))

    # Parallel conversion of FITS→XISF
    print(f"Converting {len(fits_tasks)} FITS files with {workers} workers…")
    worker_fn = partial(convert_fits_to_xisf,
                        codec=codec, shuffle=shuffle, level=level, creator_app=creator)

    with ProcessPoolExecutor(max_workers=workers) as exe:
        futures = {exe.submit(worker_fn, src, dst): (src, dst) for src,dst in fits_tasks}
        for fut in as_completed(futures):
            src, dst = futures[fut]
            try:
                nbytes, used_codec = fut.result()
                print(f"[✓] {os.path.relpath(src,input_dir)} → "
                      f"{os.path.relpath(dst,output_dir)} ({nbytes} bytes, codec={used_codec})")
                
                # Delete original FITS file if configured to do so
                if delete_older_than_days != -1:  # Only process if deletion is not disabled
                    should_delete = False
                    
                    if delete_older_than_days == 0:
                        # Delete immediately
                        should_delete = True
                    else:
                        # Check file age
                        try:
                            file_mtime = os.path.getmtime(src)
                            file_age_days = (time.time() - file_mtime) / (24 * 3600)
                            should_delete = file_age_days >= delete_older_than_days
                        except OSError as e:
                            print(f"[⚠️] Could not check age of {os.path.relpath(src,input_dir)}: {e}")
                            should_delete = False
                    
                    if should_delete:
                        try:
                            os.remove(src)
                            print(f"[🗑️] Deleted original: {os.path.relpath(src,input_dir)}")
                        except OSError as e:
                            print(f"[⚠️] Failed to delete {os.path.relpath(src,input_dir)}: {e}")
                    else:
                        if delete_older_than_days > 0:
                            print(f"[⏰] Skipped deletion (file too recent): {os.path.relpath(src,input_dir)}")
                        
            except Exception as e:
                print(f"[✗] {os.path.relpath(src,input_dir)} failed: {e}")

if __name__ == "__main__":
    main()
