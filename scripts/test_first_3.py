#!/usr/bin/env python3
"""
Test script to process the first 3 datasets from *_full.json files.

This script extracts the first 3 datasets from each full JSON file,
saves them to temporary files, and processes them with the batch processor.
"""

import json
import sys
from pathlib import Path
import tempfile
import subprocess

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def extract_first_n(json_file: Path, n: int = 3) -> list:
    """
    Extract first N datasets from a JSON file.
    
    Args:
        json_file: Path to JSON file
        n: Number of datasets to extract
        
    Returns:
        List of first N datasets
    """
    with open(json_file, 'r') as f:
        data = json.load(f)
    
    if isinstance(data, list):
        return data[:n]
    else:
        return [data]  # Single dataset

def main():
    examples_dir = Path(__file__).parent.parent / "examples"
    
    # Find all *_full.json files
    full_files = list(examples_dir.glob("*_full.json"))
    
    if not full_files:
        print("No *_full.json files found in examples/")
        return 1
    
    print(f"Found {len(full_files)} full JSON file(s)")
    print("="*80)
    
    for json_file in full_files:
        print(f"\nProcessing: {json_file.name}")
        print(f"Extracting first 3 datasets...")
        
        # Extract first 3 datasets
        datasets = extract_first_n(json_file, n=3)
        
        print(f"  → Extracted {len(datasets)} dataset(s)")
        
        # Create temporary file in examples directory
        tmp_filename = f"test_first3_{json_file.stem}.json"
        tmp_path = examples_dir / tmp_filename
        
        with open(tmp_path, 'w') as f:
            json.dump(datasets, f, indent=2)
        
        try:
            # Run batch processor on temporary file
            cmd = [
                "uv", "run", "python",
                str(Path(__file__).parent / "batch_processor.py"),
                str(examples_dir),
                "--file", tmp_filename,
                "--submit"
            ]
            
            print(f"  Running batch processor...")
            result = subprocess.run(cmd, cwd=examples_dir.parent)
            
            if result.returncode != 0:
                print(f"  ✗ Failed to process {json_file.name}")
            else:
                print(f"  ✓ Successfully processed {json_file.name}")
                
        finally:
            # Clean up temporary file
            if tmp_path.exists():
                tmp_path.unlink()
    
    print("\n" + "="*80)
    print("Test complete!")
    return 0

if __name__ == '__main__':
    sys.exit(main())
