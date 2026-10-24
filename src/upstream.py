"""Import Shi et al.'s code (third_party/agent-collusion, pinned 5afb2c5) without network side effects.

LITELLM_LOCAL_MODEL_COST_MAP=True makes LiteLLM use its bundled cost map instead of fetching one
from GitHub at import time. Import this module before anything that imports litellm.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT / "third_party" / "agent-collusion"
UPSTREAM_COMMIT = "5afb2c595aa3eff6b9b829a032f4f117b36ee54d"

os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
if str(UPSTREAM) not in sys.path:
    sys.path.insert(0, str(UPSTREAM))
