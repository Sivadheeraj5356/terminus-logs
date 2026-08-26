init vis=1
load table=0 rows=350 distinct=35 buckets=4 b0=87 b1=175 b2=262 b3=350
load table=1 rows=5200 distinct=520 buckets=4 b0=1040 b1=2080 b2=3120 b3=5200
analyze table=0 rows=700 distinct=70
pause
resume
load table=0 rows=700 distinct=70 buckets=4 b0=175 b1=350 b2=525 b3=700
query fp=rho2 partial=0
