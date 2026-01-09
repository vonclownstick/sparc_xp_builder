import csv
import random
import os
import shutil
import sys
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
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(data)

def get_yield(rows, stratum):
    s_rows = [r for r in rows if r['stratum'] == stratum]
    invited = [r for r in s_rows if r['status'] != 'Not Invited']
    if not invited:
        return 0.1 # Default yield if none invited yet
    completed = [r for r in invited if r['status'] == 'Completed']
    return max(len(completed) / len(invited), 0.01) # Avoid division by zero

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--visits", type=int, required=True)
    parser.add_argument("--prior_list", type=str)
    args = parser.parse_args()

    C = get_constants()
    output_dir = C.get('OUTPUT_DIR', 'study_data/outputs')
    backup_dir = C.get('BACKUP_DIR', 'study_data/backups')
    log_dir = C.get('LOG_DIR', 'study_data/logs')

    mgb_path = os.path.join(output_dir, 'parsed_mgb_master_list.csv')
    vumc_path = os.path.join(output_dir, 'parsed_vumc_master_list.csv')

    if not os.path.exists(mgb_path) or not os.path.exists(vumc_path):
        print("Error: Master lists not found. Run update_master.py for both sites first.")
        return

    with open(mgb_path, 'r') as f:
        mgb_rows = list(csv.DictReader(f))
    with open(vumc_path, 'r') as f:
        vumc_rows = list(csv.DictReader(f))

    # Handle Prior List
    if not args.prior_list:
        ans = input("There is no prior list provided, do you want to proceed? [Y/N]: ")
        if ans.lower() != 'y':
            sys.exit()
    else:
        if os.path.exists(args.prior_list):
            with open(args.prior_list, 'r') as f:
                prior_rows = list(csv.DictReader(f))
            
            # Create maps for quick lookup
            prior_map = {r['offspring_MRN']: r['status'] for r in prior_rows}
            
            # Update master lists
            for r in mgb_rows:
                if r['offspring_MRN'] in prior_map:
                    r['status'] = prior_map[r['offspring_MRN']]
            for r in vumc_rows:
                if r['offspring_MRN'] in prior_map:
                    r['status'] = prior_map[r['offspring_MRN']]
            
            # Save updated master lists
            save_csv(mgb_rows, list(mgb_rows[0].keys()), mgb_path)
            save_csv(vumc_rows, list(vumc_rows[0].keys()), vumc_path)
        else:
            print(f"Error: Prior list {args.prior_list} not found.")
            return

    # NOTE: We do NOT carry over holdovers. 
    # The new list is purely fresh invites to meet the target capacity.
    # Previously invited people are excluded because their status is != 'Not Invited'.
    
    total_needed = args.visits
    print(f"Total target (Fresh Invites): {total_needed}")

    # Calculate Yields and Stratum Distribution for New Invites
    site_configs = [
        {'site': 'MGB', 'rows': mgb_rows, 'ratio': C.get('MGB_RATIO', 0.6667)},
        {'site': 'VUMC', 'rows': vumc_rows, 'ratio': C.get('VUMC_RATIO', 0.3333)}
    ]

    new_selections = []
    strata = [f'S{i}' for i in range(1, 7)] # S1 to S6
    weights = {s: C.get(f'{s}_WEIGHT', 0.1) for s in strata}

    log_messages = []
    log_messages.append(f"Recruitment Update - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    for config in site_configs:
        site = config['site']
        rows = config['rows']
        site_ratio = config['ratio']
        
        site_new_needed = int(total_needed * site_ratio)
        log_messages.append(f"\nSite: {site} (Target New: {site_new_needed})")
        
        # Calculate yield per stratum
        yields = {s: get_yield(rows, s) for s in strata}
        
        # Adjust weights based on yield: W_s' = W_s / Yield_s
        adjusted_weights = {s: weights[s] / yields[s] for s in strata}
        total_adj_w = sum(adjusted_weights.values())
        normalized_weights = {s: adjusted_weights[s] / total_adj_w for s in strata}
        
        for s in strata:
            s_new_needed = int(site_new_needed * normalized_weights[s])
            log_messages.append(f"  {s}: Yield={yields[s]:.2f}, Target Invites={s_new_needed}")
            
            eligible_rows = [r for r in rows if r['stratum'] == s and r['status'] == 'Not Invited' and r['eligible'] == '1']
            
            selected = []
            if len(eligible_rows) <= s_new_needed:
                selected = eligible_rows
            else:
                selected = random.sample(eligible_rows, s_new_needed)
            
            for r in selected:
                r['status'] = 'Pending'
                r['last_contact_date'] = datetime.now().strftime('%Y-%m-%d')
                r['date_added_to_recruitment'] = datetime.now().strftime('%Y-%m-%d')
                new_selections.append(r)
            
            log_messages.append(f"    Added: {len(selected)}")

    # Update Master Lists with new Pending status
    save_csv(mgb_rows, list(mgb_rows[0].keys()), mgb_path)
    save_csv(vumc_rows, list(vumc_rows[0].keys()), vumc_path)

    random.shuffle(new_selections)
    final_list = new_selections # No holdovers

    # Output CSV
    if final_list:
        fieldnames = [f for f in final_list[0].keys() if f not in ['model_score', 'model_pctile']]
        if 'date_added_to_recruitment' not in fieldnames: fieldnames.append('date_added_to_recruitment')
        
        today_ts = datetime.now().strftime('%Y%m%d')
        output_path = os.path.join(output_dir, f"recruitment_{today_ts}.csv")
        save_csv(final_list, fieldnames, output_path)
        print(f"Saved recruitment list to {output_path}")
        
        # Backup
        if not os.path.exists(backup_dir): os.makedirs(backup_dir)
        shutil.copy(output_path, os.path.join(backup_dir, f"recruitment_{today_ts}_{datetime.now().strftime('%H%M')}.csv"))

    # Logging
    log_content = "\n".join(log_messages)
    print(log_content)
    if not os.path.exists(log_dir): os.makedirs(log_dir)
    with open(os.path.join(log_dir, f"recruitment_{datetime.now().strftime('%Y%m%d')}.log"), 'a') as f:
        f.write(log_content + "\n")

if __name__ == "__main__":
    main()