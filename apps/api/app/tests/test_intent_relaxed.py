"""Task 5: conversational intent definition no longer says '修改建议' and
covers free-form presales questions."""
import inspect
from app.services import react_intent, intent_service


def test_react_intent_definition_relaxed():
    src = inspect.getsource(react_intent)
    assert "修改建议" not in src
    assert "自由提问" in src or "问答" in src


def test_intent_service_definition_relaxed():
    src = inspect.getsource(intent_service)
    assert "修改建议" not in src
