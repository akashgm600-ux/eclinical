"""Synthetic Clinical Trial Dataset Generator.

Generates realistic clinical trial datasets for Sites, Subjects, Protocol Visits,
and Laboratory Results. Deliberately introduces controlled data-quality anomalies
(duplicates, orphan foreign keys, date sequencing errors, out-of-range values,
and format dirtiness) to rigorously exercise the ETL pipeline and quarantine engine.
"""

from datetime import date, datetime, timedelta
import random
from typing import Dict, Tuple
import pandas as pd


# Deterministic random seeds for reproducibility
SEED = 42
random.seed(SEED)


LAB_TESTS = [
    {"code": "GLUC", "name": "Glucose, Fasting", "unit": "mg/dL", "low": 70.0, "high": 99.0, "base_mean": 85.0, "base_std": 12.0},
    {"code": "HGB", "name": "Hemoglobin", "unit": "g/dL", "low": 12.0, "high": 17.5, "base_mean": 14.5, "base_std": 1.5},
    {"code": "ALT", "name": "Alanine Aminotransferase", "unit": "U/L", "low": 7.0, "high": 56.0, "base_mean": 28.0, "base_std": 10.0},
    {"code": "AST", "name": "Aspartate Aminotransferase", "unit": "U/L", "low": 10.0, "high": 40.0, "base_mean": 24.0, "base_std": 8.0},
    {"code": "CREAT", "name": "Serum Creatinine", "unit": "mg/dL", "low": 0.6, "high": 1.3, "base_mean": 0.95, "base_std": 0.2},
]


def generate_sites_dataset(num_sites: int = 8, include_anomalies: bool = True) -> pd.DataFrame:
    """Generate clinical study sites with intentional quality anomalies."""
    countries = ["USA", "Germany", "United Kingdom", "Japan", "Canada", "France"]
    investigators = [
        "Dr. Eleanor Vance", "Dr. Marcus Brody", "Dr. Aris Thorne",
        "Dr. Clara Oswald", "Dr. Henry Wu", "Dr. Sarah Adams",
        "Dr. Kenji Sato", "Dr. Elena Rostova", "Dr. David Banner"
    ]

    records = []
    base_date = date(2023, 1, 15)

    for i in range(1, num_sites + 1):
        site_id = f"SITE-{100 + i}"
        records.append({
            "site_id": site_id,
            "site_name": f"Metropolitan Clinical Center {i}",
            "country": random.choice(countries),
            "investigator_name": investigators[(i - 1) % len(investigators)],
            "activation_date": (base_date + timedelta(days=i * 20)).strftime("%Y-%m-%d"),
            "status": "ACTIVE"
        })

    if include_anomalies:
        # Anomaly 1: Duplicate site record with casing dirt
        records.append({
            "site_id": "SITE-101",
            "site_name": "  Metropolitan Clinical Center 1 (Duplicate Entry)  ",
            "country": "USA",
            "investigator_name": "Dr. Eleanor Vance",
            "activation_date": "2023-01-35",  # Invalid date (day 35)
            "status": "ACTIVE"
        })

        # Anomaly 2: Invalid status
        records.append({
            "site_id": f"SITE-{100 + num_sites + 1}",
            "site_name": "Oceanic Trial Facility",
            "country": "Australia",
            "investigator_name": "Dr. Jack Shephard",
            "activation_date": "2023-06-01",
            "status": "PENDING_APPROVAL"  # Non-standard status code
        })

        # Anomaly 3: Missing required site_name
        records.append({
            "site_id": f"SITE-{100 + num_sites + 2}",
            "site_name": None,  # Missing mandatory attribute
            "country": "Canada",
            "investigator_name": "Dr. Walter Bishop",
            "activation_date": "2023-07-15",
            "status": "SUSPENDED"
        })

    return pd.DataFrame(records)


