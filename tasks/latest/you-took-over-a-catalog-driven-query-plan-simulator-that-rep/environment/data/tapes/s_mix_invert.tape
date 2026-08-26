init vis=1
load table=0 rows=950 distinct=95 buckets=4 b0=237 b1=475 b2=712 b3=950
load table=1 rows=1800 distinct=180 buckets=4 b0=450 b1=900 b2=1350 b3=1800
pause
resume
query fp=mix partial=0
