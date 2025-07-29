# fits-to-xisf-compressor
A simple Python script to recursively scan your astrophotography library, convert all FITS files to lossless XISF (with optional Zstd, Zlib, LZ4/LZ4HC compression and byte‑shuffling), and mirror your folder tree into a new output directory.

## Features

* **Mirror‑tree layout**: input and output directories share the same subfolder structure. Non‑FITS files are simply copied over.
* **Lossless codecs**: choose between zlib (DEFLATE), LZ4, LZ4HC (high‑compression LZ4), or Zstandard (zstd) with byte‑shuffling.
* **Parallel conversion**: leverage multiple CPU cores via a configurable `workers` setting.

## Compression Algorithms

| Codec     | Speed (compress/decompress) | Typical Ratio           | Use Case                                |
| --------- | --------------------------- | ----------------------- | --------------------------------------- |
| **LZ4**   | > 500 MB/s / GB/s           | \~ 2:1                  | Extreme throughput, minimal CPU load    |
| **LZ4HC** | \~ 50 MB/s / 500 MB/s       | \~ 1.8:1                | Better ratio than LZ4, still fast reads |
| **Zlib**  | \~ 36 MB/s / 270 MB/s       | 2:1–5:1 (≈ 40%)         | Broad support, balanced ratio vs speed  |
| **Zstd**  | 200–400 MB/s / 550 MB/s     | 3.7:1–6:1 (levels 1–22) | Best balance at mid‑levels (3–6)        |

## Choosing Your Settings

* **codec**: `zstd` recommended for most use‑cases. Use `zlib` if maximum compatibility is needed.
* **level**: trade CPU for size—**5–6** gives \~ 4:1 at ≳ 100 MB/s; **3** (default) is faster (≳ 200 MB/s) with \~ 3.9:1.
* **shuffle**: `yes` for byte‑shuffling improves compression on multi‑byte scientific data.
* **workers**: set to your number of CPU cores (logical or physical) for optimal throughput.

## Installation

### Prerequisites

Make sure you have Python 3+ and pipenv installed:

> **Note**: For detailed installation instructions and troubleshooting for pipenv, see the [official Pipenv installation guide](https://pipenv.pypa.io/en/latest/installation.html).

### Setup

1. Clone the repo:

   ```bash
   git clone https://github.com/yourname/fits-to-xisf.git
   cd fits-to-xisf
   ```

2. Copy and edit the config template:

   ```bash
   cp config.ini.example config.ini
   # then adjust paths and settings in config.ini
   ```

3. Install dependencies with pipenv:

   ```bash
   pipenv install
   ```

## Usage

Run the script without arguments (reads `config.ini`):

```bash
# Using pipenv
pipenv run python fits_to_xisf_batch.py

# Or activate the virtual environment first
pipenv shell
python fits_to_xisf_batch.py
```

Converted `.xisf` files and other assets will appear in your `output_dir` with the same folder structure as `input_dir`.

## License

MIT License — see [LICENSE](LICENSE) for details.
