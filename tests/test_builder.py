from datetime import datetime, timezone
from typing import Any, Dict

import pytest

from pcl_exchange.builder import PCLMessageBuilder

def test_builder_initialization(builder_defaults: Dict[str, str]) -> None:
    builder = PCLMessageBuilder(**builder_defaults)
    assert builder.sender == builder_defaults['sender_id']
    assert builder.receiver == builder_defaults['receiver_id']

def test_build_minimal_message(
    builder_defaults: Dict[str, str],
    valid_payload_data: Dict[str, Any]
) -> None:
    """Test creating a message and checking critical JSON-LD fields."""
    builder = PCLMessageBuilder(**builder_defaults)

    builder.set_content(**valid_payload_data)
    builder.add_capability("xrd.powder.theta-2theta")
    message = builder.build()
    json_output = message.model_dump(by_alias=True, mode="json")

    assert "@context" in json_output
    assert "@graph" in json_output
    
    graph = json_output["@graph"]
    envelope = next(item for item in graph if item["@id"] == "#envelope")
    
    assert envelope["sender"] == builder_defaults['sender_id']
    assert "xrd.powder.theta-2theta" in envelope["capabilities"]
    assert envelope["action"] == "request_measurement"

def test_missing_content_raises_error(builder_defaults: Dict[str, str]) -> None:
    """Trying to build without setting content should fail."""
    builder = PCLMessageBuilder(**builder_defaults)

    with pytest.raises(ValueError):
        builder.build()

def test_builder_sets_routing_fields(
    builder_defaults: Dict[str, str],
    valid_payload_data: Dict[str, Any]
) -> None:
    builder = PCLMessageBuilder(**builder_defaults)
    builder.set_content(**valid_payload_data)
    builder.add_capability("xrd.powder.theta-2theta")

    deadline = datetime(2030, 1, 1, tzinfo=timezone.utc)

    builder.set_respond_to("https://example.org/hooks/status")
    builder.set_correlation_id("pcl-req-00042")
    builder.set_idempotency_key("pcl-req-00042-v1")
    builder.set_ttl("PT10M")
    builder.set_deadline(deadline)
    builder.set_priority(5)
    builder.set_protocol_version("1.1")
    builder.set_schema_hash("sha256", "a" * 64)

    message = builder.build()
    json_output = message.model_dump(by_alias=True, mode="json")
    envelope = next(item for item in json_output["@graph"] if item["@id"] == "#envelope")

    assert envelope["respondTo"] == "https://example.org/hooks/status"
    assert envelope["correlationId"] == "pcl-req-00042"
    assert envelope["idempotencyKey"] == "pcl-req-00042-v1"
    assert envelope["ttl"] == "PT10M"
    assert envelope["deadline"] == deadline.isoformat().replace("+00:00", "Z")
    assert envelope["priority"] == 5
    assert envelope["protocolVersion"] == "1.1"
    assert envelope["schemaHash"] == {"alg": "sha256", "value": "a" * 64}