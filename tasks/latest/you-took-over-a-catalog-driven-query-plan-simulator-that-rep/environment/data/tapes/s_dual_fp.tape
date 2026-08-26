init vis=1
load table=0 rows=720 distinct=72 buckets=4 b0=180 b1=360 b2=540 b3=720
load table=1 rows=480 distinct=48 buckets=4 b0=120 b1=240 b2=360 b3=480
query fp=phi partial=0
pause
analyze table=0 rows=960 distinct=96
analyze table=1 rows=720 distinct=72
resume
query fp=psi partial=0
