init vis=3
load table=0 rows=720 distinct=72 buckets=4 b0=180 b1=360 b2=540 b3=720
load table=1 rows=510 distinct=51 buckets=4 b0=127 b1=255 b2=382 b3=510
pause
vis gen=3
resume
query fp=vfold partial=1
