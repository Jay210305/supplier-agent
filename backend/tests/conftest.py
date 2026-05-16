from __future__ import annotations

import pytest

from limiter import limiter


@pytest.fixture(autouse=True)
def reset_rate_limit_storage() -> None:
    limiter.reset()
    yield
    limiter.reset()
