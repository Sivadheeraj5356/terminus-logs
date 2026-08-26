# Output format

Print exactly two lines (kit 1 then kit 2):

```
q1=[v_1, ..., v_T]
q2=[w_1, ..., w_T]
```

Use MiniZinc `show` on the week-indexed purchase arrays. Solve with
`minizinc --solver chuffed /app/model.mzn /app/instance.dzn`. The model is re-solved on
hidden instances. Any purchase plan that meets demand and reserves at the least total
cost is accepted.

