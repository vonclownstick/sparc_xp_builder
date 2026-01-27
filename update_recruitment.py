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

def get_yield(rows, stratum, site=None, constants=None):
    """
    Get yield for a stratum.

    Priority:
    1. Calculated from historical data (if any invites exist for this stratum)
    2. Site-specific default (e.g., MGB_S1_YIELD=0.15)
    3. Generic stratum default (e.g., S1_YIELD=0.20)
    4. Hard-coded default of 0.1
    """
    # First, try to calculate from historical data
    s_rows = [r for r in rows if r['stratum'] == stratum]
    invited = [r for r in s_rows if r['status'] != 'Not Invited']
    if invited:
        completed = [r for r in invited if r['status'] == 'Completed']
        return max(len(completed) / len(invited), 0.01)  # Avoid division by zero

    # No historical data - fall back to configured defaults
    if constants and site:
        site_key = f'{site}_{stratum}_YIELD'
        if site_key in constants:
            return float(constants[site_key])

    if constants:
        generic_key = f'{stratum}_YIELD'
        if generic_key in constants:
            return float(constants[generic_key])

    return 0.1  # Hard-coded default if nothing else specified

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--visits", type=int, required=True)
    parser.add_argument("--prior_list", type=str)
    parser.add_argument("--allow-single-site", action="store_true",
                        help="Allow running with only one site's master file present")
    args = parser.parse_args()

    C = get_constants()
    output_dir = C.get('OUTPUT_DIR', 'study_data/outputs')
    backup_dir = C.get('BACKUP_DIR', 'study_data/backups')
    log_dir = C.get('LOG_DIR', 'study_data/logs')

    mgb_path = os.path.join(output_dir, 'parsed_mgb_master_list.csv')
    vumc_path = os.path.join(output_dir, 'parsed_vumc_master_list.csv')

    mgb_exists = os.path.exists(mgb_path)
    vumc_exists = os.path.exists(vumc_path)

    if not mgb_exists and not vumc_exists:
        print("Error: No master lists found. Run update_master.py for at least one site first.")
        return

    if not (mgb_exists and vumc_exists):
        missing_site = "MGB" if not mgb_exists else "VUMC"
        present_site = "VUMC" if not mgb_exists else "MGB"
        if not args.allow_single_site:
            print(f"Warning: Only {present_site} master list found. {missing_site} master list is missing.")
            print("Use --allow-single-site to proceed with a single site.")
            return
        else:
            print(f"Note: Running with {present_site} only (--allow-single-site enabled).")

    mgb_rows = []
    vumc_rows = []
    if mgb_exists:
        with open(mgb_path, 'r') as f:
            mgb_rows = list(csv.DictReader(f))
    if vumc_exists:
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
            
            # Create maps for quick lookup of updates
            # We update status, letter1_date, letter2_date
            prior_map = {r['offspring_MRN']: r for r in prior_rows}
            
            def update_rows(rows, p_map):
                for r in rows:
                    mrn = r['offspring_MRN']
                    if mrn in p_map:
                        p_row = p_map[mrn]
                        if 'status' in p_row and p_row['status']:
                            r['status'] = p_row['status']
                        if 'letter1_date' in p_row:
                            r['letter1_date'] = p_row['letter1_date']
                        if 'letter2_date' in p_row:
                            r['letter2_date'] = p_row['letter2_date']

            update_rows(mgb_rows, prior_map)
            update_rows(vumc_rows, prior_map)

            # Save updated master lists
            if mgb_rows:
                save_csv(mgb_rows, list(mgb_rows[0].keys()), mgb_path)
            if vumc_rows:
                save_csv(vumc_rows, list(vumc_rows[0].keys()), vumc_path)
        else:
            print(f"Error: Prior list {args.prior_list} not found.")
            return

    # NOTE: We do NOT carry over holdovers. 
    total_needed = args.visits
    print(f"Total target (Fresh Invites): {total_needed}")

    # Determine site split (MGB vs VUMC) with exact rounding
    mgb_ratio = C.get('MGB_RATIO', 0.6667)

    # Build site configs based on available data
    site_configs = []
    if mgb_rows and vumc_rows:
        # Both sites available - use normal ratio
        mgb_target = int(total_needed * mgb_ratio + 0.5) # Round nearest
        vumc_target = total_needed - mgb_target
        site_configs = [
            {'site': 'MGB', 'rows': mgb_rows, 'target': mgb_target},
            {'site': 'VUMC', 'rows': vumc_rows, 'target': vumc_target}
        ]
    elif mgb_rows:
        # Only MGB available
        site_configs = [{'site': 'MGB', 'rows': mgb_rows, 'target': total_needed}]
    elif vumc_rows:
        # Only VUMC available
        site_configs = [{'site': 'VUMC', 'rows': vumc_rows, 'target': total_needed}]

    new_selections = []
    strata = [f'S{i}' for i in range(1, 7)] # S1 to S6
    weights = {s: C.get(f'{s}_WEIGHT', 0.1) for s in strata}

    log_messages = []
    log_messages.append(f"Recruitment Update - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    for config in site_configs:
        site = config['site']
        rows = config['rows']
        site_new_needed = config['target']
        
        log_messages.append(f"\nSite: {site} (Target New: {site_new_needed})")

        # Calculate yield per stratum (uses site-specific overrides from CONSTANTS if available)
        yields = {s: get_yield(rows, s, site=site, constants=C) for s in strata}
        
        # Adjust weights based on yield: W_s' = W_s / Yield_s
        adjusted_weights = {s: weights[s] / yields[s] for s in strata}
        total_adj_w = sum(adjusted_weights.values())
        normalized_weights = {s: adjusted_weights[s] / total_adj_w for s in strata}
        
        # Largest Remainder Method for Allocation
        float_targets = {s: site_new_needed * normalized_weights[s] for s in strata}
        floor_targets = {s: int(v) for s, v in float_targets.items()}
        remainder = site_new_needed - sum(floor_targets.values())
        
        # Sort by fractional part descending
        fractional_parts = {s: v - int(v) for s, v in float_targets.items()}
        sorted_strata = sorted(fractional_parts.keys(), key=lambda k: fractional_parts[k], reverse=True)
        
        # Distribute remainder
        for i in range(remainder):
            floor_targets[sorted_strata[i]] += 1
            
        # Select participants
        for s in strata:
            s_target = floor_targets[s]
            log_messages.append(f"  {s}: Yield={yields[s]:.2f}, Target Invites={s_target}")
            
            eligible_rows = [r for r in rows if r['stratum'] == s and r['status'] == 'Not Invited' and r['eligible'] == '1']
            
            selected = []
            if len(eligible_rows) <= s_target:
                selected = eligible_rows
            else:
                selected = random.sample(eligible_rows, s_target)
            
            for r in selected:
                r['status'] = 'Pending'
                r['last_contact_date'] = datetime.now().strftime('%Y-%m-%d')
                r['date_added_to_recruitment'] = datetime.now().strftime('%Y-%m-%d')
                r['letter1_date'] = '' # Initialize blank
                r['letter2_date'] = '' # Initialize blank
                new_selections.append(r)
            
            log_messages.append(f"    Added: {len(selected)}")

    # Update Master Lists with new Pending status
    if mgb_rows:
        save_csv(mgb_rows, list(mgb_rows[0].keys()), mgb_path)
    if vumc_rows:
        save_csv(vumc_rows, list(vumc_rows[0].keys()), vumc_path)

    random.shuffle(new_selections)
    final_list = new_selections 

    # Output CSV
    if final_list:
        fieldnames = [f for f in final_list[0].keys() if f not in ['model_score', 'model_pctile']]
        # Ensure new columns are in output
        for f in ['date_added_to_recruitment', 'letter1_date', 'letter2_date']:
            if f not in fieldnames: fieldnames.append(f)
        
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
