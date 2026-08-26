init vis=3
load table=0 rows=600 distinct=60 buckets=4 b0=150 b1=300 b2=450 b3=600
load table=1 rows=450 distinct=45 buckets=4 b0=112 b1=225 b2=337 b3=450
pause
vis gen=3
resume
query fp=vsnap partial=1
