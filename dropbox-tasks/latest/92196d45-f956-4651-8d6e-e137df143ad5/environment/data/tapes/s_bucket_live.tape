init vis=1
load table=0 rows=1000 distinct=100 buckets=4 b0=250 b1=500 b2=750 b3=1000
load table=1 rows=450 distinct=45 buckets=4 b0=112 b1=225 b2=337 b3=450
analyze table=0 rows=1600 distinct=160
pause
resume
query fp=blive partial=0
