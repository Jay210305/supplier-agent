from __future__ import annotations

import os
import tempfile
from pathlib import Path

os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault(
    "GENERATED_POS_DIR",
    str(Path(tempfile.gettempdir()) / "supplier-agent-test-pos"),
)

import pytest

from limiter import limiter


@pytest.fixture(autouse=True)
def reset_rate_limit_storage() -> None:
    limiter.reset()
    yield
    limiter.reset()
