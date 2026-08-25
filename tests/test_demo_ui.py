"""End-to-end test for the Streamlit demo UI (demo_ui.py) using AppTest.

Proves the UI is wired to the *real* compiled graph (real LLM calls), not a mockup:
types a question, clicks submit, and checks the route/answer actually render.

Requires: pip install -e ".[demo]" (streamlit) and a configured LLM API key.
"""

import importlib.util
import os

import pytest

pytestmark = [
    pytest.mark.skipif(
        importlib.util.find_spec("streamlit") is None,
        reason="streamlit not installed (pip install -e '.[demo]')",
    ),
    pytest.mark.skipif(
        not os.getenv("GEMINI_API_KEY")
        and not os.getenv("OPENAI_API_KEY")
        and not os.getenv("ANTHROPIC_API_KEY"),
        reason="No LLM API key configured (set GEMINI_API_KEY, OPENAI_API_KEY, or ANTHROPIC_API_KEY)",
    ),
]

from streamlit.testing.v1 import AppTest


def test_demo_ui_simple_route_end_to_end():
    at = AppTest.from_file("../demo_ui.py", default_timeout=60)
    at.run()
    assert not at.exception

    at.text_input(key="query").set_value("How do I reset my password?")
    at.button[0].click()  # "Gửi câu hỏi"
    at.run()

    assert not at.exception, f"app raised: {at.exception}"

    headings = "\n".join(md.value for md in at.markdown)
    assert "Simple" in headings, "route heading should show the classified route"
    assert "Đường đi" in headings, "trace section should render"

    assert len(at.success) >= 1, "final answer should render in a success box"
    assert at.success[0].value, "final answer must not be empty"


def test_demo_ui_risky_route_shows_approval():
    at = AppTest.from_file("../demo_ui.py", default_timeout=60)
    at.run()

    at.text_input(key="query").set_value("Refund this customer and send confirmation email")
    at.button[0].click()
    at.run()

    assert not at.exception, f"app raised: {at.exception}"

    headings = "\n".join(md.value for md in at.markdown)
    assert "Risky" in headings
    assert "Approval" in headings, "risky route must show an approval decision"


def test_demo_ui_no_secrets_in_rendered_output():
    """The UI must never render raw env vars/API keys, even if it crashes."""
    at = AppTest.from_file("../demo_ui.py", default_timeout=60)
    at.run()
    at.text_input(key="query").set_value("How do I reset my password?")
    at.button[0].click()
    at.run()

    rendered = "\n".join(
        [md.value for md in at.markdown]
        + [s.value for s in at.success]
        + [c.value for c in at.caption]
    )
    for env_var in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY"):
        secret = os.getenv(env_var)
        if secret:
            assert secret not in rendered, f"{env_var} value leaked into rendered UI"