def generate_subjects_dataset(sites_df: pd.DataFrame, num_subjects: int = 50, include_anomalies: bool = True) -> pd.DataFrame:
    """Generate study subjects linked to sites with intentional data quality issues."""
    valid_site_ids = sites_df[sites_df["site_id"].notna()]["site_id"].tolist()
    genders = ["M", "F", "OTHER"]
    statuses = ["ENROLLED", "ACTIVE", "COMPLETED", "WITHDRAWN", "SCREEN_FAIL"]

    records = []
    base_date = date(2023, 3, 1)

    for i in range(1, num_subjects + 1):
        subj_id = f"SUBJ-{1000 + i}"
        site_id = random.choice(valid_site_ids)
        enroll_date = base_date + timedelta(days=random.randint(0, 180))
        birth_year = random.randint(1955, 2002)
        dob = date(birth_year, random.randint(1, 12), random.randint(1, 28))

        records.append({
            "subject_id": subj_id,
            "site_id": site_id,
            "enrollment_date": enroll_date.strftime("%Y-%m-%d"),
            "date_of_birth": dob.strftime("%Y-%m-%d"),
            "gender": random.choice(genders),
            "status": random.choice(statuses)
        })

    if include_anomalies:
        # Anomaly 1: Orphan Foreign Key (references non-existent site)
        records.append({
            "subject_id": "SUBJ-8888",
            "site_id": "SITE-999",  # Orphan Site ID
            "enrollment_date": "2023-04-10",
            "date_of_birth": "1980-05-12",
            "gender": "M",
            "status": "ENROLLED"
        })

        # Anomaly 2: Duplicate Subject ID
        records.append({
            "subject_id": "SUBJ-1002",  # Duplicate of SUBJ-1002
            "site_id": valid_site_ids[0],
            "enrollment_date": "2023-04-15",
            "date_of_birth": "1975-08-20",
            "gender": "F",
            "status": "ACTIVE"
        })

        # Anomaly 3: Missing site_id
        records.append({
            "subject_id": "SUBJ-8889",
            "site_id": None,  # Missing mandatory foreign key
            "enrollment_date": "2023-05-01",
            "date_of_birth": "1992-11-04",
            "gender": "F",
            "status": "ENROLLED"
        })

        # Anomaly 4: Invalid date format
        records.append({
            "subject_id": "SUBJ-8890",
            "site_id": valid_site_ids[0],
            "enrollment_date": "31/02/2023",  # Impossible February 31
            "date_of_birth": "1985-09-15",
            "gender": "M",
            "status": "ACTIVE"
        })

        # Anomaly 5: Casing/Whitespace dirtiness on status
        records.append({
            "subject_id": "SUBJ-8891",
            "site_id": valid_site_ids[0],
            "enrollment_date": "2023-06-12",
            "date_of_birth": "1988-03-22",
            "gender": "M",
            "status": "  enrolled  "  # Unnormalized casing and whitespace
        })

    return pd.DataFrame(records)


def generate_visits_dataset(subjects_df: pd.DataFrame, include_anomalies: bool = True) -> pd.DataFrame:
    """Generate clinical visits for subjects with sequence and relationship checks."""
    visit_schedule = [
        ("SCREENING", 0),
        ("BASELINE", 14),
        ("WEEK 4", 42),
        ("WEEK 12", 98),
        ("COMPLETION", 182),
    ]

    records = []
    visit_counter = 5000

    # Filter to subjects with clean parseable enrollment dates for scheduling
    valid_subjects = []
    for _, row in subjects_df.iterrows():
        try:
            if pd.notna(row["enrollment_date"]):
                enr = datetime.strptime(str(row["enrollment_date"]).strip(), "%Y-%m-%d").date()
                valid_subjects.append((row["subject_id"], enr))
        except ValueError:
            continue

    for subj_id, enroll_date in valid_subjects[:35]:  # Generate visits for subset of subjects
        for visit_name, day_offset in visit_schedule:
            visit_counter += 1
            visit_id = f"VIS-{visit_counter}"
            v_date = enroll_date + timedelta(days=day_offset + random.randint(-2, 3))
            status = "ATTENDED" if random.random() > 0.1 else "MISSED"

            records.append({
                "visit_id": visit_id,
                "subject_id": subj_id,
                "visit_name": visit_name,
                "visit_date": v_date.strftime("%Y-%m-%d"),
                "visit_status": status
            })

    if include_anomalies:
        # Anomaly 1: Temporal violation - Visit date strictly BEFORE subject enrollment date
        visit_counter += 1
        records.append({
            "visit_id": f"VIS-{visit_counter}",
            "subject_id": valid_subjects[0][0],
            "visit_name": "SCREENING",
            "visit_date": (valid_subjects[0][1] - timedelta(days=45)).strftime("%Y-%m-%d"),  # 45 days before enrollment!
            "visit_status": "ATTENDED"
        })

        # Anomaly 2: Orphan Foreign Key (subject does not exist)
        visit_counter += 1
        records.append({
            "visit_id": f"VIS-{visit_counter}",
            "subject_id": "SUBJ-9999",  # Orphan Subject ID
            "visit_name": "BASELINE",
            "visit_date": "2023-07-20",
            "visit_status": "ATTENDED"
        })

        # Anomaly 3: Missing visit_date
        visit_counter += 1
        records.append({
            "visit_id": f"VIS-{visit_counter}",
            "subject_id": valid_subjects[1][0],
            "visit_name": "WEEK 4",
            "visit_date": None,  # Mandatory date missing
            "visit_status": "ATTENDED"
        })

        # Anomaly 4: Duplicate visit ID
        records.append({
            "visit_id": "VIS-5002",  # Duplicate of earlier VIS-5002
            "subject_id": valid_subjects[1][0],
            "visit_name": "WEEK 4",
            "visit_date": "2023-08-10",
            "visit_status": "CANCELLED"
        })

    return pd.DataFrame(records)


