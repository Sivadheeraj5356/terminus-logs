init vis=1
load table=0 rows=500 distinct=50 buckets=4 b0=125 b1=250 b2=375 b3=500
load table=1 rows=2400 distinct=240 buckets=4 b0=480 b1=960 b2=1440 b3=2400
analyze table=0 rows=900 distinct=90
analyze table=1 rows=3000 distinct=300
pause
analyze table=0 rows=1200 distinct=120
resume
query fp=upsilon partial=0
