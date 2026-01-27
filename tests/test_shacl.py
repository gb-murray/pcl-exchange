import json
from pcl_exchange.builder import PCLMessageBuilder
from pcl_exchange.validation import validate_semantics, validate_structure
from pcl_exchange.crypto import Signer


def test_generated_json_passes_shacl(builder_defaults, valid_payload_data, key_pair):
    """
    Integration Test:
    1. Python Builder creates JSON
    2. JSON Schema Validator checks envelope structure
    3. SHACL Validator checks graph semantics
    """
    builder = PCLMessageBuilder(**builder_defaults)
    builder.set_content(**valid_payload_data)
    builder.add_capability("xrd.powder.theta-2theta")
    builder.sign(Signer(key_pair))
    
    message = builder.build()
    json_data = message.to_json() # returns string
    
    # validate structure and semantics
    data_dict = json.loads(json_data)
    envelope_dict = next(item for item in data_dict["@graph"] if item["@id"] == "#envelope")
    
    is_valid_structure, err = validate_structure(envelope_dict)
    assert is_valid_structure, f"JSON Schema Validation Failed: {err}"

    conforms, report = validate_semantics(json_data, "shapes/measurement_request.ttl")
    assert conforms, f"SHACL Validation Failed:\n{report}"

def test_invalid_structure_fails_shacl(builder_defaults, valid_payload_data):
    """
    Test that SHACL correctly catches a missing mandatory field.
    """
    builder = PCLMessageBuilder(**builder_defaults)
    builder.set_content(**valid_payload_data)
    message = builder.build()
    
    # break the structure by removing a required field
    for item in message.graph:
        if item.id == "#content":
            item.instrument = None 
            
    # break the JSON for SHACL
    json_str = message.to_json()
    json_dict = json.loads(json_str)
    
    for item in json_dict["@graph"]:
        if item["@id"] == "#content":
            del item["instrument"] 
            
    broken_json = json.dumps(json_dict)

    conforms, report = validate_semantics(broken_json, "shapes/measurement_request.ttl")
    assert not conforms
    assert "instrument" in report # the report should have missing field