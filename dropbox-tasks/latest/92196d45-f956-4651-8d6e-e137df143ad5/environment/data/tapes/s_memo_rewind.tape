init vis=1
load table=0 rows=1000 distinct=100 buckets=4 b0=250 b1=500 b2=750 b3=1000
load table=1 rows=1000 distinct=100 buckets=4 b0=250 b1=500 b2=750 b3=1000
analyze table=0 rows=2000 distinct=200
query fp=mu partial=0
analyze table=1 rows=2000 distinct=200
pause
resume
query fp=mu partial=0
