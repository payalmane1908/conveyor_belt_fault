"""
Download script for Mendeley Research Dataset:
'Experimental vibration data collected for a belt drive system under different operating conditions'
DOI: 10.17632/jf8v2ndydr.1
Authors: Ramy Khalifa, Soumaya Yacout, Samuel Bassetto, Yasser Shaban
License: CC BY 4.0
"""

import os
import sys
import zipfile
import urllib.request
from pathlib import Path

# Paths
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR.parent
RAW_RESEARCH_DIR = DATA_DIR / "raw" / "research" / "mendeley_belt_drive"
ARCHIVE_PATH = RAW_RESEARCH_DIR / "mendeley_belt_drive_dataset.zip"

DOWNLOAD_URL = "https://data.mendeley.com/public-api/zip/jf8v2ndydr/download/1"

def download_and_extract():
    RAW_RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
    
    print(f"Downloading Mendeley belt drive dataset from:\n  {DOWNLOAD_URL}")
    print(f"Target file: {ARCHIVE_PATH}")
    
    req = urllib.request.Request(DOWNLOAD_URL, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    
    # Download with progress report
    with urllib.request.urlopen(req, timeout=120) as response, open(ARCHIVE_PATH, "wb") as out_file:
        total_size = int(response.headers.get("Content-Length", 0))
        downloaded = 0
        chunk_size = 1024 * 1024  # 1 MB chunks
        
        while True:
            chunk = response.read(chunk_size)
            if not chunk:
                break
            out_file.write(chunk)
            downloaded += len(chunk)
            if total_size > 0:
                percent = (downloaded / total_size) * 100
                print(f"\rProgress: {downloaded / (1024*1024):.1f} MB / {total_size / (1024*1024):.1f} MB ({percent:.1f}%)", end="", flush=True)
            else:
                print(f"\rDownloaded: {downloaded / (1024*1024):.1f} MB", end="", flush=True)
                
    print("\nDownload complete! Verifying and extracting zip archive...")
    
    with zipfile.ZipFile(ARCHIVE_PATH, "r") as zip_ref:
        namelist = zip_ref.namelist()
        print(f"Archive contains {len(namelist)} items.")
        zip_ref.extractall(RAW_RESEARCH_DIR)
        
    print(f"Successfully extracted dataset to: {RAW_RESEARCH_DIR}")
    
    # List top level extracted items
    items = list(RAW_RESEARCH_DIR.iterdir())
    print(f"Extracted {len(items)} top-level items in {RAW_RESEARCH_DIR}:")
    for item in sorted(items):
        if item.is_dir():
            child_count = len(list(item.iterdir()))
            print(f"  [DIR]  {item.name} ({child_count} files)")
        else:
            print(f"  [FILE] {item.name} ({item.stat().st_size} bytes)")

if __name__ == "__main__":
    download_and_extract()
