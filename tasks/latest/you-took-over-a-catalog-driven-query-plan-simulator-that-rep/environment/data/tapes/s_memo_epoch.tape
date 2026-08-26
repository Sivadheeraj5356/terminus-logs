init vis=1
load table=0 rows=900 distinct=90 buckets=4 b0=225 b1=450 b2=675 b3=900
load table=1 rows=650 distinct=65 buckets=4 b0=162 b1=325 b2=487 b3=650
query fp=epoch0 partial=0
pause
resume
analyze table=1 rows=900 distinct=90
query fp=epoch0 partial=0
