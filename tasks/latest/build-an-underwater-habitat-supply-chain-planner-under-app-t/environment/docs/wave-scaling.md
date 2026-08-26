# wave scaling

Transfer duration scales by wave_m on each cargo row.

Formula:

```
transfer_min = base_min * wave_m
```

Round transfer_min to six decimal places in tide snapshot acts.

Example: base_min 6 with wave_m 2.2 yields transfer_min 13.2.
