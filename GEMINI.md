# SPARC-XP Recruitment System (Updated)

## Project Overview
This project is a standalone Python-based toolkit designed to manage and automate the recruitment process for the ASD (Autism Spectrum Disorder) Recruitment Protocol (SPARC-XP). It handles the end-to-end recruitment lifecycle, including cohort selection, age eligibility tracking, maternal relationship deduplication, and automated outreach generation.

## Architecture & Key Scripts

The system consists of three main operational scripts and a configuration file:

### 1. Master List Management (`update_master.py`)
*   **Purpose:** Ingests raw data dumps from MGB and VUMC and maintains the master study database.
*   **Key Functions:**
    *   Ingests raw CSV data (expects `mgb_` or `vumc_` prefix).
    *   Calculates age and eligibility (Age 4-6).
    *   Assigns participants to risk strata (S1-S6) based on model percentiles.
    *   Deduplicates offspring by MRN.
    *   Flags maternal relationships (multiple offspring, previous enrollments).
    *   Maintains `date_added` and `integrity_hash` for data safety.
*   **Options:**
    *   `--trim N`: After excluding age-ineligible participants, randomly downsample to N rows while maintaining the proportional distribution across strata.

### 2. Recruitment List Generation (`update_recruitment.py`)
*   **Purpose:** The core operational script to generate monthly outreach lists.
*   **Key Functions:**
    *   **Dynamic Yield Adjustment:** Automatically adjusts sampling weights based on the actual response rates (yield) of each stratum to meet Target N goals.
    *   **Prior List Integration:** Ingests the previous month's recruitment list to update participant statuses (e.g., Completed, Refused).
    *   **Holdover Management:** Prioritizes participants who were invited but haven't completed the visit yet.
    *   **Site Allocation:** Distributes invites between MGB (approx. 2/3) and VUMC (approx. 1/3) according to constants.
    *   **Stratified Random Sampling:** Selects new participants randomly within each stratum to meet targets.
    *   **Safety:** Automatically creates validated backups in a `backups/` directory.
*   **Options:**
    *   `--allow-single-site`: By default, the script requires both MGB and VUMC master lists to be present. Use this flag to allow running with only one site's data available (all invites will go to that site).

### 3. Reporting (`consort.py`)
*   **Purpose:** Generates a historical summary of recruitment batches.
*   **Output:** Prints a table showing dates, sites, strata, yield rates, and counts added per batch.

### 4. Configuration (`CONSTANTS.txt`)
*   **Purpose:** Central configuration file for study parameters.
*   **Parameters:**
    *   Recruitment weights (`S1_WEIGHT` to `S6_WEIGHT`)
    *   Site ratios (`MGB_RATIO`, `VUMC_RATIO`)
    *   Age eligibility limits (`AGE_MIN`, `AGE_MAX`)
    *   Follow-up intervals (`FOLLOWUP_X_DAYS`)
    *   **Yield defaults** (`S1_YIELD` to `S6_YIELD`): Default yield values used when no historical data exists
        *   Calculated yields from historical data take precedence when available
        *   Site-specific defaults supported: `MGB_S1_YIELD=0.15`, `VUMC_S1_YIELD=0.08`, etc.
        *   Priority: calculated from history > site-specific default > generic default > 0.1

## Usage Guide

### 1. Update Master Lists
Place raw data in the root or `study_data/inputs/`.
```bash
python3 update_master.py mgb_data_20260108.csv
python3 update_master.py vumc_data_20260108.csv

# Optionally trim to a specific size while maintaining stratum proportions:
python3 update_master.py mgb_data_20260108.csv --trim 1000
```

### 2. Generate Recruitment Batch
Specify the target number of completed visits.
```bash
python3 update_recruitment.py --visits 40 --prior_list study_data/outputs/recruitment_previous.csv

# Run with only one site's data available:
python3 update_recruitment.py --visits 40 --allow-single-site
```

### 3. View Report
```bash
python3 consort.py
```

## Data Integrity Safety
The system uses `integrity_hash` (MD5 of MRN, DOB, and Stratum) and `verification_MRN` to detect accidental row-sorting or data corruption in the master CSV files.