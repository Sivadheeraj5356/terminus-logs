init vis=1
load table=0 rows=640 distinct=64 buckets=4 b0=160 b1=320 b2=480 b3=640
load table=1 rows=1600 distinct=160 buckets=4 b0=320 b1=640 b2=960 b3=1600
pause
analyze table=0 rows=1280 distinct=128
analyze table=1 rows=2000 distinct=200
resume
query fp=psi2 partial=0
