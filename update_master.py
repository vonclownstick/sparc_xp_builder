import csv
import random
import os
import shutil
import sys
import hashlib
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

def trim_by_stratum(rows, target_n, constants):
    """Downsample rows to target_n using configured stratum weights."""
    # Only consider eligible rows for trimming
    eligible_rows = [r for r in rows if r.get('eligible') == '1']
    ineligible_rows = [r for r in rows if r.get('eligible') != '1']

    if len(eligible_rows) <= target_n:
        print(f"Note: Only {len(eligible_rows)} eligible rows available, no trimming needed.")
        return rows

    # Get configured weights from CONSTANTS
    strata = ['S1', 'S2', 'S3', 'S4', 'S5', 'S6']
    weights = {s: constants.get(f'{s}_WEIGHT', 0.1) for s in strata}

    # Normalize weights to sum to 1.0
    total_weight = sum(weights.values())
    weights = {s: w / total_weight for s, w in weights.items()}

    # Count available rows per stratum
    strata_available = {}
    for r in eligible_rows:
        s = r.get('stratum', 'S6')
        strata_available[s] = strata_available.get(s, 0) + 1

    # Calculate target counts per stratum using configured weights
    strata_targets = {s: weights[s] * target_n for s in strata}

    # Use largest remainder method for integer allocation
    floor_targets = {s: int(v) for s, v in strata_targets.items()}
    remainder = target_n - sum(floor_targets.values())
    fractional_parts = {s: v - int(v) for s, v in strata_targets.items()}
    sorted_strata = sorted(fractional_parts.keys(), key=lambda k: fractional_parts[k], reverse=True)
    for i in range(remainder):
        floor_targets[sorted_strata[i]] += 1

    # Sample from each stratum (cap at available if needed)
    sampled_rows = []
    actual_total = 0
    shortfall = 0
    for s in strata:
        s_rows = [r for r in eligible_rows if r.get('stratum') == s]
        s_target = floor_targets.get(s, 0)
        available = len(s_rows)

        if available < s_target:
            # Not enough in this stratum - take all available
            sampled_rows.extend(s_rows)
            actual_total += available
            shortfall += s_target - available
        else:
            sampled_rows.extend(random.sample(s_rows, s_target))
            actual_total += s_target

    # If there was a shortfall, try to fill from other strata proportionally
    if shortfall > 0:
        remaining_eligible = [r for r in eligible_rows if r not in sampled_rows]
        if remaining_eligible:
            fill_count = min(shortfall, len(remaining_eligible))
            sampled_rows.extend(random.sample(remaining_eligible, fill_count))
            print(f"  Note: {shortfall} shortfall in target strata, filled {fill_count} from others")

    print(f"Trimmed from {len(eligible_rows)} to {len(sampled_rows)} eligible rows (target: {target_n})")
    print(f"Target weights from CONSTANTS.txt:")
    for s in strata:
        orig = strata_available.get(s, 0)
        final = len([r for r in sampled_rows if r.get('stratum') == s])
        target_pct = weights[s] * 100
        actual_pct = final / len(sampled_rows) * 100 if sampled_rows else 0
        print(f"  {s}: {orig} -> {final} (target: {target_pct:.0f}%, actual: {actual_pct:.1f}%)")

    # Return sampled eligible + all ineligible (ineligible are kept for record but excluded from recruitment)
    return sampled_rows + ineligible_rows


def main():
    parser = argparse.ArgumentParser(description="Update master list from raw site data")
    parser.add_argument("input_file", help="Input CSV file (must start with 'mgb_' or 'vumc_')")
    parser.add_argument("--trim", type=int, metavar="N",
                        help="After excluding ineligible, downsample to N rows while maintaining stratum distribution")
    args = parser.parse_args()

    input_file = args.input_file
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

    # Apply trim if requested
    if args.trim:
        final_rows = trim_by_stratum(final_rows, args.trim, C)
        # Re-run maternal flags after trimming since some mothers may have lost offspring
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
