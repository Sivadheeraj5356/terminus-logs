init vis=4
load table=0 rows=1100 distinct=110 buckets=4 b0=275 b1=550 b2=825 b3=1100
load table=1 rows=250 distinct=25 buckets=4 b0=62 b1=125 b2=187 b3=250
pause
vis gen=4
resume
query fp=xi partial=1
