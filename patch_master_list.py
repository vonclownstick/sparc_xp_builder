import csv
import os
import shutil
import argparse
from datetime import datetime

def get_constants():
    c = {}
    if not os.path.exists('CONSTANTS.txt'):
        return None
    with open('CONSTANTS.txt', 'r') as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                parts = line.strip().split('=')
                if len(parts) == 2:
                    k, v = parts
                    try:
                        c[k] = float(v)
                    except ValueError:
                        c[k] = v
    return c

def save_csv(data, fieldnames, filename):
    with open(filename, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)

def main():
    parser = argparse.ArgumentParser(description="Patch recruitment list to create new master list with blinded fields restored (model_score, model_pctile, stratum)")
    parser.add_argument("recruitment_file", help="Input recruitment CSV file (recruitment_YYYYMMDD.csv)")
    args = parser.parse_args()

    recruitment_file = args.recruitment_file
    if not os.path.exists(recruitment_file):
        print(f"Error: Recruitment file {recruitment_file} not found.")
        return

    C = get_constants()
    output_dir = C.get('OUTPUT_DIR', 'study_data/outputs')
    backup_dir = C.get('BACKUP_DIR', 'study_data/backups')

    # Read recruitment list
    with open(recruitment_file, 'r') as f:
        recruitment_rows = list(csv.DictReader(f))

    if not recruitment_rows:
        print("Error: Recruitment file is empty.")
        return

    print(f"Loaded {len(recruitment_rows)} rows from recruitment list.")

    # Load master lists to get model_score and model_pctile
    mgb_path = os.path.join(output_dir, 'parsed_mgb_master_list.csv')
    vumc_path = os.path.join(output_dir, 'parsed_vumc_master_list.csv')

    master_data = {}  # MRN -> {model_score, model_pctile}

    if os.path.exists(mgb_path):
        with open(mgb_path, 'r') as f:
            mgb_master = list(csv.DictReader(f))
            for row in mgb_master:
                mrn = row['offspring_MRN']
                master_data[mrn] = {
                    'model_score': row.get('model_score', ''),
                    'model_pctile': row.get('model_pctile', ''),
                    'stratum': row.get('stratum', '')
                }
        print(f"Loaded {len(mgb_master)} rows from MGB master list.")

    if os.path.exists(vumc_path):
        with open(vumc_path, 'r') as f:
            vumc_master = list(csv.DictReader(f))
            for row in vumc_master:
                mrn = row['offspring_MRN']
                master_data[mrn] = {
                    'model_score': row.get('model_score', ''),
                    'model_pctile': row.get('model_pctile', ''),
                    'stratum': row.get('stratum', '')
                }
        print(f"Loaded {len(vumc_master)} rows from VUMC master list.")

    if not master_data:
        print("Error: No master lists found. Cannot retrieve blinded fields (model_score, model_pctile, stratum).")
        return

    # Add model_score, model_pctile, and stratum back to recruitment rows
    # AIDEV-NOTE: These fields are excluded from recruitment list for blinding, but needed in master list
    patched_rows = []
    missing_count = 0

    for row in recruitment_rows:
        mrn = row['offspring_MRN']
        if mrn in master_data:
            row['model_score'] = master_data[mrn]['model_score']
            row['model_pctile'] = master_data[mrn]['model_pctile']
            row['stratum'] = master_data[mrn]['stratum']
            patched_rows.append(row)
        else:
            print(f"Warning: MRN {mrn} not found in master lists. Skipping.")
            missing_count += 1

    if missing_count > 0:
        print(f"Warning: {missing_count} rows skipped due to missing MRN in master lists.")

    # Determine site from the data (use 'site' column if available)
    # Group by site to create separate master lists
    sites = {}
    for row in patched_rows:
        site = row.get('site', 'UNKNOWN')
        if site not in sites:
            sites[site] = []
        sites[site].append(row)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M')

    # Create backup directory if needed
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)

    # Save new master lists for each site
    for site, site_rows in sites.items():
        if site == 'MGB':
            output_filename = 'parsed_mgb_master_list.csv'
        elif site == 'VUMC':
            output_filename = 'parsed_vumc_master_list.csv'
        else:
            print(f"Warning: Unknown site '{site}'. Skipping.")
            continue

        output_path = os.path.join(output_dir, output_filename)

        # Backup existing master list if it exists
        if os.path.exists(output_path):
            backup_path = os.path.join(backup_dir, f"{output_filename}_pre_patch_{timestamp}.csv")
            shutil.copy(output_path, backup_path)
            print(f"Backed up existing {output_filename} to {backup_path}")

        # Prepare fieldnames (ensure model_score and model_pctile are included)
        fieldnames = list(site_rows[0].keys())

        # Remove 'date_added_to_recruitment' if present (recruitment-specific field)
        if 'date_added_to_recruitment' in fieldnames:
            fieldnames.remove('date_added_to_recruitment')

        # Ensure model_score, model_pctile, and stratum are present
        if 'model_score' not in fieldnames:
            fieldnames.append('model_score')
        if 'model_pctile' not in fieldnames:
            fieldnames.append('model_pctile')
        if 'stratum' not in fieldnames:
            fieldnames.append('stratum')

        # Save new master list
        save_csv(site_rows, fieldnames, output_path)
        print(f"Saved new {site} master list to {output_path} ({len(site_rows)} rows)")

        # Create backup of new version
        backup_new_path = os.path.join(backup_dir, f"{output_filename}_patched_{timestamp}.csv")
        shutil.copy(output_path, backup_new_path)
        print(f"Backed up new {output_filename} to {backup_new_path}")

    print("\nPatch complete!")
    print(f"Total rows processed: {len(patched_rows)}")
    print(f"Sites updated: {', '.join(sites.keys())}")

if __name__ == "__main__":
    main()
