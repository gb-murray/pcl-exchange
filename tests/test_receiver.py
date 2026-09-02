import copy
import json
from pathlib import Path
from typing import Any, Callable, Dict

from jwcrypto import jwk

from pcl_exchange.builder import PCLMessageBuilder
from pcl_exchange.crypto import Signer
from pcl_exchange.receiver import parse_and_validate_crate


def _never_called(sender_id: str) -> jwk.JWK:
    raise AssertionError(f"resolver should not have been called for '{sender_id}'")


def _example_resolver(example_sender_public_key: jwk.JWK) -> Callable[[str], jwk.JWK]:
    def _resolve(sender_id: str) -> jwk.JWK:
        if sender_id != "https://ror.org/03yrm5c26":
            raise LookupError(sender_id)
        return example_sender_public_key

    return _resolve


def test_valid_crate_from_path(example_sender_public_key: jwk.JWK) -> None:
    result = parse_and_validate_crate(
        Path("examples") / "pcl_action_crate_example.json", _example_resolver(example_sender_public_key)
    )

    assert result.valid is True
    assert result.errors == []
    assert result.envelope is not None and result.envelope["@id"] == "#envelope"
    assert result.content is not None and result.content["@id"] == "#content"


def test_valid_crate_from_dict(example_action_crate: Dict[str, Any], example_sender_public_key: jwk.JWK) -> None:
    result = parse_and_validate_crate(
        copy.deepcopy(example_action_crate), _example_resolver(example_sender_public_key)
    )

    assert result.valid is True
    assert result.errors == []
    assert result.envelope is not None and result.envelope["@id"] == "#envelope"
    assert result.content is not None and result.content["@id"] == "#content"


def test_valid_crate_from_json_string(
    example_action_crate: Dict[str, Any], example_sender_public_key: jwk.JWK
) -> None:
    result = parse_and_validate_crate(json.dumps(example_action_crate), _example_resolver(example_sender_public_key))

    assert result.valid is True
    assert result.errors == []
    assert result.envelope is not None and result.envelope["@id"] == "#envelope"


def test_missing_envelope_node(example_action_crate: Dict[str, Any]) -> None:
    data = copy.deepcopy(example_action_crate)
    data["@graph"] = [node for node in data["@graph"] if node.get("@id") != "#envelope"]

    result = parse_and_validate_crate(data, _never_called)

    assert result.valid is False
    assert result.envelope is None
    assert result.content is None
    assert [e.code for e in result.errors] == ["MISSING_ENVELOPE"]


def test_content_ref_target_missing(example_action_crate: Dict[str, Any], example_sender_public_key: jwk.JWK) -> None:
    data = copy.deepcopy(example_action_crate)
    for node in data["@graph"]:
        if node.get("@id") == "#envelope":
            node["contentRef"] = {"@id": "#does-not-exist"}

    result = parse_and_validate_crate(data, _example_resolver(example_sender_public_key))

    assert result.valid is False
    assert result.envelope is not None
    assert result.content is None
    # tampering contentRef also invalidates the signature, since it covers the whole envelope
    assert [e.code for e in result.errors] == ["CONTENT_NOT_FOUND", "INVALID_SIGNATURE"]


def test_envelope_schema_violation(example_action_crate: Dict[str, Any], example_sender_public_key: jwk.JWK) -> None:
    data = copy.deepcopy(example_action_crate)
    for node in data["@graph"]:
        if node.get("@id") == "#envelope":
            del node["sender"]

    result = parse_and_validate_crate(data, _example_resolver(example_sender_public_key))

    assert result.valid is False
    assert result.envelope is not None
    assert "sender" not in result.envelope
    # sender is gone, so the signature step can't resolve a sender id either
    assert [e.code for e in result.errors] == ["SCHEMA_VALIDATION_ERROR", "MISSING_SENDER"]


def test_invalid_json_string() -> None:
    result = parse_and_validate_crate("{not valid json", _never_called)

    assert result.valid is False
    assert result.envelope is None
    assert [e.code for e in result.errors] == ["INVALID_JSON"]


