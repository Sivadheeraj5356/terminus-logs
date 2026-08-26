init vis=1
load table=0 rows=400 distinct=40 buckets=4 b0=50 b1=120 b2=260 b3=400
load table=1 rows=2000 distinct=200 buckets=4 b0=400 b1=900 b2=1500 b3=2000
analyze table=0 rows=600 distinct=60
pause
analyze table=1 rows=2200 distinct=220
resume
query fp=delta partial=0
