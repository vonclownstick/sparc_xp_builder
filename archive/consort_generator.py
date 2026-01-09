import csv
import random
import os
import shutil
import sys
from datetime import datetime

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

def main():
    C = get_constants()
    if not C:
        print("Error: CONSTANTS.txt not found.")
        return
        
    master_csv = os.path.join(C.get('OUTPUT_DIR', 'outputs'), 'master_list.csv')
    
    if not os.path.exists(master_csv): 
        print(f"Error: {master_csv} not found.")
        return
        
    with open(master_csv, 'r') as f:
        rows = list(csv.DictReader(f))
    
    total = len(rows)
    eligible = len([r for r in rows if r['eligible'] == '1'])
    invited = len([r for r in rows if r['status'] != 'Not Invited'])
    completed = len([r for r in rows if r['status'] == 'Completed'])
    multi_offspring = len([r for r in rows if r['multiple_offspring'] == 'Yes'])

    diagram = f"""
    CONSORT RECRUITMENT FLOW
    ========================
    Total Base Population: {total}
    (Records with multi-child mothers: {multi_offspring})
              |
              v
    Eligible (Age 4-5): {eligible}
              |
              v
    Total Invited: {invited}
              |
    |---------|---------|---------|
    v                   v         v
[ COMPLETED ]      [ PENDING ] [ DROPPED/AGED ]
(n = {completed})    (n = {len([r for r in rows if r['status'] == 'Pending'])})  (n = {len([r for r in rows if r['status'] == 'Aged Out'])})
    """
    print(diagram)
    
    output_path = os.path.join(C.get('OUTPUT_DIR', 'outputs'), 'CONSORT_DIAGRAM.txt')
    with open(output_path, 'w') as f: f.write(diagram)
    print(f"Saved diagram to {output_path}")

if __name__ == "__main__":
    main()