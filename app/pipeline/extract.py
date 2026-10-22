"""Extraction Stage: Reads and verifies source CSV datasets."""

import hashlib
import logging
from pathlib import Path
from typing import Dict, List, Tuple
import pandas as pd

logger = logging.getLogger(__name__)

# Expected mandatory columns per entity
REQUIRED_SCHEMAS: Dict[str, List[str]] = {
    "sites": ["site_id", "site_name", "country", "status"],
    "subjects": ["subject_id", "site_id", "enrollment_date", "status"],
    "visits": ["visit_id", "subject_id", "visit_name", "visit_date", "visit_status"],
    "lab_results": [
        "result_id",
        "visit_id",
        "subject_id",
        "test_code",
        "test_name",
        "result_value",
        "unit",
        "collection_date",
    ],
}


class ExtractionError(Exception):
    """Raised when an unrecoverable extraction failure occurs."""
    pass


def calculate_file_hash(file_path: Path) -> str:
    """Calculate SHA-256 checksum of an input file for auditability."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    return sha256.hexdigest()


def extract_datasets(input_dir: Path | str) -> Tuple[Dict[str, pd.DataFrame], Dict[str, dict]]:
    """Extract CSV files, validate availability, schema headers, and return dataframes with file metadata.

    Args:
        input_dir: Path to directory containing raw CSV files.

    Returns:
        Tuple of (Dict of entity_name -> DataFrame, Dict of entity_name -> metadata)
    """
    input_path = Path(input_dir)
    if not input_path.exists() or not input_path.is_dir():
        raise ExtractionError(f"Input directory does not exist: {input_path}")

    datasets: Dict[str, pd.DataFrame] = {}
    file_metadata: Dict[str, dict] = {}

    for entity, required_cols in REQUIRED_SCHEMAS.items():
        file_name = f"{entity}.csv"
        file_path = input_path / file_name

        if not file_path.exists():
            raise ExtractionError(f"Required input file missing: {file_path.name} in {input_path}")

        logger.info(f"Extracting entity '{entity}' from {file_path}")
        file_hash = calculate_file_hash(file_path)

        try:
            # Read CSV with string types initially to avoid silent cast corruptions
            df = pd.read_csv(file_path, dtype=str, keep_default_na=False)
        except Exception as e:
            raise ExtractionError(f"Failed to read CSV '{file_path}': {e}") from e

        # Validate header presence
        missing_cols = [c for c in required_cols if c not in df.columns]
        if missing_cols:
            raise ExtractionError(
                f"File '{file_name}' schema mismatch! Missing required columns: {missing_cols}. Found: {list(df.columns)}"
            )

        datasets[entity] = df
        file_metadata[entity] = {
            "file_name": file_name,
            "file_path": str(file_path.resolve()),
            "sha256": file_hash,
            "row_count": len(df),
            "columns": list(df.columns),
        }
        logger.info(f"Extracted '{entity}': {len(df)} rows, hash: {file_hash[:8]}...")

    return datasets, file_metadata
