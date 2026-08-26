init vis=1
load table=0 rows=400 distinct=40 buckets=8 b0=50 b1=100 b2=150 b3=200 b4=250 b5=300 b6=350 b7=400
load table=1 rows=5000 distinct=500 buckets=4 b0=1000 b1=2000 b2=3000 b3=5000
analyze table=0 rows=800 distinct=80
pause
resume
load table=0 rows=800 distinct=80 buckets=4 b0=200 b1=400 b2=600 b3=800
query fp=rho partial=0
