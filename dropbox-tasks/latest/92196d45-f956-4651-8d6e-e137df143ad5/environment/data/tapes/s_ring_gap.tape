init vis=1
load table=0 rows=920 distinct=92 buckets=4 b0=230 b1=460 b2=690 b3=920
load table=1 rows=700 distinct=70 buckets=4 b0=175 b1=350 b2=525 b3=700
query fp=rgap partial=0
pause
analyze table=0 rows=1300 distinct=130
resume
query fp=rgap partial=0
