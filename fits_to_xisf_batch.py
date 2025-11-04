#!/usr/bin/env python3
import configparser
import os
import sys
import shutil
from functools import partial
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timedelta

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

def delete_old_fits_files(input_dir, days):
    """
    Delete FITS files in input_dir (recursively) that are older than 'days' days.
    """
    if days <= 0:
        return  # No deletion if days <= 0
    
    cutoff = datetime.now() - timedelta(days=days)
    deleted_count = 0
    
    for root, dirs, files in os.walk(input_dir):
        for fn in files:
            if fn.lower().endswith(".fits"):
                filepath = os.path.join(root, fn)
                try:
                    # Get file modification time
                    mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
                    if mtime < cutoff:
                        os.remove(filepath)
                        print(f"[🗑] Deleted old FITS file: {os.path.relpath(filepath, input_dir)} (modified: {mtime.strftime('%Y-%m-%d %H:%M:%S')})")
                        deleted_count += 1
                except Exception as e:
                    print(f"[✗] Failed to delete {filepath}: {e}")
    
    if deleted_count > 0:
        print(f"Deleted {deleted_count} FITS file(s) older than {days} days from input directory")

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
            except Exception as e:
                print(f"[✗] {os.path.relpath(src,input_dir)} failed: {e}")
    
    # Delete old FITS files if configured (after conversion is complete)
    if delete_older_than_days > 0:
        print(f"\nChecking for FITS files older than {delete_older_than_days} days in input directory...")
        delete_old_fits_files(input_dir, delete_older_than_days)

if __name__ == "__main__":
    main()
