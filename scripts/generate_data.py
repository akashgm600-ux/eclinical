"""CLI Script to generate synthetic clinical trial datasets."""

import argparse
import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from data.synthetic_generator import generate_all_datasets


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic clinical trial datasets.")
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/sample",
        help="Directory to save generated CSV files (default: data/sample)",
    )
    parser.add_argument(
        "--clean-only",
        action="store_true",
        help="If set, do not introduce deliberate data quality anomalies.",
    )
    args = parser.parse_args()

    out_path = Path(args.output_dir)
    include_anomalies = not args.clean_only
    print(f"[*] Generating synthetic clinical trial data into: {out_path.resolve()}")
    print(f"[*] Deliberate data quality anomalies enabled: {include_anomalies}")

    datasets = generate_all_datasets(str(out_path), include_anomalies=include_anomalies)

    for name, df in datasets.items():
        print(f"    - {name}.csv: {len(df)} rows, {len(df.columns)} columns")

    print("[+] Successfully generated all synthetic datasets!")


if __name__ == "__main__":
    main()
