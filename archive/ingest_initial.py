import csv
import random
import os
import shutil
import sys
import hashlib
from datetime import datetime

def generate_integrity_hash(row):
    # Combines key identity fields into a single string to detect row-shifts
    base_string = f"{row['offspring_MRN']}|{row['offspring_DOB']}|{row['stratum']}"
    return hashlib.md5(base_string.encode()).hexdigest()[:8]

def get_constants():
    c = {}
    if not os.path.exists('CONSTANTS.txt'):
        return None
    with open('CONSTANTS.txt', 'r') as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                k, v = line.strip().split('=')
                try:
                    c[k] = float(v)
                except ValueError:
                    c[k] = v
    return c

def calculate_age(dob_str):
    try:
        # Expected format: YYYY-MM-DD
        dob = datetime.strptime(dob_str, '%Y-%m-%d')
        return (datetime.now() - dob).days / 365.25
    except:
        return 0.0

def save_csv(data, fieldnames, filename, extrasaction='ignore'):
    with open(filename, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction=extrasaction)
        writer.writeheader()
        writer.writerows(data)

def update_maternal_flags(rows):
    """Updates relationship flags across the entire dataset."""
    maternal_map = {}
    for r in rows:
        m_id = r['maternal_MRN']
        if m_id not in maternal_map: maternal_map[m_id] = []
        maternal_map[m_id].append(r)

    for r in rows:
        m_id = r['maternal_MRN']
        r['multiple_offspring'] = 'Yes' if len(maternal_map[m_id]) > 1 else 'No'
        # Check if mother completed study with any other child
        r['prev_maternal_enrollment'] = 'Yes' if any(
            o['status'] == 'Completed' and o['offspring_MRN'] != r['offspring_MRN'] 
            for o in maternal_map[m_id]
        ) else 'No'
    return rows

def main(input_filename):
    C = get_constants()
    if not C: 
        print("Error: CONSTANTS.txt not found."); return
        
    # Ensure directories exist
    for d in [C.get('INPUT_DIR', 'inputs'), C.get('OUTPUT_DIR', 'outputs'), C.get('BACKUP_DIR', 'backups')]:
        if not os.path.exists(d): os.makedirs(d)

    input_path = os.path.join(C.get('INPUT_DIR', 'inputs'), input_filename)
    output_path = os.path.join(C.get('OUTPUT_DIR', 'outputs'), 'master_list.csv')

    if not os.path.exists(input_path):
        print(f"Error: Input file {input_path} not found.")
        return

    raw_data = []
    with open(input_path, 'r') as f:
        reader = csv.DictReader(f)
        raw_data = list(reader)

    fieldnames = list(raw_data[0].keys()) + [
        'current_age', 'eligible', 'status', 'contact_stage', 
        'last_contact_date', 'rand_num', 'multiple_offspring', 
        'prev_maternal_enrollment', 'integrity_hash', 'ROW_ID', 'verification_MRN'
    ]

    seen_offspring = set()
    unique_data = []
    
    for row in raw_data:
        o_id = row['offspring_MRN']
        if o_id in seen_offspring: continue
        seen_offspring.add(o_id)
        
        age = calculate_age(row['offspring_DOB'])
        row.update({
            'current_age': round(age, 2),
            'eligible': '1' if C['AGE_MIN'] <= age < C['AGE_MAX'] else '0',
            'status': 'Not Invited',
            'contact_stage': '-1',
            'last_contact_date': '',
            'rand_num': random.random(),
            'integrity_hash': generate_integrity_hash(row),
            'verification_MRN': o_id
        })
        unique_data.append(row)

    unique_data = update_maternal_flags(unique_data)
    unique_data.sort(key=lambda x: (x['stratum'], float(x['rand_num'])))
    
    # Assign ROW_ID after sorting
    for i, row in enumerate(unique_data):
        row['ROW_ID'] = i + 1

    save_csv(unique_data, fieldnames, output_path)
    print(f"Initialized {len(unique_data)} unique records to {output_path}. {len(raw_data) - len(unique_data)} duplicates skipped.")

    # Set Start Date if not present
    if 'START_DATE' not in C:
        today_str = datetime.now().strftime('%Y-%m-%d')
        with open('CONSTANTS.txt', 'a') as f:
            f.write(f"\nSTART_DATE={today_str}\n")
        print(f"Set study START_DATE to {today_str}")

if __name__ == "__main__":
    # Handle both new (1 arg) and old (2 arg) usage styles just in case, but prefer new
    if len(sys.argv) < 2: 
        print("Usage: python ingest_initial.py raw_data.csv")
    else: 
        # If user provides 2 args (input, output), we just take the input and ignore the output arg 
        # (since output path is now constant in C)
        # But wait, sys.argv[0] is script name.
        # sys.argv[1] is input.
        main(os.path.basename(sys.argv[1]))