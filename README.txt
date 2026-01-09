# ASD Recruitment Protocol (v2.0)

1. Initial Ingest: python ingest_initial.py raw_data.csv master_list.csv
2. Monthly Update: python monthly.py master_list.csv [new_refresh.csv]
3. CONSORT Diagram: python consort_generator.py master_list.csv

Features:
- Generic Python (no dependencies)
- Offspring deduplication
- Maternal relationship flagging (multiple children / previous completion)
- Automated validated backups
