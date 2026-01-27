from pcl_exchange.validation import validate_semantics, validate_structure

import json

def test_example_compliance():
    # load the example message
    with open("examples/pcl_action_crate_example.json") as f:
        data = json.load(f)

    # check structure
    valid, err = validate_structure(data)
    assert valid, f"JSON Schema failed: {err}"

    # check semantics
    conforms, report = validate_semantics(data, "shapes/measurement_request.ttl")
    assert conforms, f"SHACL failed: {report}"