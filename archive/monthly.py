import csv
import random
import os
import shutil
import argparse
import hashlib
from datetime import datetime

# Global log file path (set in main)
LOG_FILE = None

def log(message):
    print(message)
    if LOG_FILE:
        with open(LOG_FILE, 'a') as f:
            f.write(message + "\n")

def generate_integrity_hash(row):
    # Combines key identity fields into a single string to detect row-shifts
    base_string = f"{row['offspring_MRN']}|{row['offspring_DOB']}|{row['stratum']}"
    return hashlib.md5(base_string.encode()).hexdigest()[:8]

def check_data_integrity(rows):
    errors = []
    for i, row in enumerate(rows):
        # 1. Check if the verification MRN still matches the main MRN
        if row.get('verification_MRN') and row['offspring_MRN'] != row['verification_MRN']:
            errors.append(f"Row {i+2}: MRN mismatch (Sorted incorrectly?)")
            
        # 2. Re-calculate hash and compare
        if row.get('integrity_hash'):
            current_hash = generate_integrity_hash(row)
            if current_hash != row['integrity_hash']:
                errors.append(f"Row {i+2}: Data drift (DOB or Stratum changed for this MRN)")
            
    if errors:
        log("!!! CRITICAL DATA INTEGRITY ERROR !!!")
        for err in errors[:5]: log(err) # Show first 5 errors
        if len(errors) > 5: log(f"...and {len(errors)-5} more.")
        return False
    return True

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
                    c[k] = v # Handle dates/strings
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

def validate_and_backup(filename, backup_dir):
    if not os.path.exists(backup_dir): os.makedirs(backup_dir)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M')
    backup_name = os.path.join(backup_dir, f"{os.path.basename(filename).split('.')[0]}_backup_{timestamp}.csv")
    shutil.copy(filename, backup_name)
    with open(backup_name, 'r') as f:
        if not f.read(1): raise Exception("Backup failed validation.")
    log(f"Backup validated: {backup_name}")

