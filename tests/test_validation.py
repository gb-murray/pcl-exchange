import copy
from typing import Any, Dict

import pcl_exchange.validation as validation
from pcl_exchange.validation import get_shape_for_action, validate_semantics, validate_structure


def test_get_shape_for_action_known_actions() -> None:
    assert get_shape_for_action("request_measurement") == "shapes/request_measurement.ttl"
    assert get_shape_for_action("launch_workflow") == "shapes/launch_workflow.ttl"


def test_get_shape_for_action_unmapped_action() -> None:
    assert get_shape_for_action("cancel_job") is None


def test_get_shape_for_action_does_not_read_shape_content(monkeypatch: Any) -> None:
    def fail_if_read(filename: str) -> str:
        raise AssertionError(f"Unexpected schema read: {filename}")

    monkeypatch.setattr(validation, "get_schema_text", fail_if_read)

    assert get_shape_for_action("request_measurement") == "shapes/request_measurement.ttl"

def test_example_compliance(example_action_crate: Dict[str, Any]) -> None:
    data = copy.deepcopy(example_action_crate)

    graph = data.get("@graph", [])
    envelope = next((item for item in graph if item.get("@id") == "#envelope"), None)
    assert envelope is not None, "Example crate missing #envelope node"

    valid, err = validate_structure(envelope)
    assert valid, f"JSON Schema failed: {err}"

    conforms, report = validate_semantics(data, "shapes/request_measurement.ttl")
    assert conforms, f"SHACL failed: {report}"

def test_envelope_with_routing_fields_validates(example_action_crate: Dict[str, Any]) -> None:
    data = copy.deepcopy(example_action_crate)

    graph = data.get("@graph", [])
    envelope = next((item for item in graph if item.get("@id") == "#envelope"), None)
    assert envelope is not None, "Example crate missing #envelope node"

    envelope["respondTo"] = "https://example.org/hooks/status"
    envelope["correlationId"] = "pcl-req-00042"
    envelope["idempotencyKey"] = "pcl-req-00042-v1"
    envelope["ttl"] = "PT10M"
    envelope["deadline"] = "2030-01-01T00:00:00Z"
    envelope["priority"] = 5
    envelope["protocolVersion"] = "1.1"
    envelope["schemaHash"] = {"alg": "sha256", "value": "a" * 64}

    valid, err = validate_structure(envelope)
    assert valid, f"JSON Schema failed: {err}"