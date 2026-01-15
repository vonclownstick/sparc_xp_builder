import csv
import os
import random

def create_mgb_toy():
    data = [['mother_MRN','mother_last','mother_first','mother_phone','offspring_MRN','offspring_last','offspring_first','offspring_sex','offspring_DOB','model_score','model_pctile']]
    
    # Generate 100 candidates distributed across strata
    for i in range(100):
        pctile = random.uniform(0, 100)
        stratum = 'S6'
        if pctile > 95: stratum = 'S1'
        elif pctile > 90: stratum = 'S2'
        elif pctile > 80: stratum = 'S3'
        elif pctile > 50: stratum = 'S4'
        elif pctile > 10: stratum = 'S5'
        
        data.append([
            f'MOM_M{i}', 'Smith', 'Jane', '555-0101', 
            f'CHILD_M{i}', 'Smith', 'Alice', 'F', 
            '2021-02-01', str(pctile/100), str(pctile)
        ])
        
    with open('mgb_master_list.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(data)

def create_vumc_toy():
    data = [['mother_MRN','mother_last','mother_first','mother_phone','offspring_MRN','offspring_last','offspring_first','offspring_sex','offspring_DOB','model_score','model_pctile']]
    
    # Generate 50 candidates
    for i in range(50):
        pctile = random.uniform(0, 100)
        data.append([
            f'MOM_V{i}', 'Taylor', 'Rose', '555-0201', 
            f'CHILD_V{i}', 'Taylor', 'Sam', 'M', 
            '2021-02-02', str(pctile/100), str(pctile)
        ])

    with open('vumc_master_list.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(data)

create_mgb_toy()
create_vumc_toy()
print("Created toy data files with ~150 candidates.")
