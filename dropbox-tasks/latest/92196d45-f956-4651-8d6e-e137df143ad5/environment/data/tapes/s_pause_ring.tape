init vis=1
load table=0 rows=880 distinct=88 buckets=4 b0=220 b1=440 b2=660 b3=880
load table=1 rows=540 distinct=54 buckets=4 b0=135 b1=270 b2=405 b3=540
query fp=pring partial=0
pause
analyze table=0 rows=1200 distinct=120
resume
query fp=pring partial=0
