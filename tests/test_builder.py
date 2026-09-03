from datetime import datetime, timezone
import json
import re
from typing import Any, Dict, Optional

import pytest

from pcl_exchange.builder import PCLMessageBuilder, build_ack, build_nack
from pcl_exchange.crypto import Signer
from pcl_exchange.models import DEFAULT_SCHEMAS, PCLEnvelope, PCLError, PCLErrorCode, PCLErrorFault
from pcl_exchange.validation import validate_structure

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
    assert envelope["schema"] == DEFAULT_SCHEMAS["request_measurement"]

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


def test_set_action_type_updates_schema_default(
    builder_defaults: Dict[str, str],
    valid_payload_data: Dict[str, Any],
) -> None:
    builder = PCLMessageBuilder(**builder_defaults)
    builder.set_content(**valid_payload_data)
    builder.add_capability("xrd.powder.theta-2theta")
    builder.set_action_type("launch_workflow")

    envelope = next(
        item
        for item in builder.build().model_dump(by_alias=True, mode="json")["@graph"]
        if item["@id"] == "#envelope"
    )

    assert envelope["action"] == "launch_workflow"
    assert envelope["schema"] == DEFAULT_SCHEMAS["launch_workflow"]


def test_set_action_type_invalid_raises_value_error(builder_defaults: Dict[str, str]) -> None:
    builder = PCLMessageBuilder(**builder_defaults)

    with pytest.raises(ValueError, match="Unsupported action type"):
        builder.set_action_type("unsupported_action")


def test_set_schema_after_set_action_type_overrides_default(
    builder_defaults: Dict[str, str],
    valid_payload_data: Dict[str, Any],
) -> None:
    custom_schema = "https://example.org/schemas/custom-workflow/v1"
    builder = PCLMessageBuilder(**builder_defaults)
    builder.set_content(**valid_payload_data)
    builder.add_capability("xrd.powder.theta-2theta")
    builder.set_action_type("launch_workflow")
    builder.set_schema(custom_schema)

    envelope = next(
        item
        for item in builder.build().model_dump(by_alias=True, mode="json")["@graph"]
        if item["@id"] == "#envelope"
    )

    assert envelope["schema"] == custom_schema


def test_set_action_type_after_set_schema_uses_action_default(
    builder_defaults: Dict[str, str],
    valid_payload_data: Dict[str, Any],
) -> None:
    builder = PCLMessageBuilder(**builder_defaults)
    builder.set_content(**valid_payload_data)
    builder.add_capability("xrd.powder.theta-2theta")
    builder.set_schema("https://example.org/schemas/custom-measurement/v1")
    builder.set_action_type("launch_workflow")

    envelope = next(
        item
        for item in builder.build().model_dump(by_alias=True, mode="json")["@graph"]
        if item["@id"] == "#envelope"
    )

    assert envelope["schema"] == DEFAULT_SCHEMAS["launch_workflow"]


def test_set_schema_with_hash_sets_schema_and_schema_hash(
    builder_defaults: Dict[str, str],
    valid_payload_data: Dict[str, Any],
) -> None:
    schema_uri = "https://example.org/schemas/measurement/v2"
    schema_hash = {"alg": "sha256", "value": "b" * 64}
    builder = PCLMessageBuilder(**builder_defaults)
    builder.set_content(**valid_payload_data)
    builder.add_capability("xrd.powder.theta-2theta")
    builder.set_schema(schema_uri, schema_hash=schema_hash)

    envelope = next(
        item
        for item in builder.build().model_dump(by_alias=True, mode="json")["@graph"]
        if item["@id"] == "#envelope"
    )

    assert envelope["schema"] == schema_uri
    assert envelope["schemaHash"] == schema_hash


def test_set_action_type_and_schema_validate_structure(
    builder_defaults: Dict[str, str],
    valid_payload_data: Dict[str, Any],
    key_pair: Any,
) -> None:
    builder = PCLMessageBuilder(**builder_defaults)
    builder.set_content(**valid_payload_data)
    builder.add_capability("xrd.powder.theta-2theta")
    builder.set_action_type("launch_workflow")
    builder.set_schema("https://example.org/schemas/workflow/v2")
    builder.sign(Signer(private_key=key_pair))

    data_dict = json.loads(builder.build().to_json())
    envelope = next(item for item in data_dict["@graph"] if item["@id"] == "#envelope")
    valid, error = validate_structure(envelope)

    assert valid, error


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


def _build_original_envelope(
    builder_defaults: Dict[str, str],
    valid_payload_data: Dict[str, Any],
    correlation_id: Optional[str] = None,
    idempotency_key: Optional[str] = None,
) -> PCLEnvelope:
    """Builds a signed-shape request envelope to use as the `envelope` argument for build_ack/build_nack."""
    builder = PCLMessageBuilder(**builder_defaults)
    builder.set_content(**valid_payload_data)
    builder.add_capability("xrd.powder.theta-2theta")
    if correlation_id is not None:
        builder.set_correlation_id(correlation_id)
    if idempotency_key is not None:
        builder.set_idempotency_key(idempotency_key)
    message = builder.build()
    return next(item for item in message.graph if isinstance(item, PCLEnvelope))


