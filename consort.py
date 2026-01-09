import os
import re
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

def parse_new_log(content):
    runs = []
    # Split by "Recruitment Update"
    parts = content.split("Recruitment Update - ")
    for part in parts[1:]:
        lines = part.strip().split('\n')
        date_str = lines[0].strip()
        
        current_site = None
        run_data = {'date': date_str, 'stats': {}}
        
        for line in lines[1:]:
            site_match = re.match(r"Site: (\w+)", line)
            if site_match:
                current_site = site_match.group(1)
                run_data['stats'][current_site] = {}
                continue
            
            stratum_match = re.search(r"(S\d): Yield=([\d.]+), Target Invites=(\d+)", line)
            if stratum_match and current_site:
                s = stratum_match.group(1)
                y = stratum_match.group(2)
                ti = stratum_match.group(3)
                run_data['stats'][current_site][s] = {'yield': y, 'target': ti}
                
            added_match = re.search(r"Added: (\d+)", line)
            if added_match and current_site and s:
                run_data['stats'][current_site][s]['added'] = added_match.group(1)
        
        runs.append(run_data)
    return runs

def main():
    C = get_constants()
    log_dir = C.get('LOG_DIR', 'study_data/logs')
    
    all_runs = []
    
    if os.path.exists(log_dir):
        for filename in sorted(os.listdir(log_dir)):
            if filename.startswith('recruitment_'):
                with open(os.path.join(log_dir, filename), 'r') as f:
                    content = f.read()
                    all_runs.extend(parse_new_log(content))
    
    if not all_runs:
        print("No recruitment runs found in logs.")
        return

    # Print Table
    print(f"{'Date':<20} | {'Site':<5} | {'Stratum':<7} | {'Yield':<6} | {'Added':<5}")
    print("-" * 55)
    
    for run in all_runs:
        for site, site_data in run['stats'].items():
            for s, s_data in site_data.items():
                y = s_data.get('yield', '0.00')
                a = s_data.get('added', '0')
                print(f"{run['date']:<20} | {site:<5} | {s:<7} | {y:<6} | {a:<5}")

if __name__ == "__main__":
    main()
