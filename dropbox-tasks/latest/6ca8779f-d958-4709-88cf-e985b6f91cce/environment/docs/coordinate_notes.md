# Coordinate notes

Cells are stored as `[x, y]` with origin at the north-west corner of the map.
Neighbor offsets used by movement are:

```
[x+1,y], [x-1,y], [x,y+1], [x,y-1], [x+1,y-1], [x-1,y+1]
```

Distance uses cube conversion `(x, y, -x-y)` and `max(|dx|,|dy|,|dz|)`.
Line sampling for LOS walks an inclusive interpolated path with the same distance
as the step count.
