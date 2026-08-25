"""Load .env before pytest collects test modules.

Test files check os.getenv(...) at import time (e.g. tests/test_graph_smoke.py's
pytestmark skipif), so the .env file must be loaded before collection — not just
inside llm.py, which is imported later.
"""

from dotenv import load_dotenv

load_dotenv()
