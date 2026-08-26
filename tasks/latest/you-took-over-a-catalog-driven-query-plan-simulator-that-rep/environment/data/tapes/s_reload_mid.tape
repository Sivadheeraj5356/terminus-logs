init vis=1
load table=0 rows=1000 distinct=100 buckets=4 b0=250 b1=500 b2=750 b3=1000
load table=1 rows=800 distinct=50 buckets=4 b0=200 b1=400 b2=600 b3=800
analyze table=0 rows=1500 distinct=150
pause
analyze table=1 rows=1200 distinct=80
resume
query fp=alpha partial=0
