from datetime import datetime, timezone
import re
from typing import Any, Dict

import pytest

from pcl_exchange.builder import PCLMessageBuilder
from pcl_exchange.crypto import Signer

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


def test_build_populates_content_digest(
    builder_defaults: Dict[str, str],
    valid_payload_data: Dict[str, Any]
) -> None:
    builder = PCLMessageBuilder(**builder_defaults)
    builder.set_content(**valid_payload_data)
    builder.add_capability("xrd.powder.theta-2theta")

    message = builder.build()
    json_output = message.model_dump(by_alias=True, mode="json")
    envelope = next(item for item in json_output["@graph"] if item["@id"] == "#envelope")
    content_digest = envelope["contentDigest"]

    assert content_digest["alg"] == "sha256"
    assert re.fullmatch(r"[A-Fa-f0-9]{64}", content_digest["value"]) is not None
    assert isinstance(content_digest["size"], int)
    assert content_digest["size"] > 0


def test_content_digest_is_deterministic_for_fixed_content(
    builder_defaults: Dict[str, str],
    valid_payload_data: Dict[str, Any]
) -> None:
    first_builder = PCLMessageBuilder(**builder_defaults)
    first_builder.set_content(**valid_payload_data)
    first_builder.add_capability("xrd.powder.theta-2theta")

    second_builder = PCLMessageBuilder(**builder_defaults)
    second_builder.set_content(**valid_payload_data)
    second_builder.add_capability("xrd.powder.theta-2theta")

    first_message = first_builder.build().model_dump(by_alias=True, mode="json")
    second_message = second_builder.build().model_dump(by_alias=True, mode="json")

    first_envelope = next(item for item in first_message["@graph"] if item["@id"] == "#envelope")
    second_envelope = next(item for item in second_message["@graph"] if item["@id"] == "#envelope")

    assert first_envelope["contentDigest"]["value"] == second_envelope["contentDigest"]["value"]
    assert first_envelope["contentDigest"]["size"] == second_envelope["contentDigest"]["size"]


def test_sign_requires_content(builder_defaults: Dict[str, str], key_pair: Any) -> None:
    builder = PCLMessageBuilder(**builder_defaults)

    with pytest.raises(RuntimeError, match="Message content has not been set"):
        builder.sign(Signer(private_key=key_pair))


def test_sign_cannot_be_called_twice(
    builder_defaults: Dict[str, str],
    valid_payload_data: Dict[str, Any],
    key_pair: Any
) -> None:
    builder = PCLMessageBuilder(**builder_defaults)
    builder.set_content(**valid_payload_data)
    signer = Signer(private_key=key_pair)

    builder.sign(signer)

    with pytest.raises(RuntimeError, match="Cannot call sign\(\) more than once"):
        builder.sign(signer)


@pytest.mark.parametrize(
    "mutation_call",
    [
        lambda b, p: b.set_content(**p),
        lambda b, _: b.add_capability("xrd.powder.theta-2theta"),
        lambda b, _: b.set_respond_to("https://example.org/hooks/status"),
        lambda b, _: b.set_correlation_id("pcl-req-00042"),
        lambda b, _: b.set_idempotency_key("pcl-req-00042-v1"),
        lambda b, _: b.set_ttl("PT10M"),
        lambda b, _: b.set_deadline(datetime(2030, 1, 1, tzinfo=timezone.utc)),
        lambda b, _: b.set_priority(5),
        lambda b, _: b.set_protocol_version("1.1"),
        lambda b, _: b.set_schema_hash("sha256", "a" * 64),
    ],
)
def test_mutations_after_sign_are_rejected(
    builder_defaults: Dict[str, str],
    valid_payload_data: Dict[str, Any],
    key_pair: Any,
    mutation_call: Any,
) -> None:
    builder = PCLMessageBuilder(**builder_defaults)
    builder.set_content(**valid_payload_data)
    builder.sign(Signer(private_key=key_pair))

    with pytest.raises(RuntimeError, match="Cannot modify builder after sign\(\) has been called"):
        mutation_call(builder, valid_payload_data)