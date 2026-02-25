#!/usr/bin/env python3
"""
Batch download crystal structures from OpenMaterialsDB.

Downloads all available POSCAR structures for a given formula and exports
a CSV summary of material metadata.

Usage:
    python batch_download.py --formula "TiO2" --output-dir /tmp/tio2
    python batch_download.py --formula "+Li +Fe +O" --output-dir /tmp/lifeox --csv metadata.csv
"""

import argparse
import csv
import time
from pathlib import Path

from fetch_materials import (
    search_materials,
    get_compound_details,
    download_poscar,
)


def batch_download(formula, output_dir="./structures", delay=1.0):
    """
    Search for a formula and download all available POSCAR files.

    Args:
        formula: Search query string.
        output_dir: Directory to save POSCAR files.
        delay: Delay in seconds between requests to avoid rate limiting.

    Returns:
        List of metadata dicts with keys: formula, compound_cid, vasp_sid, file_path.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Searching for: {formula}")
    results = search_materials(formula)
    if not results:
        print("No results found.")
        return []

    print(f"Found {len(results)} compound(s)")
    metadata = []

    for r in results:
        time.sleep(delay)
        details = get_compound_details(r["compound_cid"], r["formula"])

        for sid in details["vasp_sids"]:
            time.sleep(delay)
            try:
                file_path = download_poscar(sid, output_dir=str(output_dir))
                metadata.append({
                    "formula": r["formula"],
                    "compound_cid": r["compound_cid"],
                    "name": r.get("name", ""),
                    "spacegroup": r.get("spacegroup", ""),
                    "vasp_sid": sid,
                    "file_path": str(file_path),
                })
            except Exception as e:
                print(f"  Failed to download vasp_sid={sid}: {e}")

    print(f"\nDownloaded {len(metadata)} structure(s) to {output_dir}")
    return metadata


def export_csv(metadata, csv_path):
    """Export metadata list to CSV."""
    if not metadata:
        print("No metadata to export.")
        return
    fieldnames = ["formula", "compound_cid", "name", "spacegroup", "vasp_sid", "file_path"]
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(metadata)
    print(f"Metadata exported to {csv_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Batch download structures from OpenMaterialsDB"
    )
    parser.add_argument(
        "--formula",
        required=True,
        help="Search formula or species query",
    )
    parser.add_argument(
        "--output-dir",
        default="./structures",
        help="Output directory for POSCAR files",
    )
    parser.add_argument(
        "--csv",
        default=None,
        help="Path to export metadata CSV",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Delay between requests in seconds (default: 1.0)",
    )
    args = parser.parse_args()

    metadata = batch_download(
        args.formula,
        output_dir=args.output_dir,
        delay=args.delay,
    )

    if args.csv:
        export_csv(metadata, args.csv)
