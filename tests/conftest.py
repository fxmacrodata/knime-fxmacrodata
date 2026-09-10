"""Use KNIME's official Python testing backend, never a local SDK imitation."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import knime.extension.testing  # noqa: E402,F401
