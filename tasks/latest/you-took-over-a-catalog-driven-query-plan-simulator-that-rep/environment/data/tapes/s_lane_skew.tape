init vis=1
load table=0 rows=680 distinct=68 buckets=4 b0=40 b1=180 b2=420 b3=680
load table=1 rows=4200 distinct=420 buckets=4 b0=840 b1=1680 b2=2520 b3=4200
analyze table=0 rows=820 distinct=82
pause
analyze table=1 rows=4600 distinct=460
resume
query fp=lambda partial=0
