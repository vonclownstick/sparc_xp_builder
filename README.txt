# ASD Recruitment Protocol (v2.0)

1. Initial Ingest: python ingest_initial.py raw_data.csv master_list.csv
2. Monthly Update: python monthly.py master_list.csv [new_refresh.csv]
3. CONSORT Diagram: python consort_generator.py master_list.csv

Key elements:
- Weighting by stratum 
- Re-weighting based on yield per stratum w prior invites
- Offspring deduplication
- Maternal relationship flagging (multiple children / previous completion)
- Automated validated backups
- Hashing to minimize risk of sorting

TO DO:
- Clarify how output list will be used by CRC's - and in particular whether to upload edited list each time we make a new version
- Clarify how to implement 7d and 30d re-invitations. Leaning towards doing that with same recruitment list (ie just prior to running next round)
