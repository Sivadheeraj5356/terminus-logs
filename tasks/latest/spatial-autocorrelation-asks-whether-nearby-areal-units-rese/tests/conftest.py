"""Write the /logs/verifier/passed marker only when the whole session passes."""

import os


def pytest_sessionfinish(session, exitstatus):
    if exitstatus == 0:
        try:
            os.makedirs("/logs/verifier", exist_ok=True)
            with open("/logs/verifier/passed", "w") as fh:
                fh.write("passed\n")
        except OSError:
            pass
