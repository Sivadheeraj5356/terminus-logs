init vis=1
load table=0 rows=600 distinct=60 buckets=4 b0=60 b1=180 b2=360 b3=600
load table=1 rows=3000 distinct=300 buckets=4 b0=300 b1=900 b2=1800 b3=3000
analyze table=0 rows=1200 distinct=120
pause
analyze table=0 rows=1800 distinct=180
resume
query fp=tau partial=0
