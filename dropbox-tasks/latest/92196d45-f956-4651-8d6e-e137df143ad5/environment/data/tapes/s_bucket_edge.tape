init vis=1
load table=0 rows=300 distinct=30 buckets=4 b0=75 b1=150 b2=225 b3=300
load table=1 rows=6000 distinct=600 buckets=4 b0=1200 b1=2400 b2=3600 b3=6000
analyze table=0 rows=600 distinct=60
pause
resume
load table=0 rows=600 distinct=60 buckets=8 b0=75 b1=150 b2=225 b3=300 b4=375 b5=450 b6=525 b7=600
query fp=theta partial=0
