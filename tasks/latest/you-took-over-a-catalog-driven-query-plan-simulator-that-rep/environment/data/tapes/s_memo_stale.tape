init vis=1
load table=0 rows=1000 distinct=100 buckets=4 b0=250 b1=500 b2=750 b3=1000
load table=1 rows=800 distinct=50 buckets=4 b0=200 b1=400 b2=600 b3=800
query fp=beta partial=0
pause
analyze table=0 rows=1400 distinct=140
resume
query fp=beta partial=0
