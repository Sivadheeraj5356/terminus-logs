#!/bin/bash
minizinc --solver chuffed -t 300000 /app/model.mzn /app/instance.dzn
