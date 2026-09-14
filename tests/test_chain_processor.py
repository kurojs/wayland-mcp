"""A chain must report failure and stop at the step that failed.

The handlers registered by server_mcp return dicts. ChainProcessor stored the
whole dict in its "success" field, and a non-empty dict is always truthy, so a
failing step looked successful, never broke the chain, and the overall result was
unconditionally True -- an action chain reported success no matter what happened.
"""
import pytest

from wayland_mcp.chain_processor import ACTION_HANDLERS, ChainProcessor, register_handler


@pytest.fixture(autouse=True)
def clean_registry():
    """Keep the module-level handler registry from leaking between tests."""
    saved = dict(ACTION_HANDLERS)
    ACTION_HANDLERS.clear()
    yield
    ACTION_HANDLERS.clear()
    ACTION_HANDLERS.update(saved)


def test_a_chain_of_successful_steps_succeeds():
    calls = []
    register_handler("ok:", lambda action: calls.append(action) or {"success": True})
    result = ChainProcessor("ok:one;ok:two").execute()
    assert result["success"] is True
    assert result["executed"] == 2
    assert calls == ["ok:one", "ok:two"]


def test_a_failing_step_makes_the_chain_fail():
    register_handler("bad:", lambda _action: {"success": False, "error": "nope"})
    result = ChainProcessor("bad:one").execute()
    assert result["success"] is False
    assert result["results"][0]["error"] == "nope"


def test_a_failing_step_stops_the_chain():
    """The steps after a failure must not run: later ones assume earlier worked."""
    calls = []
    register_handler("bad:", lambda _action: {"success": False, "error": "nope"})
    register_handler("ok:", lambda action: calls.append(action) or {"success": True})
    result = ChainProcessor("bad:one;ok:two").execute()
    assert result["success"] is False
    assert result["executed"] == 1
    assert calls == []


def test_handlers_returning_a_bare_bool_still_work():
    """The registry is public API; a handler may predate the dict convention."""
    register_handler("plain:", lambda _action: True)
    register_handler("plainfail:", lambda _action: False)
    assert ChainProcessor("plain:x").execute()["success"] is True
    assert ChainProcessor("plainfail:x").execute()["success"] is False


def test_step_success_is_a_boolean_not_a_dict():
    register_handler("ok:", lambda _action: {"success": True})
    step = ChainProcessor("ok:x").execute()["results"][0]
    assert step["success"] is True


def test_an_error_from_a_handler_is_reported_against_its_step():
    register_handler("boom:", lambda _action: (_ for _ in ()).throw(RuntimeError("kaboom")))
    result = ChainProcessor("boom:x").execute()
    assert result["success"] is False
    assert "kaboom" in result["results"][0]["error"]


def test_an_unknown_action_is_refused_before_anything_runs():
    calls = []
    register_handler("ok:", lambda action: calls.append(action) or {"success": True})
    result = ChainProcessor("ok:one;nonsense:two").execute()
    assert result["success"] is False
    assert result["executed"] == 0
    assert calls == []


def test_a_chain_longer_than_the_limit_is_refused():
    register_handler("ok:", lambda _action: {"success": True})
    result = ChainProcessor(";".join(["ok:x"] * 11)).execute()
    assert result["success"] is False


def test_an_empty_chain_is_refused():
    assert ChainProcessor("").execute()["success"] is False


def test_the_step_label_names_the_action_it_ran():
    """The label came from prefix[:-1], which turned "click" into "clic"."""
    register_handler("click", lambda _action: {"success": True})
    step = ChainProcessor("click").execute()["results"][0]
    assert "clic " not in step["output"]
    assert "click" in step["output"]
