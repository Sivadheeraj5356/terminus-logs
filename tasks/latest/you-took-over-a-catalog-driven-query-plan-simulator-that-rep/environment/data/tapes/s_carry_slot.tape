init vis=1
load table=0 rows=850 distinct=85 buckets=4 b0=212 b1=425 b2=637 b3=850
load table=1 rows=1600 distinct=160 buckets=4 b0=400 b1=800 b2=1200 b3=1600
analyze table=0 rows=1200 distinct=120
pause
analyze table=0 rows=1600 distinct=160
resume
query fp=slot partial=0
