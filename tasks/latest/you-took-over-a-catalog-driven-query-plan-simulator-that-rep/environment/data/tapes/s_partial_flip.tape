init vis=3
load table=0 rows=1500 distinct=150 buckets=4 b0=375 b1=750 b2=1125 b3=1500
load table=1 rows=200 distinct=20 buckets=4 b0=50 b1=100 b2=150 b3=200
query fp=chi partial=1
pause
vis gen=3
analyze table=0 rows=1800 distinct=180
resume
query fp=chi partial=1
