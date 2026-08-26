init vis=1
load table=0 rows=640 distinct=64 buckets=4 b0=160 b1=320 b2=480 b3=640
load table=1 rows=1600 distinct=160 buckets=4 b0=400 b1=800 b2=1200 b3=1600
analyze table=0 rows=900 distinct=90
analyze table=1 rows=1800 distinct=180
pause
analyze table=0 rows=1200 distinct=120
analyze table=1 rows=2100 distinct=210
resume
query fp=theta partial=0
