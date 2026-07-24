import json
from pathlib import Path

import pytest

from ingest import db

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str):
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture
def conn():
    c = db.connect(":memory:")
    yield c
    c.close()
