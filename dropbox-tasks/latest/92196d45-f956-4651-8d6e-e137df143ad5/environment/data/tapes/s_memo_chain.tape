init vis=1
load table=0 rows=900 distinct=90 buckets=4 b0=225 b1=450 b2=675 b3=900
load table=1 rows=900 distinct=90 buckets=4 b0=225 b1=450 b2=675 b3=900
analyze table=0 rows=1500 distinct=150
query fp=zeta partial=0
pause
analyze table=1 rows=1500 distinct=150
resume
query fp=zeta partial=0
