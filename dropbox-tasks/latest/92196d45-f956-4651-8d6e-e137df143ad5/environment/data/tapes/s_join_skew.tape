init vis=1
load table=0 rows=750 distinct=75 buckets=4 b0=75 b1=225 b2=450 b3=750
load table=1 rows=3900 distinct=390 buckets=4 b0=780 b1=1560 b2=2340 b3=3900
analyze table=0 rows=950 distinct=95
pause
analyze table=1 rows=4300 distinct=430
resume
query fp=omega2 partial=0
