init vis=1
load table=0 rows=900 distinct=90 buckets=4 b0=225 b1=450 b2=675 b3=900
load table=1 rows=1100 distinct=55 buckets=4 b0=275 b1=550 b2=825 b3=1100
query fp=iota partial=0
pause
analyze table=0 rows=1300 distinct=130
resume
query fp=iota partial=0
