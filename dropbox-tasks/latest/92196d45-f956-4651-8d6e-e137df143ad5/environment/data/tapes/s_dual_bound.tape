init vis=1
load table=0 rows=1150 distinct=115 buckets=4 b0=287 b1=575 b2=862 b3=1150
load table=1 rows=420 distinct=42 buckets=4 b0=105 b1=210 b2=315 b3=420
analyze table=0 rows=1500 distinct=150
pause
resume
query fp=dbnd partial=0
