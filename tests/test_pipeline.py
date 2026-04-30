"""Backward-compat stub: tests have been split into dedicated modules.

- Collection and report-builder tests:  tests/test_pipeline_collection.py
- run_pipeline and main integration:    tests/test_pipeline_run.py
- Phase2, semantic, and tracing:        tests/test_pipeline_phase2.py
"""

from .test_pipeline_collection import *  # noqa: F401, F403
from .test_pipeline_phase2 import *  # noqa: F401, F403
from .test_pipeline_run import *  # noqa: F401, F403
