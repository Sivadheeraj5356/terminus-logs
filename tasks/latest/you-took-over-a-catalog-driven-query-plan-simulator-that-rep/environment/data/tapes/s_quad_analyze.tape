init vis=1
load table=0 rows=800 distinct=80 buckets=4 b0=200 b1=400 b2=600 b3=800
load table=1 rows=2200 distinct=220 buckets=4 b0=440 b1=880 b2=1320 b3=2200
analyze table=0 rows=1600 distinct=160
analyze table=1 rows=2800 distinct=280
pause
analyze table=0 rows=2000 distinct=200
resume
query fp=phi partial=0
