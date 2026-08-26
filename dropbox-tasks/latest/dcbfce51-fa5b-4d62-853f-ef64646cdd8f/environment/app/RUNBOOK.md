# Climate model CF time-axis engine

The editable `cfaxis` package is installed during image build. Changes under `/app/cfaxis` are visible to `/app/bin/climconvert` without reinstalling.

```bash
export TZ=UTC
export PATH="/app/bin:/usr/local/bin:${PATH}"
python3 -c 'import cfaxis'
/app/bin/climconvert --help
```

Calendar arithmetic: `/app/docs/time-contract.md`.  
Multi-member CF axis rules: `/app/docs/CLIMATE_AXIS.md` (`/app/data/climate-axis-manifest.toml`).

## Example commands

```bash
export TZ=UTC
/app/bin/climconvert validate --in /data/samples/gregorian_monthly.ccf
/app/bin/climconvert convert --in /data/samples/gregorian_monthly.ccf --out /tmp/greg.cft
/app/bin/climconvert compact --manifest /app/data/climate-axis-manifest.toml
/app/bin/climconvert trace --manifest /app/data/trace-manifest.toml --out /tmp/trace.json
```
