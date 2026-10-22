"""CLI Entrypoint to execute the Clinical Trial Data Quality & ETL Pipeline."""

import argparse
import json
import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.pipeline.runner import run_pipeline


def main():
    parser = argparse.ArgumentParser(description="Run the Clinical Trial Data Quality & ETL Pipeline.")
    parser.add_argument(
        "--input-dir",
        type=str,
        default=None,
        help="Input folder containing CSV files (default: from .env or data/sample)",
    )
    parser.add_argument(
        "--db-url",
        type=str,
        default=None,
        help="Target database connection URL (default: from .env)",
    )
    args = parser.parse_args()

    try:
        summary = run_pipeline(input_dir=args.input_dir, db_url=args.db_url)
        print("\n" + "=" * 60)
        print("PIPELINE EXECUTION SUMMARY")
        print("=" * 60)
        print(f"Run ID:            {summary['run_id']}")
        print(f"Status:            {summary['status']}")
        print(f"Duration:          {summary['duration_seconds']}s")
        print(f"Records Extracted: {summary['records_extracted']}")
        print(f"Records Loaded:    {summary['records_loaded']}")
        print(f"Quarantined:       {summary['records_quarantined']}")
        print(f"Pass Rate:         {summary['data_quality_pass_rate_pct']}%")
        print("=" * 60)
        print("\nBreakdown by Entity:")
        for ent, cnts in summary["by_entity"].items():
            print(f"  - {ent.ljust(12)}: Extracted={cnts['extracted']}, Clean={cnts['clean']}, Rejected={cnts['rejected']}")
        print("\nTop Quarantine Rules Triggered:")
        for rule, count in summary["quarantine_summary"]["by_rule"].items():
            print(f"  - {rule.ljust(28)}: {count} violations")
        print("=" * 60 + "\n")

    except Exception as e:
        print(f"\n[-] Pipeline execution failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
