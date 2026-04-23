from pcl_exchange.validation import validate_semantics, validate_structure
import json

def test_example_compliance():
    with open("examples/pcl_action_crate_example.json", encoding="utf-8") as f:
        data = json.load(f)

    graph = data.get("@graph", [])
    envelope = next((item for item in graph if item.get("@id") == "#envelope"), None)
    assert envelope is not None, "Example crate missing #envelope node"

    valid, err = validate_structure(envelope)
    assert valid, f"JSON Schema failed: {err}"

    conforms, report = validate_semantics(data, "shapes/measurement_request.ttl")
    assert conforms, f"SHACL failed: {report}"