def main():
    global LOG_FILE
    parser = argparse.ArgumentParser(description="Monthly Recruitment Manager")
    parser.add_argument("-u", "--updates", help="Filename of the edited outreach CSV with status updates (in inputs folder)", default=None)
    parser.add_argument("-r", "--refresh", help="Filename of new quarterly data for ingestion (in inputs folder)", default=None)
    parser.add_argument("--target_n", type=int, help="Override target number of recruits", default=None)
    parser.add_argument("--yield_rate", type=float, help="Override expected yield rate", default=0.2)
    parser.add_argument("--force", action="store_true", help="Skip off-cycle confirmation")
    
    args = parser.parse_args()
    C = get_constants()
    
    # Ensure directories exist
    for d in [C.get('INPUT_DIR', 'inputs'), C.get('OUTPUT_DIR', 'outputs'), C.get('BACKUP_DIR', 'backups'), C.get('LOG_DIR', 'logs')]:
        if not os.path.exists(d): os.makedirs(d)

    # Setup Logging
    today = datetime.now()
    log_dir = C.get('LOG_DIR', 'logs')
    LOG_FILE = os.path.join(log_dir, f"monthly_{today.strftime('%Y-%m-%d')}.log")

    master_csv_path = os.path.join(C.get('OUTPUT_DIR', 'outputs'), 'master_list.csv')
    
    if not os.path.exists(master_csv_path):
        log(f"Error: Master file {master_csv_path} not found. Please run ingest_initial.py first.")
        return

    with open(master_csv_path, 'r') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)
    
    if not rows:
        log(f"Error: Master list {master_csv_path} contains no data rows. It may have been corrupted. Please restore from backup or re-run initialization.")
        return

    # --- Integrity Check ---
    if not check_data_integrity(rows):
        log("Aborting due to data integrity errors.")
        return

    # --- Date & Cycle Logic ---
    if 'START_DATE' not in C:
        log("Warning: START_DATE not found in CONSTANTS.txt. Assuming Month 1.")
        months_passed = 0
        diff = 0
    else:
        start_date = datetime.strptime(C['START_DATE'], '%Y-%m-%d')
        months_passed = (today.year - start_date.year) * 12 + today.month - start_date.month
        
        cycle_day = start_date.day
        current_day = today.day
        # Calculate signed deviation
        # If today is 5th and cycle is 1st -> +4
        # If today is 28th and cycle is 1st -> -3 (approx)
        
        # Simple deviation: today - cycle
        raw_diff = current_day - cycle_day
        # adjusting for wrap-around
        if raw_diff > 15: diff = raw_diff - 30 # e.g. 28 - 1 = 27 -> -3
        elif raw_diff < -15: diff = raw_diff + 30 # e.g. 2 - 28 = -26 -> +4
        else: diff = raw_diff
        
        diff_str = f"{'+' if diff >= 0 else ''}{diff}"
        
        log(f"Run {today.strftime('%-m/%-d/%y %-I:%M%p')}, MONTH {months_passed}, {diff_str} days")
        
        if abs(diff) > 7 and not args.force:
            log(f"WARNING: Today ({today.strftime('%Y-%m-%d')}) is >7 days from the cycle start day ({cycle_day}).")
            confirm = input("Are you sure you want to run off-cycle? [y/N]: ")
            if confirm.lower() != 'y':
                log("Aborted.")
                return

    # --- Target Logic ---
    if args.target_n:
        target_n = args.target_n
    else:
        target_n = 40 if months_passed <= 1 else 80
    
    list_size = int(target_n / args.yield_rate)
    log(f"Plan: Target N={target_n} (Yield={args.yield_rate}) -> Generating List Size: {list_size}")

    fieldnames = list(rows[0].keys())
    # Ensure integrity fields are in fieldnames (if adding new ones)
    for f in ['integrity_hash', 'ROW_ID', 'verification_MRN']:
        if f not in fieldnames: fieldnames.append(f)
        
    outreach_fieldnames = fieldnames + ['carryover']

    # 1. Ingest Status Updates & Carryover
    carryover_list = []
    
    if args.updates:
        update_path = os.path.join(C.get('INPUT_DIR', 'inputs'), args.updates)
        if os.path.exists(update_path):
            log(f"Ingesting updates from {update_path}...")
            with open(update_path, 'r') as f:
                update_rows = list(csv.DictReader(f))
            
            master_map = {r['offspring_MRN']: r for r in rows}
            updated_count = 0
            
            for u_row in update_rows:
                mrn = u_row['offspring_MRN']
                if mrn in master_map:
                    m_row = master_map[mrn]
                    # Update Status
                    if u_row.get('status') and u_row['status'] != m_row['status']:
                        m_row['status'] = u_row['status']
                        updated_count += 1
                    
                    # Carryover Check
                    if m_row['status'] == 'Pending':
                        m_row['carryover'] = 'Yes'
                        if u_row.get('contact_stage'): m_row['contact_stage'] = u_row['contact_stage']
                        if u_row.get('last_contact_date'): m_row['last_contact_date'] = u_row['last_contact_date']
                        carryover_list.append(m_row)
            
            log(f"Applied updates to {updated_count} records.")
            log(f"Identified {len(carryover_list)} carryover participants (still Pending).")
        else:
            log(f"Warning: Update file {update_path} not found. Skipping updates.")

    # 2. Update Age & Age-Out
    for row in rows:
        row['current_age'] = round(calculate_age(row['offspring_DOB']), 2)
        if float(row['current_age']) >= C['AGE_MAX'] and row['status'] not in ['Completed', 'Refused']:
            row['status'] = 'Aged Out'

    # 3. Quarterly Refresh
    if args.refresh:
        refresh_path = os.path.join(C.get('INPUT_DIR', 'inputs'), args.refresh)
        if os.path.exists(refresh_path):
            with open(refresh_path, 'r') as f:
                new_data = list(csv.DictReader(f))
            existing_offspring = {r['offspring_MRN'] for r in rows}
            added = 0
            for r in new_data:
                if r['offspring_MRN'] not in existing_offspring:
                    age = calculate_age(r['offspring_DOB'])
                    r.update({
                        'current_age': round(age, 2), 'eligible': '1' if C['AGE_MIN'] <= age < C['AGE_MAX'] else '0',
                        'status': 'Not Invited', 'contact_stage': '-1', 'last_contact_date': '', 'rand_num': random.random(),
                        # Generate integrity fields for new rows
                        'integrity_hash': generate_integrity_hash(r),
                        'verification_MRN': r['offspring_MRN']
                    })
                    rows.append(r)
                    existing_offspring.add(r['offspring_MRN'])
                    added += 1
            log(f"Refresh: {added} new offspring added.")
        else:
             log(f"Warning: Refresh file {refresh_path} not found. Skipping refresh.")

    # 4. Update Maternal Flags
    rows = update_maternal_flags(rows)
    rows.sort(key=lambda x: (x['stratum'], float(x['rand_num'])))
    
    # Re-assign ROW_ID after sorting
    for i, row in enumerate(rows):
        row['ROW_ID'] = i + 1

    # 5. Generate Outreach List
    outreach = list(carryover_list) 
    carryover_ids = {r['offspring_MRN'] for r in outreach}

    for row in rows:
        if row['offspring_MRN'] in carryover_ids: continue
        
        if row['status'] == 'Pending' and row['last_contact_date']:
            try:
                last_date = datetime.strptime(row['last_contact_date'], '%Y-%m-%d')
                delta = (today - last_date).days
                stage = int(row['contact_stage'])
                needs_remind = (
                    (stage == 0 and delta >= C['FOLLOWUP_1_DAYS']) or
                    (stage == 7 and delta >= (C['FOLLOWUP_2_DAYS'] - C['FOLLOWUP_1_DAYS'])) or
                    (stage == 30 and delta >= (C['FOLLOWUP_3_DAYS'] - C['FOLLOWUP_2_DAYS']))
                )
                if needs_remind:
                    row['contact_stage'] = str(7 if stage == 0 else (30 if stage == 7 else 90))
                    row['last_contact_date'] = today.strftime('%Y-%m-%d')
                    row['carryover'] = 'No' 
                    outreach.append(row)
                    carryover_ids.add(row['offspring_MRN'])
            except ValueError: pass

    # Pull New Batch
    n_existing = len(outreach)
    n_needed = list_size - n_existing
    
    if n_needed > 0:
        log(f"Pulling {n_needed} new participants to reach list size {list_size}...")
        weights = {f'S{i}': C[f'S{i}_WEIGHT'] for i in range(1, 6)}
        
        for s, w in weights.items():
            n_stratum = int(n_needed * w)
            count = 0
            for row in rows:
                if count >= n_stratum: break
                if row['offspring_MRN'] in carryover_ids: continue
                
                if row['stratum'] == s and row['status'] == 'Not Invited' and C['AGE_MIN'] <= float(row['current_age']) < C['AGE_MAX']:
                    row['status'] = 'Pending'; row['contact_stage'] = '0'
                    row['last_contact_date'] = today.strftime('%Y-%m-%d')
                    row['carryover'] = 'No'
                    outreach.append(row)
                    count += 1
    else:
        log(f"Carryover ({n_existing}) meets or exceeds list size ({list_size}). No new participants pulled.")

    log(f"Generated outreach list with {len(outreach)} participants.")
    validate_and_backup(master_csv_path, C.get('BACKUP_DIR', 'backups'))
    save_csv(rows, fieldnames, master_csv_path)
    
    outreach_path = os.path.join(C.get('OUTPUT_DIR', 'outputs'), f"outreach_{today.strftime('%Y%m%d')}.csv")
    save_csv(outreach, outreach_fieldnames, outreach_path)
    
    # 6. Reporting
    log("\n--- CURRENT STATUS SUMMARY ---")
    weights = {f'S{i}': C[f'S{i}_WEIGHT'] for i in range(1, 6)}
    for s in weights.keys():
        s_rows = [r for r in rows if r['stratum'] == s]
        invited = [r for r in s_rows if r['status'] != 'Not Invited']
        comp = [r for r in invited if r['status'] == 'Completed']
        yield_rate = (len(comp)/len(invited)*100) if invited else 0
        log(f"{s}: Invited: {len(invited)} | Completed: {len(comp)} | Yield: {yield_rate:.1f}%")

if __name__ == "__main__":
    main()
