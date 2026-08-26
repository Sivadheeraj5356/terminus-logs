init vis=1
load table=0 rows=1100 distinct=110 buckets=4 b0=275 b1=550 b2=825 b3=1100
load table=1 rows=1100 distinct=110 buckets=4 b0=275 b1=550 b2=825 b3=1100
analyze table=0 rows=2200 distinct=220
query fp=pi partial=0
pause
analyze table=1 rows=2200 distinct=220
resume
query fp=pi partial=0
