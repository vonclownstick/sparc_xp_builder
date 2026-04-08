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
*   `--prior_list <file>`: (Recommended) The previous month's recruitment CSV, after the
    research team has updated it. The script uses this to advance the contact pipeline and
    update the master database.
*   `--weights S1,S2,...,S6`: (Optional) Override stratum weights for this run only.
    Does NOT modify CONSTANTS.txt. Example: `--weights 0.55,0.20,0.00,0.10,0.07,0.08`
*   `--allow-single-site`: Allow running with only one site's master file present.
*   `--yield <VALUE>`: Override all yield calculations with a fixed value.

**Action:**
1.  Locate last month's recruitment file (e.g., `recruitment_20260101.csv`).
2.  Update the `status` column for any participant who responded:
    *   Set to `Consented` if they agreed to enroll.
    *   Set to `Refused` if they explicitly declined.
    *   Leave as `Pending` if there was no response (the script will automatically
        advance them to the next contact stage).
    *   That's it -- `status` is the ONLY column you need to edit. Everything else
        (contact_stage, letter dates, stage advancement) is managed by the script.
    *   (Optional: you may correct `letter1_date`/`letter2_date`/`letter3_date` if the
        actual mail date differed from what the script recorded.)
3.  Run: `python3 update_recruitment.py --visits 40 --prior_list study_data/outputs/recruitment_20260101.csv`

**Result:**
*   Generates `study_data/outputs/recruitment_YYYYMMDD.csv` containing:
    *   Holdover participants still in the contact pipeline (stages 2 and 3), AND
    *   Newly selected invitees (stage 1).
    *   The `contact_stage` column tells you which letter to send (1, 2, or 3).
*   Updates the Master List statuses, including marking participants who exhausted all
    3 contacts without responding as `No Response - 3 Letters`.
*   Logs contact stage transitions and stratum-specific yield adjustments to console
    and `study_data/logs/`.

**Contact Stage Lifecycle:**
    Stage -1  -->  Stage 1  -->  Stage 2  -->  Stage 3  -->  Removed
    (master)      (letter 1)    (letter 2)    (letter 3)    (No Response - 3 Letters)

*   Stage 1 -> 2: Automatic on next run if still Pending.
*   Stage 2 -> 3: Automatic on next run if >28 days since letter 2 and still Pending.
*   Stage 3 -> Removed: Automatic on next run if still Pending. Master list updated.

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
When editing the recruitment file to create a `prior_list`:

*   `status` (THE ONLY COLUMN YOU NEED TO EDIT):
    *   `Consented` - Participant agreed to enroll. Stops further contact.
    *   `Refused` - Participant explicitly declined. Stops further contact.
    *   `Pending` - No response. Leave as-is; the script advances them automatically.

*   `letter1_date`, `letter2_date`, `letter3_date` (optional corrections):
    *   Only edit these if the actual mail date differs from the script-generated date.
    *   Format: YYYY-MM-DD.

*   `contact_stage` (DO NOT EDIT):
    *   Managed automatically by the script. Indicates which letter to send (1, 2, or 3).
