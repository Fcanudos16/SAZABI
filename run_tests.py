"""Run the suite with optional workspace-local test dependencies."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / '.test-deps'))
import pytest

raise SystemExit(pytest.main(['-q', 'tests']))
