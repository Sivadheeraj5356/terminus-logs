init vis=1
load table=0 rows=500 distinct=50 buckets=4 b0=125 b1=250 b2=375 b3=500
load table=1 rows=2200 distinct=220 buckets=4 b0=550 b1=1100 b2=1650 b3=2200
analyze table=0 rows=1100 distinct=110
pause
analyze table=0 rows=1800 distinct=180
resume
query fp=eflip partial=0
