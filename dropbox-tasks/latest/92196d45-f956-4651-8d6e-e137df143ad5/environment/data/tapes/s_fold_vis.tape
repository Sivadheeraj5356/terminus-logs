init vis=4
load table=0 rows=1050 distinct=105 buckets=4 b0=262 b1=525 b2=787 b3=1050
load table=1 rows=280 distinct=28 buckets=4 b0=70 b1=140 b2=210 b3=280
pause
vis gen=4
resume
query fp=fold partial=1
