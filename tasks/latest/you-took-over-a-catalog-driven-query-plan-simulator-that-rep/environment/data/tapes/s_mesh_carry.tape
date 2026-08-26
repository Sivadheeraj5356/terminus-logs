init vis=1
load table=0 rows=700 distinct=70 buckets=4 b0=175 b1=350 b2=525 b3=700
load table=1 rows=1800 distinct=180 buckets=4 b0=360 b1=720 b2=1080 b3=1800
analyze table=0 rows=1400 distinct=140
pause
analyze table=0 rows=2100 distinct=210
resume
query fp=kappa partial=0
