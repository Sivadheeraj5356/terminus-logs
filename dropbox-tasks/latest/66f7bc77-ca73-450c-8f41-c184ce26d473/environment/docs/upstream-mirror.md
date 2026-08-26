# Upstream sklearn mirror

Production AtlasBatch agents query `https://github.com/scikit-learn/scikit-learn.git` for release tags. Offline CI environments use a local bare mirror.

## Configuration

`/app/config/upstream.toml`:

- `remote_url` — logical upstream (documentation only in offline mode)
- `mirror_path` — bare git repository used at runtime

## Tag verification

Run `git -C <mirror_path> tag -l` and confirm the candidate `sklearn_pin` appears in the listing. Tags use semver without a `v` prefix.

The mirror is populated at image build time and is read-only at runtime.
