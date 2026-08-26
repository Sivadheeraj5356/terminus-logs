init vis=1
load table=0 rows=900 distinct=90 buckets=4 b0=225 b1=450 b2=675 b3=900
load table=1 rows=700 distinct=35 buckets=4 b0=175 b1=350 b2=525 b3=700
query fp=base partial=0
