import pytest
from pcl_exchange.builder import PCLMessageBuilder

def test_builder_initialization(builder_defaults):
    builder = PCLMessageBuilder(**builder_defaults)
    assert builder.sender == builder_defaults['sender_id']
    assert builder.receiver == builder_defaults['receiver_id']

def test_build_minimal_message(builder_defaults, valid_payload_data):
    """Test creating a message and checking critical JSON-LD fields."""
    builder = PCLMessageBuilder(**builder_defaults)
    
    # set content
    builder.set_content(**valid_payload_data)
    builder.add_capability("xrd.powder.theta-2theta")
    
    # build
    message = builder.build()
    json_output = message.model_dump(by_alias=True)

    assert "@context" in json_output
    assert "@graph" in json_output
    
    # get envelope
    graph = json_output["@graph"]
    envelope = next(item for item in graph if item["@id"] == "#envelope")
    
    assert envelope["sender"] == builder_defaults['sender_id']
    assert "xrd.powder.theta-2theta" in envelope["capabilities"]
    assert envelope["action"] == "request_measurement"

def test_missing_content_raises_error(builder_defaults):
    """Trying to build without setting content should fail."""
    builder = PCLMessageBuilder(**builder_defaults)
    # dont call set_content()
    
    with pytest.raises(Exception): # Pydantic validation error expected
        builder.build()