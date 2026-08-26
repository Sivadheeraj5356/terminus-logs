import pytest

from reference_flaky import prepare_valid_history_rows


@pytest.fixture(scope="session", autouse=True)
def upstream_history_ready():
    prepare_valid_history_rows()
