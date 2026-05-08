import copy
from typing import Any, Dict

from pcl_exchange.validation import validate_semantics, validate_structure

def test_example_compliance(example_action_crate: Dict[str, Any]) -> None:
    data = copy.deepcopy(example_action_crate)

    graph = data.get("@graph", [])
    envelope = next((item for item in graph if item.get("@id") == "#envelope"), None)
    assert envelope is not None, "Example crate missing #envelope node"

    valid, err = validate_structure(envelope)
    assert valid, f"JSON Schema failed: {err}"

    conforms, report = validate_semantics(data, "shapes/measurement_request.ttl")
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