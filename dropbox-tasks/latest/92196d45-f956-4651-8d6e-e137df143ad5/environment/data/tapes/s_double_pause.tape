init vis=1
load table=0 rows=500 distinct=50 buckets=4 b0=125 b1=250 b2=375 b3=500
load table=1 rows=800 distinct=80 buckets=4 b0=160 b1=320 b2=480 b3=800
analyze table=0 rows=900 distinct=90
pause
analyze table=1 rows=1200 distinct=120
resume
pause
analyze table=0 rows=1100 distinct=110
resume
query fp=sigma partial=0
