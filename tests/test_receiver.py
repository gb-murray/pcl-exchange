import copy
import json
from pathlib import Path
from typing import Any, Dict

from pcl_exchange.receiver import parse_and_validate_crate


def test_valid_crate_from_path() -> None:
    result = parse_and_validate_crate(Path("examples") / "pcl_action_crate_example.json")

    assert result.valid is True
    assert result.errors == []
    assert result.envelope is not None and result.envelope["@id"] == "#envelope"
    assert result.content is not None and result.content["@id"] == "#content"


def test_valid_crate_from_dict(example_action_crate: Dict[str, Any]) -> None:
    result = parse_and_validate_crate(copy.deepcopy(example_action_crate))

    assert result.valid is True
    assert result.errors == []
    assert result.envelope is not None and result.envelope["@id"] == "#envelope"
    assert result.content is not None and result.content["@id"] == "#content"


def test_valid_crate_from_json_string(example_action_crate: Dict[str, Any]) -> None:
    result = parse_and_validate_crate(json.dumps(example_action_crate))

    assert result.valid is True
    assert result.errors == []
    assert result.envelope is not None and result.envelope["@id"] == "#envelope"


def test_missing_envelope_node(example_action_crate: Dict[str, Any]) -> None:
    data = copy.deepcopy(example_action_crate)
    data["@graph"] = [node for node in data["@graph"] if node.get("@id") != "#envelope"]

    result = parse_and_validate_crate(data)

    assert result.valid is False
    assert result.envelope is None
    assert result.content is None
    assert [e.code for e in result.errors] == ["MISSING_ENVELOPE"]


def test_content_ref_target_missing(example_action_crate: Dict[str, Any]) -> None:
    data = copy.deepcopy(example_action_crate)
    for node in data["@graph"]:
        if node.get("@id") == "#envelope":
            node["contentRef"] = {"@id": "#does-not-exist"}

    result = parse_and_validate_crate(data)

    assert result.valid is False
    assert result.envelope is not None
    assert result.content is None
    assert [e.code for e in result.errors] == ["CONTENT_NOT_FOUND"]


def test_envelope_schema_violation(example_action_crate: Dict[str, Any]) -> None:
    data = copy.deepcopy(example_action_crate)
    for node in data["@graph"]:
        if node.get("@id") == "#envelope":
            del node["sender"]

    result = parse_and_validate_crate(data)

    assert result.valid is False
    assert result.envelope is not None
    assert "sender" not in result.envelope
    assert [e.code for e in result.errors] == ["SCHEMA_VALIDATION_ERROR"]


def test_invalid_json_string() -> None:
    result = parse_and_validate_crate("{not valid json")

    assert result.valid is False
    assert result.envelope is None
    assert [e.code for e in result.errors] == ["INVALID_JSON"]


def test_missing_graph_key() -> None:
    result = parse_and_validate_crate({"@context": "https://w3id.org/ro/crate/1.1/context"})

    assert result.valid is False
    assert result.envelope is None
    assert [e.code for e in result.errors] == ["MISSING_GRAPH"]
