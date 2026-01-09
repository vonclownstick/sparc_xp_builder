import csv

# 1. BASELINE DATA (Initial Start)
baseline = [
    ['maternal_MRN', 'offspring_MRN', 'offspring_DOB', 'stratum'],
    ['MOM_001', 'CHILD_A', '2021-06-15', 'S1'],  # Twin 1 (Eligible)
    ['MOM_001', 'CHILD_B', '2021-06-15', 'S1'],  # Twin 2 (Eligible)
    ['MOM_002', 'CHILD_C', '2021-02-01', 'S2'],  # Eligible
    ['MOM_003', 'CHILD_D', '2020-01-10', 'S3'],  # Too old (>5)
    ['MOM_004', 'CHILD_E', '2021-11-20', 'S1'],  # Eligible
    ['MOM_005', 'CHILD_F', '2022-03-01', 'S4'],  # Too young (<4)
    ['MOM_001', 'CHILD_A', '2021-06-15', 'S1'],  # INTERNAL DUPLICATE (Should be skipped)
]

# 2. QUARTERLY REFRESH (New data 3 months later)
refresh = [
    ['maternal_MRN', 'offspring_MRN', 'offspring_DOB', 'stratum'],
    ['MOM_006', 'CHILD_G', '2022-01-05', 'S1'],  # New child
    ['MOM_002', 'CHILD_C', '2021-02-01', 'S2'],  # DUPLICATE of existing Master (Should be skipped)
    ['MOM_007', 'CHILD_H', '2021-08-12', 'S5'],  # New child
]

def write_toy_csv(filename, data):
    import os
    path = os.path.join('study_data/inputs', filename)
    with open(path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(data)
    print(f"Created {path}")

write_toy_csv('baseline_data.csv', baseline)
write_toy_csv('quarterly_refresh.csv', refresh)