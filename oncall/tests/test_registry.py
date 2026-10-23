import jsonschema
import pytest

from oncall.models import make_result
from oncall.tools import TOOL_SCHEMAS, TOOLS, register_tool


@pytest.fixture
def dummy_tools():
    @register_tool(
        "dummy_echo",
        "Echo the message back.",
        {"properties": {"msg": {"type": "string"}}, "required": ["msg"]},
    )
    def dummy_echo(msg: str):
        return make_result("dummy_echo", {"msg": msg}, msg, [])

    @register_tool("dummy_boom", "Always fails.", {"properties": {}})
    def dummy_boom():
        raise RuntimeError("kaboom")

    yield
    for name in ("dummy_echo", "dummy_boom"):
        TOOLS.pop(name, None)
        TOOL_SCHEMAS.pop(name, None)


def test_registered_tool_has_valid_schema(dummy_tools):
    assert "dummy_echo" in TOOLS
    schema = TOOL_SCHEMAS["dummy_echo"]
    assert schema["name"] == "dummy_echo"
    assert schema["description"] == "Echo the message back."
    jsonschema.Draft202012Validator.check_schema(schema["input_schema"])
    jsonschema.validate({"msg": "hi"}, schema["input_schema"])
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({}, schema["input_schema"])


def test_registered_tool_runs(dummy_tools):
    result = TOOLS["dummy_echo"](msg="hi")
    assert result["ok"] is True
    assert result["summary"] == "hi"


def test_exception_becomes_error_result(dummy_tools):
    result = TOOLS["dummy_boom"]()
    assert result["ok"] is False
    assert result["tool"] == "dummy_boom"
    assert result["error"] == "RuntimeError: kaboom"
