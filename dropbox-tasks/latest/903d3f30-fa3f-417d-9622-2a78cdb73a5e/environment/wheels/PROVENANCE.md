# Python wheel provenance

These six platform-independent wheels were retrieved from their versioned
PyPI release pages on 2026-07-16 and are retained byte-for-byte in this task.
They are included only so the pytest reporting adapter can run without
package-index access during the Docker build or verification.

| Distribution | Upstream source | License recorded by wheel | SHA-256 |
| --- | --- | --- | --- |
| `iniconfig 2.3.0` | [PyPI release](https://pypi.org/project/iniconfig/2.3.0/), [source](https://github.com/pytest-dev/iniconfig) | MIT | `f631c04d2c48c52b84d0d0549c99ff3859c98df65b3101406327ecc7d53fbf12` |
| `packaging 26.2` | [PyPI release](https://pypi.org/project/packaging/26.2/), [source](https://github.com/pypa/packaging) | Apache-2.0 OR BSD-2-Clause | `5fc45236b9446107ff2415ce77c807cee2862cb6fac22b8a73826d0693b0980e` |
| `pluggy 1.6.0` | [PyPI release](https://pypi.org/project/pluggy/1.6.0/), [source](https://github.com/pytest-dev/pluggy) | MIT | `e920276dd6813095e9377c0bc5566d94c932c33b27a3e3945d8389c374dd4746` |
| `Pygments 2.20.0` | [PyPI release](https://pypi.org/project/Pygments/2.20.0/), [source](https://github.com/pygments/pygments) | BSD-2-Clause | `81a9e26dd42fd28a23a2d169d86d7ac03b46e2f8b59ed4698fb4785f946d0176` |
| `pytest 8.4.1` | [PyPI release](https://pypi.org/project/pytest/8.4.1/), [source](https://github.com/pytest-dev/pytest) | MIT | `539c70ba6fcead8e78eebbf1115e8b589e7565830d7d006a8723f19ac8a0afb7` |
| `pytest-json-ctrf 0.3.5` | [PyPI release](https://pypi.org/project/pytest-json-ctrf/0.3.5/), [source](https://github.com/infopulse/pytest-common-test-report-json) | MIT | `e82fd1d69be2f92385bc33540063e5ad7b17b36de67764c84f3ceb9815a895e9` |

The root `requirements.lock` is the build input and records the same exact
digest for every artifact. Five wheels carry their license texts in
`.dist-info/licenses`;
`pytest-json-ctrf` declares the MIT license in its embedded package metadata.
The builder installs from this directory with `--no-index` and
`--require-hashes`, runs `pip check`, and copies the resulting root-only
virtual environment into the runtime image. No wheel, trainer, or Python game
implementation is exposed under `/app`.
