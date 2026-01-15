SPARC-XP RECRUITMENT SYSTEM: ANALYST INSTRUCTIONS
===================================================

This document outlines the standard operating procedure (SOP) for running the monthly recruitment cycle.

PREREQUISITES
-------------
*   Python 3.x installed.
*   Access to the project directory.
*   New raw data dumps from MGB and/or VUMC.

DIRECTORY STRUCTURE
-------------------
*   `study_data/inputs/`: Place raw CSV dumps here.
*   `study_data/outputs/`: Generated Master Lists and Recruitment Lists appear here.
*   `study_data/backups/`: Automatic backups of every file modification.
*   `study_data/logs/`: Detailed execution logs.
*   `CONSTANTS.txt`: Configuration file for weights and parameters.

WORKFLOW OVERVIEW
-----------------
Run the scripts in this exact order:
1.  `update_master.py` (Run twice: once for MGB, once for VUMC)
2.  `update_recruitment.py`
3.  `consort.py` (Optional, for reporting)

-------------------------------------------------------------------------------
STEP 1: INGEST NEW DATA
-------------------------------------------------------------------------------
**Command:** `python3 update_master.py <filename>`

**Inputs:**
*   Raw CSV files must start with `mgb_` or `vumc_`.
*   Required Columns: `mother_MRN`, `offspring_MRN`, `offspring_DOB`, `model_pctile` (plus other identifiers).

**Action:**
1.  Place your new files (e.g., `mgb_jan2026.csv`) in the project root or direct path.
2.  Run: `python3 update_master.py mgb_jan2026.csv`
3.  Confirm [Y] if prompted to update an existing master list.
4.  Repeat for VUMC: `python3 update_master.py vumc_jan2026.csv`

**Result:**
*   Updates `study_data/outputs/parsed_mgb_master_list.csv` (and vumc equivalent).
*   Backups saved to `study_data/backups/`.

-------------------------------------------------------------------------------
STEP 2: GENERATE RECRUITMENT LIST
-------------------------------------------------------------------------------
**Command:** `python3 update_recruitment.py --visits <N> [--prior_list <file>]`

**Arguments:**
*   `--visits <N>`: (Required) Total number of *fresh invites* to generate for this batch.
*   `--prior_list <file>`: (Recommended) The previous month's recruitment CSV. Used to update participant statuses (e.g., to 'Completed' or 'Refused') in the master database, which ensures accurate yield calculations for the new batch.

**Action:**
1.  Locate last month's recruitment file (e.g., `recruitment_20260101.csv`).
    *   *Important:* Ensure you have marked participants as 'Completed', 'Refused', etc., in this file before running.
2.  Run: `python3 update_recruitment.py --visits 40 --prior_list study_data/outputs/recruitment_20260101.csv`

**Result:**
*   Generates `study_data/outputs/recruitment_YYYYMMDD.csv` containing ONLY NEW invitees.
*   Updates the Master List statuses.
*   Logs Stratum-specific yield adjustments to console and `study_data/logs/`.

-------------------------------------------------------------------------------
STEP 3: REPORTING
-------------------------------------------------------------------------------
**Command:** `python3 consort.py`

**Action:**
*   Run anytime to view a historical table of recruitment batches, showing date, site, stratum, yield rates, and counts added.

-------------------------------------------------------------------------------
CONFIGURATION (CONSTANTS.txt)
-------------------------------------------------------------------------------
Edit `CONSTANTS.txt` to adjust:
*   **Weights (`S1_WEIGHT`...)**: Target proportion of recruits from each risk stratum.
*   **Ratios (`MGB_RATIO`)**: Split between sites (Default: ~67% MGB, ~33% VUMC).
*   **Age Limits**: `AGE_MIN` / `AGE_MAX` (Default: 4.0 / 6.0).

**Current Strata Definitions:**
*   S1 (Top 5%): P > 95.0
*   S2 (5-10%):  90.0 < P <= 95.0
*   S3 (Decile 9): 80.0 < P <= 90.0
*   S4 (Mid-High): 50.0 < P <= 80.0
*   S5 (Low-Mid):  10.0 < P <= 50.0
*   S6 (Bottom 10%): P <= 10.0

**Recruitment File Management:**
When editing the recruitment file to create a `prior_list`, you can use the following columns:
*   `status`: Updates the participant's status.
    *   Valid values: 'Pending', 'Completed', 'Refused', 'No Response', 'invite 1 sent', 'invite 2 sent'.
    *   Participants with 3 letters sent should generally be marked as 'Refused' or 'No Response' to prevent further contact.
*   `letter1_date`: Date the first letter was sent (YYYY-MM-DD).
*   `letter2_date`: Date the second letter was sent (YYYY-MM-DD).
