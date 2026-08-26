init vis=1
load table=0 rows=780 distinct=78 buckets=4 b0=195 b1=390 b2=585 b3=780
load table=1 rows=620 distinct=62 buckets=4 b0=155 b1=310 b2=465 b3=620
query fp=gring partial=0
pause
analyze table=1 rows=980 distinct=98
resume
analyze table=0 rows=1100 distinct=110
query fp=gring partial=0
