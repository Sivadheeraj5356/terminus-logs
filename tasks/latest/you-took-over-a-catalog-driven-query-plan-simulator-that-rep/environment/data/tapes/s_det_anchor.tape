init vis=1
load table=0 rows=640 distinct=64 buckets=4 b0=160 b1=320 b2=480 b3=640
load table=1 rows=360 distinct=36 buckets=4 b0=90 b1=180 b2=270 b3=360
analyze table=0 rows=700 distinct=70
query fp=theta partial=0
