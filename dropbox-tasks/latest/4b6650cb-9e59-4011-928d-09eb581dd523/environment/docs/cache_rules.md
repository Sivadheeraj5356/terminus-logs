# Width cache

`/app/environment/ops/sweep.cache` lists `{profile, width_ms, manifest_gen}` rows. For a profile, choose the first row where `profile` matches and `manifest_gen >= manifest.manifest_gen`; otherwise use `window_width_ms` from the manifest.