def test_build_ack_swaps_sender_receiver_and_echoes_fields(
    builder_defaults: Dict[str, str],
    valid_payload_data: Dict[str, Any],
) -> None:
    original = _build_original_envelope(builder_defaults, valid_payload_data, correlation_id="pcl-req-00042")

    ack = build_ack(original)

    assert ack.sender == original.receiver
    assert ack.receiver == original.sender
    assert ack.action == "ack"
    assert ack.schema_ == DEFAULT_SCHEMAS["ack"]
    assert ack.capabilities == original.capabilities
    assert ack.project == original.project
    assert ack.sample == original.sample
    assert ack.correlation_id == "pcl-req-00042"
    assert ack.content_ref == "#none"
    assert ack.authz is None


def test_build_ack_correlation_id_falls_back_to_original_identifier(
    builder_defaults: Dict[str, str],
    valid_payload_data: Dict[str, Any],
) -> None:
    original = _build_original_envelope(builder_defaults, valid_payload_data)

    ack = build_ack(original)

    assert ack.correlation_id == original.identifier


def test_build_ack_job_id_sets_identifier(
    builder_defaults: Dict[str, str],
    valid_payload_data: Dict[str, Any],
) -> None:
    original = _build_original_envelope(builder_defaults, valid_payload_data)

    ack_with_job_id = build_ack(original, job_id="job-12345678")
    ack_without_job_id = build_ack(original)

    assert ack_with_job_id.identifier == "job-12345678"
    assert ack_without_job_id.identifier.startswith("urn:uuid:")


def test_build_ack_validates_against_envelope_schema(
    builder_defaults: Dict[str, str],
    valid_payload_data: Dict[str, Any],
    key_pair: Any,
) -> None:
    original = _build_original_envelope(builder_defaults, valid_payload_data)

    ack = build_ack(original, job_id="job-12345678")
    ack_data = ack.model_dump(mode="json", by_alias=True, exclude_none=True)
    ack_data["authz"] = {"type": "DetachedJWS", "jws": Signer(private_key=key_pair).sign(ack_data)}

    valid, error = validate_structure(ack_data)

    assert valid, error


def test_build_nack_returns_envelope_and_error_linked_by_content_ref(
    builder_defaults: Dict[str, str],
    valid_payload_data: Dict[str, Any],
) -> None:
    original = _build_original_envelope(builder_defaults, valid_payload_data, correlation_id="pcl-req-00042")

    nack_envelope, error = build_nack(
        original, code=PCLErrorCode.SCHEMA_MISMATCH, reason="Envelope failed schema validation"
    )

    assert nack_envelope.action == "nack"
    assert nack_envelope.schema_ == DEFAULT_SCHEMAS["nack"]
    assert nack_envelope.content_ref == {"@id": "#error"}
    assert error.id == "#error"
    assert error.code == PCLErrorCode.SCHEMA_MISMATCH
    assert error.reason == "Envelope failed schema validation"
    assert error.correlation_id == nack_envelope.correlation_id == "pcl-req-00042"


def test_build_nack_carries_faults(
    builder_defaults: Dict[str, str],
    valid_payload_data: Dict[str, Any],
) -> None:
    original = _build_original_envelope(builder_defaults, valid_payload_data)
    faults = [PCLErrorFault(message="Value must match pattern", path="/capabilities/0")]

    _, error = build_nack(original, code=PCLErrorCode.SCHEMA_MISMATCH, reason="bad", faults=faults)

    assert error.faults == faults


def test_build_nack_validates_against_envelope_and_error_schemas(
    builder_defaults: Dict[str, str],
    valid_payload_data: Dict[str, Any],
    key_pair: Any,
) -> None:
    original = _build_original_envelope(builder_defaults, valid_payload_data)

    nack_envelope, error = build_nack(original, code=PCLErrorCode.INTERNAL_ERROR, reason="Unexpected failure")

    envelope_data = nack_envelope.model_dump(mode="json", by_alias=True, exclude_none=True)
    envelope_data["authz"] = {"type": "DetachedJWS", "jws": Signer(private_key=key_pair).sign(envelope_data)}
    envelope_valid, envelope_error = validate_structure(envelope_data)
    assert envelope_valid, envelope_error

    error_data = error.model_dump(mode="json", by_alias=True, exclude_none=True)
    error_valid, error_error = validate_structure(error_data, schema_filename="error.json")
    assert error_valid, error_error


def test_pclerror_to_json_round_trip() -> None:
    error = PCLError(id="#error", code=PCLErrorCode.NOT_FOUND, reason="Sample not found")

    parsed = json.loads(error.to_json())

    assert parsed["@id"] == "#error"
    assert parsed["code"] == "NOT_FOUND"
    assert parsed["reason"] == "Sample not found"
    assert "correlationId" not in parsed


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
        lambda b, _: b.set_action_type("launch_workflow"),
        lambda b, _: b.set_schema(
            "https://w3id.org/pcl-schema/measure-request/v1.0",
            schema_hash={"alg": "sha256", "value": "a" * 64},
        ),
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