def test_missing_graph_key() -> None:
    result = parse_and_validate_crate({"@context": "https://w3id.org/ro/crate/1.1/context"}, _never_called)

    assert result.valid is False
    assert result.envelope is None
    assert [e.code for e in result.errors] == ["MISSING_GRAPH"]


def _build_signed_crate(
    key_pair: jwk.JWK, builder_defaults: Dict[str, str], valid_payload_data: Dict[str, Any]
) -> Dict[str, Any]:
    builder = PCLMessageBuilder(**builder_defaults)
    builder.set_content(**valid_payload_data)
    builder.add_capability("xrd.powder.theta-2theta")
    builder.sign(Signer(private_key=key_pair))
    return json.loads(builder.build().to_json())


def test_signed_crate_verifies(
    key_pair: jwk.JWK, builder_defaults: Dict[str, str], valid_payload_data: Dict[str, Any]
) -> None:
    data = _build_signed_crate(key_pair, builder_defaults, valid_payload_data)

    result = parse_and_validate_crate(data, lambda sender_id: key_pair)

    assert result.valid is True
    assert result.errors == []


def test_tampered_field_invalidates_signature(
    key_pair: jwk.JWK, builder_defaults: Dict[str, str], valid_payload_data: Dict[str, Any]
) -> None:
    data = _build_signed_crate(key_pair, builder_defaults, valid_payload_data)
    for node in data["@graph"]:
        if node.get("@id") == "#envelope":
            node["capabilities"] = ["tampered.capability"]

    result = parse_and_validate_crate(data, lambda sender_id: key_pair)

    assert result.valid is False
    assert [e.code for e in result.errors] == ["INVALID_SIGNATURE"]


def test_tampered_jws_invalidates_signature(
    key_pair: jwk.JWK, builder_defaults: Dict[str, str], valid_payload_data: Dict[str, Any]
) -> None:
    data = _build_signed_crate(key_pair, builder_defaults, valid_payload_data)
    for node in data["@graph"]:
        if node.get("@id") == "#envelope":
            node["authz"]["jws"] = node["authz"]["jws"][:-4] + "abcd"

    result = parse_and_validate_crate(data, lambda sender_id: key_pair)

    assert result.valid is False
    assert [e.code for e in result.errors] == ["INVALID_SIGNATURE"]


def test_unknown_sender_key(
    key_pair: jwk.JWK, builder_defaults: Dict[str, str], valid_payload_data: Dict[str, Any]
) -> None:
    data = _build_signed_crate(key_pair, builder_defaults, valid_payload_data)

    def _resolver(sender_id: str) -> jwk.JWK:
        raise LookupError(sender_id)

    result = parse_and_validate_crate(data, _resolver)

    assert result.valid is False
    assert [e.code for e in result.errors] == ["UNKNOWN_SENDER_KEY"]


def test_missing_signature(
    key_pair: jwk.JWK, builder_defaults: Dict[str, str], valid_payload_data: Dict[str, Any]
) -> None:
    data = _build_signed_crate(key_pair, builder_defaults, valid_payload_data)
    for node in data["@graph"]:
        if node.get("@id") == "#envelope":
            del node["authz"]

    result = parse_and_validate_crate(data, lambda sender_id: key_pair)

    assert result.valid is False
    assert [e.code for e in result.errors] == ["SCHEMA_VALIDATION_ERROR", "MISSING_SIGNATURE"]


def test_unsupported_authz_type(
    key_pair: jwk.JWK, builder_defaults: Dict[str, str], valid_payload_data: Dict[str, Any]
) -> None:
    data = _build_signed_crate(key_pair, builder_defaults, valid_payload_data)
    for node in data["@graph"]:
        if node.get("@id") == "#envelope":
            node["authz"] = {"@id": "#vp"}

    result = parse_and_validate_crate(data, lambda sender_id: key_pair)

    assert result.valid is False
    assert [e.code for e in result.errors] == ["UNSUPPORTED_AUTHZ_TYPE"]