def generate_labs_dataset(visits_df: pd.DataFrame, include_anomalies: bool = True) -> pd.DataFrame:
    """Generate laboratory results tied to visits and subjects with physiological bounds."""
    records = []
    lab_counter = 9000

    valid_visits = visits_df[visits_df["visit_date"].notna() & visits_df["subject_id"].notna()]

    for _, v_row in valid_visits.iloc[:60].iterrows():
        visit_id = v_row["visit_id"]
        subj_id = v_row["subject_id"]
        col_date = v_row["visit_date"]

        # Run 2 to 4 tests per visit
        tests_to_run = random.sample(LAB_TESTS, k=random.randint(2, 4))
        for t in tests_to_run:
            lab_counter += 1
            res_id = f"LAB-{lab_counter}"
            val = round(random.gauss(t["base_mean"], t["base_std"]), 2)

            flag = "NORMAL"
            if val < t["low"]:
                flag = "LOW"
            elif val > t["high"]:
                flag = "HIGH"

            records.append({
                "result_id": res_id,
                "visit_id": visit_id,
                "subject_id": subj_id,
                "test_code": t["code"],
                "test_name": t["name"],
                "result_value": val,
                "unit": t["unit"],
                "reference_low": t["low"],
                "reference_high": t["high"],
                "collection_date": col_date,
                "abnormal_flag": flag
            })

    if include_anomalies:
        # Anomaly 1: Physiological impossibility (Negative lab result value)
        lab_counter += 1
        records.append({
            "result_id": f"LAB-{lab_counter}",
            "visit_id": valid_visits.iloc[0]["visit_id"],
            "subject_id": valid_visits.iloc[0]["subject_id"],
            "test_code": "GLUC",
            "test_name": "Glucose, Fasting",
            "result_value": -24.5,  # Biologically impossible negative glucose
            "unit": "mg/dL",
            "reference_low": 70.0,
            "reference_high": 99.0,
            "collection_date": valid_visits.iloc[0]["visit_date"],
            "abnormal_flag": "CRITICAL"
        })

        # Anomaly 2: Extreme Outlier (Data entry error, e.g., missing decimal)
        lab_counter += 1
        records.append({
            "result_id": f"LAB-{lab_counter}",
            "visit_id": valid_visits.iloc[1]["visit_id"],
            "subject_id": valid_visits.iloc[1]["subject_id"],
            "test_code": "HGB",
            "test_name": "Hemoglobin",
            "result_value": 9999.0,  # Impossible hemoglobin > 1000
            "unit": "g/dL",
            "reference_low": 12.0,
            "reference_high": 17.5,
            "collection_date": valid_visits.iloc[1]["visit_date"],
            "abnormal_flag": "CRITICAL"
        })

        # Anomaly 3: Orphan Foreign Key (references non-existent visit)
        lab_counter += 1
        records.append({
            "result_id": f"LAB-{lab_counter}",
            "visit_id": "VIS-99999",  # Non-existent visit
            "subject_id": valid_visits.iloc[2]["subject_id"],
            "test_code": "ALT",
            "test_name": "Alanine Aminotransferase",
            "result_value": 32.0,
            "unit": "U/L",
            "reference_low": 7.0,
            "reference_high": 56.0,
            "collection_date": "2023-08-15",
            "abnormal_flag": "NORMAL"
        })

        # Anomaly 4: Duplicate Result ID
        records.append({
            "result_id": "LAB-9005",  # Duplicate of LAB-9005
            "visit_id": valid_visits.iloc[3]["visit_id"],
            "subject_id": valid_visits.iloc[3]["subject_id"],
            "test_code": "CREAT",
            "test_name": "Serum Creatinine",
            "result_value": 1.1,
            "unit": "mg/dL",
            "reference_low": 0.6,
            "reference_high": 1.3,
            "collection_date": valid_visits.iloc[3]["visit_date"],
            "abnormal_flag": "NORMAL"
        })

    return pd.DataFrame(records)


def generate_all_datasets(output_dir: str, include_anomalies: bool = True) -> Dict[str, pd.DataFrame]:
    """Generate all datasets and export to specified directory."""
    import os
    os.makedirs(output_dir, exist_ok=True)

    sites_df = generate_sites_dataset(num_sites=8, include_anomalies=include_anomalies)
    subjects_df = generate_subjects_dataset(sites_df, num_subjects=45, include_anomalies=include_anomalies)
    visits_df = generate_visits_dataset(subjects_df, include_anomalies=include_anomalies)
    labs_df = generate_labs_dataset(visits_df, include_anomalies=include_anomalies)

    sites_df.to_csv(os.path.join(output_dir, "sites.csv"), index=False)
    subjects_df.to_csv(os.path.join(output_dir, "subjects.csv"), index=False)
    visits_df.to_csv(os.path.join(output_dir, "visits.csv"), index=False)
    labs_df.to_csv(os.path.join(output_dir, "lab_results.csv"), index=False)

    return {
        "sites": sites_df,
        "subjects": subjects_df,
        "visits": visits_df,
        "lab_results": labs_df
    }
