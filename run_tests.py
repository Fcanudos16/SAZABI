"""Run the suite with optional workspace-local test dependencies."""
import sys
import os
from uuid import uuid4
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / os.environ.get('SAZABI_TEST_DEPS', '.test-deps')))
import pytest

# A fresh directory avoids touching old Windows test folders with incompatible ACLs.
root = Path(__file__).resolve().parent
temporary = root / 'data' / 'test-runs' / uuid4().hex
assert temporary.is_relative_to(root) and not temporary.exists()
temporary.parent.mkdir(parents=True, exist_ok=True)
raise SystemExit(pytest.main(['-q', '-p', 'no:cacheprovider', '--basetemp', str(temporary), 'tests']))
