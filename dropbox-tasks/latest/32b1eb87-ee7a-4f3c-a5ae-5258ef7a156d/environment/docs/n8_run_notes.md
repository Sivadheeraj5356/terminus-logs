# w00 baseline warm rows
/app/tools/n2_driver --reset --batch w00

# w01 stamp-early trap graph
/app/tools/n2_driver --batch w01 --fixture r_row_a

# w02 rapid-apply trap graph
/app/tools/n2_driver --batch w02 --fixture r_row_b

# w03 carrier-delay trap graph
/app/tools/n2_driver --batch w03 --fixture r_row_c

# w04 combined replay (continuation fixtures)
/app/tools/n2_driver --batch w04 --fixture r_row_a2
/app/tools/n2_driver --batch w05 --fixture r_row_b2
/app/tools/n2_driver --batch w06 --fixture r_row_c2

# w07 idempotent second pass over continuation graphs
/app/tools/n2_driver --batch w07 --fixture r_row_a3
/app/tools/n2_driver --batch w08 --fixture r_row_b3

# regenerate observations after all batches
/app/tools/w8_emit
