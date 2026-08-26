init vis=1
load table=0 rows=2000 distinct=200 buckets=4 b0=100 b1=400 b2=900 b3=2000
load table=1 rows=350 distinct=35 buckets=4 b0=87 b1=175 b2=262 b3=350
analyze table=0 rows=2400 distinct=240
pause
analyze table=1 rows=700 distinct=70
resume
query fp=omega partial=0
