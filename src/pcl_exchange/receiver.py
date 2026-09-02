from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from jwcrypto import jwk
from pydantic import BaseModel, Field

from .crypto import Verifier
from .validation import validate_structure

CrateInput = Union[Dict[str, Any], str, Path]
PublicKeyResolver = Callable[[str], Union[jwk.JWK, Dict[str, Any]]]


class CrateError(BaseModel):
    code: str
    message: str


class CrateParseResult(BaseModel):
    valid: bool
    envelope: Optional[Dict[str, Any]] = None
    content: Optional[Dict[str, Any]] = None
    errors: List[CrateError] = Field(default_factory=list)


def _load_crate(crate_json_or_path: CrateInput) -> Union[Dict[str, Any], CrateError]:
    """Resolve dict/path/JSON-string input into a parsed crate dict."""
    if isinstance(crate_json_or_path, dict):
        return crate_json_or_path

    if isinstance(crate_json_or_path, Path):
        path: Optional[Path] = crate_json_or_path
    else:
        candidate = Path(crate_json_or_path)
        path = candidate if candidate.is_file() else None

    if path is not None:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as e:
            return CrateError(code="INVALID_JSON", message=f"Failed to read crate file '{path}': {e}")
    else:
        text = crate_json_or_path

    try:
        data: Any = json.loads(text)
    except json.JSONDecodeError as e:
        return CrateError(code="INVALID_JSON", message=f"Invalid JSON: {e}")

    if not isinstance(data, dict):
        return CrateError(code="INVALID_JSON", message="Crate JSON must be an object")

    return data


def _resolve_node_ref(value: Any) -> Optional[str]:
    """Extract an @id string from either a {'@id': ...} ref or a bare string."""
    if isinstance(value, dict):
        ref_id = value.get("@id")
        return ref_id if isinstance(ref_id, str) else None
    if isinstance(value, str):
        return value
    return None


def verify_envelope_signature(
    envelope: Dict[str, Any], public_key_resolver: PublicKeyResolver
) -> Tuple[bool, Optional[CrateError]]:
    """Verify an envelope's DetachedJWS 'authz' signature using a sender-keyed resolver."""
    sender_id = _resolve_node_ref(envelope.get("sender"))
    if sender_id is None:
        return False, CrateError(code="MISSING_SENDER", message="Envelope is missing a resolvable 'sender'")

    authz = envelope.get("authz")
    if not isinstance(authz, dict):
        return False, CrateError(code="MISSING_SIGNATURE", message="Envelope is missing an 'authz' block")

    authz_type = authz.get("type")
    if authz_type != "DetachedJWS":
        return False, CrateError(
            code="UNSUPPORTED_AUTHZ_TYPE",
            message=f"authz type '{authz_type}' cannot be verified; only 'DetachedJWS' is supported",
        )

    if not authz.get("jws"):
        return False, CrateError(code="MISSING_SIGNATURE", message="authz.jws is missing or empty")

    try:
        public_key = public_key_resolver(sender_id)
    except (LookupError) as e:
        return False, CrateError(code="UNKNOWN_SENDER_KEY", message=f"No public key found for sender '{sender_id}': {e}")

    verifier = Verifier(public_key)
    if not verifier.verify(envelope):
        return False, CrateError(code="INVALID_SIGNATURE", message="Envelope signature verification failed")

    return True, None


def parse_and_validate_crate(
    crate_json_or_path: CrateInput, public_key_resolver: PublicKeyResolver
) -> CrateParseResult:
    """Load a PCL RO-Crate, extract the envelope/content nodes, and validate structure + signature."""
    loaded = _load_crate(crate_json_or_path)
    if isinstance(loaded, CrateError):
        return CrateParseResult(valid=False, errors=[loaded])

    graph = loaded.get("@graph")
    if not isinstance(graph, list):
        return CrateParseResult(
            valid=False,
            errors=[CrateError(code="MISSING_GRAPH", message="Crate is missing a top-level '@graph' array")],
        )

    envelope = next((node for node in graph if isinstance(node, dict) and node.get("@id") == "#envelope"), None)
    if envelope is None:
        return CrateParseResult(
            valid=False,
            errors=[CrateError(code="MISSING_ENVELOPE", message="No node with @id '#envelope' found in @graph")],
        )

    errors: List[CrateError] = []

    schema_valid, schema_error = validate_structure(envelope)
    if not schema_valid:
        errors.append(
            CrateError(code="SCHEMA_VALIDATION_ERROR", message=schema_error or "Envelope failed schema validation")
        )

    content_ref_id = _resolve_node_ref(envelope.get("contentRef"))
    content: Optional[Dict[str, Any]] = None
    if content_ref_id is None:
        errors.append(CrateError(code="MISSING_CONTENT_REF", message="Envelope is missing a resolvable 'contentRef'"))
    else:
        content = next(
            (node for node in graph if isinstance(node, dict) and node.get("@id") == content_ref_id), None
        )
        if content is None:
            errors.append(
                CrateError(
                    code="CONTENT_NOT_FOUND", message=f"No node with @id '{content_ref_id}' found in @graph"
                )
            )

    signature_valid, signature_error = verify_envelope_signature(envelope, public_key_resolver)
    if not signature_valid and signature_error is not None:
        errors.append(signature_error)

    return CrateParseResult(valid=not errors, envelope=envelope, content=content, errors=errors)
