import csv
import os

def create_mgb_toy():
    data = [
        ['mother_MRN','mother_last','mother_first','mother_phone','offspring_MRN','offspring_last','offspring_first','offspring_sex','offspring_DOB','model_score','model_pctile'],
        ['MOM1','Smith','Jane','555-0101','CHILD1','Smith','Alice','F','2021-02-01','0.99','99'], # S1
        ['MOM2','Jones','Mary','555-0102','CHILD2','Jones','Bob','M','2021-06-01','0.92','92'], # S2
        ['MOM3','Brown','Lucy','555-0103','CHILD3','Brown','Charlie','M','2021-05-15','0.85','85'], # S3
        ['MOM4','White','Emma','555-0104','CHILD4','White','David','M','2021-12-10','0.75','75'], # S4 (was 75)
        ['MOM5','Green','Sarah','555-0105','CHILD5','Green','Eve','F','2021-08-20','0.55','55'], # S4 (was 65)
        ['MOM6','Black','Anna','555-0106','CHILD6','Black','Frank','M','2021-09-01','0.45','45'], # S5
        ['MOM7','Grey','Kate','555-0107','CHILD7','Grey','George','M','2021-10-01','0.15','15'], # S5
        ['MOM8','Gold','Rose','555-0108','CHILD8','Gold','Harry','M','2021-01-10','0.05','5'], # S6
    ]
    with open('mgb_master_list.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(data)

def create_vumc_toy():
    data = [
        ['mother_MRN','mother_last','mother_first','mother_phone','offspring_MRN','offspring_last','offspring_first','offspring_sex','offspring_DOB','model_score','model_pctile'],
        ['MOM_V1','Taylor','Rose','555-0201','CHILD_V1','Taylor','Sam','M','2021-02-02','0.96','96'], # S1
        ['MOM_V2','Miller','Grace','555-0202','CHILD_V2','Miller','Tom','M','2021-06-20','0.65','65'], # S4
        ['MOM_V3','Davis','Kate','555-0203','CHILD_V3','Davis','Harry','M','2021-07-01','0.02','2'], # S6
    ]
    with open('vumc_master_list.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(data)

create_mgb_toy()
create_vumc_toy()
print("Created toy data files.")