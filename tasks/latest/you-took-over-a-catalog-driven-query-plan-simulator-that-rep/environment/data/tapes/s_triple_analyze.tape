init vis=1
load table=0 rows=500 distinct=50 buckets=4 b0=125 b1=250 b2=375 b3=500
load table=1 rows=500 distinct=50 buckets=4 b0=125 b1=250 b2=375 b3=500
analyze table=0 rows=800 distinct=80
analyze table=1 rows=700 distinct=70
pause
analyze table=0 rows=1100 distinct=110
resume
query fp=eps partial=0
