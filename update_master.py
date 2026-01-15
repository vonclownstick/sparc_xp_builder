import csv
import random
import os
import shutil
import sys
import hashlib
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

def save_constants(c):
    with open('CONSTANTS.txt', 'w') as f:
        for k, v in c.items():
            f.write(f"{k}={v}\n")

def calculate_age(dob_str):
    try:
        # Expected format: YYYY-MM-DD
        dob = datetime.strptime(dob_str, '%Y-%m-%d')
        return (datetime.now() - dob).days / 365.25
    except:
        return 0.0

def get_stratum(pctile):
    try:
        p = float(pctile)
        if p > 95.0: return 'S1'
        if p > 90.0: return 'S2'
        if p > 80.0: return 'S3'
        if p > 50.0: return 'S4'
        if p > 10.0: return 'S5'
        return 'S6'
    except:
        return 'S6'

def generate_integrity_hash(row):
    # Combines key identity fields into a single string to detect row-shifts
    base_string = f"{row['offspring_MRN']}|{row['offspring_DOB']}|{row['stratum']}"
    return hashlib.md5(base_string.encode()).hexdigest()[:8]

def update_maternal_flags(rows):
    maternal_map = {}
    for r in rows:
        m_id = r['mother_MRN']
        if m_id not in maternal_map: maternal_map[m_id] = []
        maternal_map[m_id].append(r)

    for r in rows:
        m_id = r['mother_MRN']
        r['multiple_offspring'] = 'Yes' if len(maternal_map[m_id]) > 1 else 'No'
        r['prev_maternal_enrollment'] = 'Yes' if any(
            o['status'] == 'Completed' and o['offspring_MRN'] != r['offspring_MRN'] 
            for o in maternal_map[m_id]
        ) else 'No'
    return rows

def main():
    if len(sys.argv) < 2:
        print("Usage: python update_master.py <input_file.csv>")
        return

    input_file = sys.argv[1]
    filename = os.path.basename(input_file)
    
    if filename.startswith('mgb_'):
        site = 'MGB'
        master_list_name = 'parsed_mgb_master_list.csv'
    elif filename.startswith('vumc_'):
        site = 'VUMC'
        master_list_name = 'parsed_vumc_master_list.csv'
    else:
        print("Error: Input file must start with 'mgb_' or 'vumc_'.")
        return

    C = get_constants()
    output_dir = C.get('OUTPUT_DIR', 'study_data/outputs')
    backup_dir = C.get('BACKUP_DIR', 'study_data/backups')
    master_list_path = os.path.join(output_dir, master_list_name)
    
    today_str = datetime.now().strftime('%Y-%m-%d')
    timestamp = datetime.now().strftime('%Y%m%d_%H%M')

    # Backup ingested file
    if not os.path.exists(backup_dir): os.makedirs(backup_dir)
    shutil.copy(input_file, os.path.join(backup_dir, f"{filename}_{timestamp}.csv"))

    existing_rows = []
    if os.path.exists(master_list_path):
        ans = input(f"{master_list_name} already exists. Do you want to update it? [Y/N]: ")
        if ans.lower() != 'y':
            print("Aborted.")
            return
        
        # Backup prior version
        shutil.copy(master_list_path, os.path.join(backup_dir, f"{master_list_name}_{timestamp}.csv"))
        
        with open(master_list_path, 'r') as f:
            existing_rows = list(csv.DictReader(f))

    existing_map = {r['offspring_MRN']: r for r in existing_rows}
    
    with open(input_file, 'r') as f:
        new_data = list(csv.DictReader(f))

    new_mrns = {r['offspring_MRN'] for r in new_data}
    
    final_rows = []
    added_count = 0
    removed_count = 0

    # Process new and updated records
    for row in new_data:
        mrn = row['offspring_MRN']
        if mrn in existing_map:
            # Keep existing record, maybe update some fields? 
            # Instructions say: "we do not change the date_added for existing entries"
            # and "only add the people where their offspring_MRN value was not previously present"
            # This implies we keep the OLD record if it exists.
            final_rows.append(existing_map[mrn])
        else:
            # New record
            row['date_added'] = today_str
            row['status'] = 'Not Invited'
            row['current_age'] = round(calculate_age(row['offspring_DOB']), 2)
            row['eligible'] = '1' if C['AGE_MIN'] <= float(row['current_age']) < C['AGE_MAX'] else '0'
            row['stratum'] = get_stratum(row['model_pctile'])
            row['contact_stage'] = '-1'
            row['last_contact_date'] = ''
            row['rand_num'] = random.random()
            row['integrity_hash'] = generate_integrity_hash(row)
            row['verification_MRN'] = mrn
            row['site'] = site
            final_rows.append(row)
            added_count += 1

    # Handle removals
    for mrn, row in existing_map.items():
        if mrn not in new_mrns:
            if row['status'] != 'Not Invited':
                # Keep them if they have been invited
                final_rows.append(row)
            else:
                # Remove them
                removed_count += 1

    final_rows = update_maternal_flags(final_rows)
    
    # Fieldnames
    if final_rows:
        fieldnames = list(final_rows[0].keys())
        # Ensure all necessary fields are present
        required_fields = ['date_added', 'status', 'current_age', 'eligible', 'stratum', 
                           'contact_stage', 'last_contact_date', 'rand_num', 
                           'integrity_hash', 'verification_MRN', 'site',
                           'multiple_offspring', 'prev_maternal_enrollment',
                           'letter1_date', 'letter2_date']
        for f in required_fields:
            if f not in fieldnames: fieldnames.append(f)
        
        # Ensure all rows have the required keys
        for row in final_rows:
            for f in required_fields:
                if f not in row: row[f] = ''
            
        with open(master_list_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(final_rows)
        
        # Backup new version
        shutil.copy(master_list_path, os.path.join(backup_dir, f"{master_list_name}_new_{timestamp}.csv"))

    # Stats
    prev_offspring = len(existing_rows)
    prev_mothers = len(set(r['mother_MRN'] for r in existing_rows))
    curr_offspring = len(final_rows)
    curr_mothers = len(set(r['mother_MRN'] for r in final_rows))
    
    print(f"\nUpdate Summary for {site}:")
    print(f"Previous: {prev_offspring} offspring, {prev_mothers} mothers")
    print(f"Updated:  {curr_offspring} offspring, {curr_mothers} mothers")
    print(f"Added:    {added_count}")
    print(f"Removed:  {removed_count}")

    # Update CONSTANTS
    if 'START_DATE' not in C:
        C['START_DATE'] = today_str
    C['LAST_UPDATE'] = today_str
    save_constants(C)

if __name__ == "__main__":
    main()
