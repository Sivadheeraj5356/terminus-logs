init vis=3
load table=0 rows=1300 distinct=130 buckets=4 b0=325 b1=650 b2=975 b3=1300
load table=1 rows=400 distinct=40 buckets=4 b0=100 b1=200 b2=300 b3=400
pause
vis gen=3
resume
query fp=omicron partial=1
