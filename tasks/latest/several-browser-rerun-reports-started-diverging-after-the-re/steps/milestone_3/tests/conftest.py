import pytest

from reference_flaky import prepare_valid_history_rows, write_reference_plan


@pytest.fixture(scope="session", autouse=True)
def upstream_plan_ready():
    prepare_valid_history_rows()
    write_reference_plan()
