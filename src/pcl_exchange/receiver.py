from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

from .validation import validate_structure

CrateInput = Union[Dict[str, Any], str, Path]


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
        text = crate_json_or_path if isinstance(crate_json_or_path, str) else ""

    try:
        data: Any = json.loads(text)
    except json.JSONDecodeError as e:
        return CrateError(code="INVALID_JSON", message=f"Invalid JSON: {e}")

    if not isinstance(data, dict):
        return CrateError(code="INVALID_JSON", message="Crate JSON must be an object")

    return data


def _resolve_content_ref_id(content_ref: Any) -> Optional[str]:
    if isinstance(content_ref, dict):
        ref_id = content_ref.get("@id")
        return ref_id if isinstance(ref_id, str) else None
    if isinstance(content_ref, str):
        return content_ref
    return None


def parse_and_validate_crate(crate_json_or_path: CrateInput) -> CrateParseResult:
    """Load a PCL RO-Crate, extract the envelope/content nodes, and validate the envelope structure."""
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

    content_ref_id = _resolve_content_ref_id(envelope.get("contentRef"))
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

    return CrateParseResult(valid=not errors, envelope=envelope, content=content, errors=errors)
