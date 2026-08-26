init vis=1
load table=0 rows=1200 distinct=120 buckets=4 b0=300 b1=600 b2=900 b3=1200
load table=1 rows=300 distinct=15 buckets=4 b0=75 b1=150 b2=225 b3=300
query fp=zeta partial=0
pause
analyze table=1 rows=900 distinct=90
resume
query fp=eta partial=1
