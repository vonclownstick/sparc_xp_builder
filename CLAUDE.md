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
    *   **3-Stage Contact System:** Automatically tracks and advances participants through a multi-letter outreach sequence (see below).
    *   **Dynamic Yield Adjustment:** Automatically adjusts sampling weights based on the actual response rates (yield) of each stratum to meet Target N goals.
    *   **Prior List Integration:** Ingests the previous month's recruitment list to update participant statuses and advance contact stages.
    *   **Holdover Management:** Carries forward participants still in the contact pipeline (stages 2 and 3) alongside new invites.
    *   **Site Allocation:** Distributes invites between MGB (approx. 2/3) and VUMC (approx. 1/3) according to constants.
    *   **Stratified Random Sampling:** Selects new participants randomly within each stratum to meet targets.
    *   **Safety:** Automatically creates validated backups in a `backups/` directory.
*   **Options:**
    *   `--allow-single-site`: By default, the script requires both MGB and VUMC master lists to be present. Use this flag to allow running with only one site's data available (all invites will go to that site).
    *   `--weights S1,S2,S3,S4,S5,S6`: Override stratum weights for this run only (e.g., `--weights 0.55,0.20,0.00,0.10,0.07,0.08`). Does not modify CONSTANTS.txt.
    *   `--yield VALUE`: Override all yield calculations with a fixed value (e.g., `--yield 0.05`).

#### Contact Stage Lifecycle

Each participant progresses through a 3-letter outreach sequence, managed automatically by the script:

| Stage | Trigger | Action |
|-------|---------|--------|
| **-1** (default) | Participant is in master list but never selected | No contact |
| **1** | Selected for a new recruitment batch | `letter1_date` set, initial letter sent |
| **2** | Next run, participant still Pending | `letter2_date` set, follow-up letter sent |
| **3** | Next run, >28 days since letter 2, still Pending | `letter3_date` set, final letter sent |
| **Removed** | Next run, stage 3 participant still Pending | Status set to `No Response - 3 Letters` in master list, removed from active recruitment |

Participants marked as `Consented`, `Completed`, or `Refused` at any stage are removed from the pipeline and not advanced further.

#### Prior List Workflow (What the Research Team Does)

1.  The script outputs a recruitment CSV with all active participants (`contact_stage` tells you which letter to send).
2.  The research team sends letters and updates **only the `status` column**:
    *   **`Consented`** — participant agreed to enroll
    *   **`Refused`** — participant explicitly declined
    *   **Leave as `Pending`** — no response yet (the script advances them automatically)
3.  The edited CSV is fed back as `--prior_list` on the next run.

**Optional:** The team may also correct `letter1_date`, `letter2_date`, or `letter3_date` if the actual mail date differed from the script-generated date. These corrections are preserved.

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
Specify the target number of fresh invites and provide the prior list.
```bash
python3 update_recruitment.py --visits 40 --prior_list study_data/outputs/recruitment_previous.csv

# Run with only one site's data available:
python3 update_recruitment.py --visits 40 --allow-single-site

# Override stratum weights for a catch-up run (does not modify CONSTANTS.txt):
python3 update_recruitment.py --visits 40 --weights 0.55,0.20,0.00,0.10,0.07,0.08
```

### 3. View Report
```bash
python3 consort.py
```

## Data Integrity Safety
The system uses `integrity_hash` (MD5 of MRN, DOB, and Stratum) and `verification_MRN` to detect accidental row-sorting or data corruption in the master CSV files.