SPARC-XP RECRUITMENT SYSTEM: USER GUIDE
=======================================

This system automates the selection of participants for the SPARC-XP study. It manages the participant database, tracks eligibility, and generates stratified recruitment lists based on study targets and historical response rates.

The process consists of three sequential steps:

STEP 1: UPDATE MASTER DATABASE
------------------------------
**Script:** `update_master.py`

This script is responsible for ingesting raw data from clinical sites (MGB and VUMC) and maintaining the central study database.

**Key Actions:**
1.  **Ingestion:** Reads raw CSV data files containing potential participants.
2.  **Eligibility Check:** Calculates age to ensure participants are within the eligible range (4.0 to 6.0 years).
3.  **Stratification:** Assigns each participant to a Risk Stratum (S1-S6) based on their model percentile score.
4.  **Deduplication:** Identifies and links siblings or multiple births to the same mother to prevent over-recruitment from single families.
5.  **Status Updates:** For participants already in the system, it updates their records with the latest data without overwriting their original entry date or selection status.

STEP 2: GENERATE RECRUITMENT LIST
---------------------------------
**Script:** `update_recruitment.py`

This script selects a specific number of *new* participants for outreach.

**Key Actions:**
1.  **Status Reconciliation:** Reads the previous month's recruitment list (if provided) to update the status of previously invited participants (e.g., marking them as 'Completed' or 'Refused').
2.  **Yield Calculation:** Calculates the actual success rate (Yield) for each stratum based on historical data.
3.  **Dynamic Weighting:** Adjusts the number of invites per stratum. If a group has a low response rate, the system increases the number of invites for that group to ensure the study meets its final enrollment targets.
4.  **Selection:** Randomly selects eligible, non-invited participants from the master database to meet the specified target number of fresh invites.
5.  **Output:** Generates a CSV file containing only the new participants to be contacted.

STEP 3: REPORTING
-----------------
**Script:** `consort.py`

This script provides a historical overview of the recruitment process.

**Key Actions:**
1.  **Log Parsing:** Reads the system logs from all previous recruitment runs.
2.  **Summary Table:** Prints a table showing the date of each run, the site (MGB/VUMC), the number of participants invited per stratum, and the calculated yield at that time.

-------------------------------------------------------------------------------
DATA SECURITY & INTEGRITY
-------------------------------------------------------------------------------
To prevent data corruption—specifically errors caused by manual editing in spreadsheet software (like Excel)—the system employs a cryptographic "Integrity Hash."

**How it works:**
The system generates a unique code (Hash) for every participant by mathematically combining three critical pieces of information:
1.  Offspring MRN (Medical Record Number)
2.  Date of Birth
3.  Risk Stratum

**Why this is important:**
A common error in manual data management occurs when a user sorts a spreadsheet but accidentally selects only *some* columns (e.g., sorting names but not medical record numbers). This results in a "row shift," where a patient's name might be aligned with another patient's medical history.

**The Safeguard:**
Every time the system reads the Master List, it recalculates this Hash based on the data in the row.
*   **Match:** If the calculated Hash matches the stored Hash, the data is safe.
*   **Mismatch:** If they do not match, it means the data has been altered or shifted. The system will immediately stop and alert the user to the corruption, preventing invalid data from being used.