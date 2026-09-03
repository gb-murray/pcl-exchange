import json
import socket
from typing import Any, Dict

from pytest_httpserver import HTTPServer

from pcl_exchange.builder import PCLMessageBuilder, build_ack, build_nack
from pcl_exchange.callback import CallbackClient
from pcl_exchange.models import PCLEnvelope, PCLErrorCode


def _build_original_envelope(builder_defaults: Dict[str, str], valid_payload_data: Dict[str, Any]) -> PCLEnvelope:
    builder = PCLMessageBuilder(**builder_defaults)
    builder.set_content(**valid_payload_data)
    builder.add_capability("xrd.powder.theta-2theta")
    message = builder.build()
    return next(item for item in message.graph if isinstance(item, PCLEnvelope))


def _unused_port() -> int:
    """Binds an ephemeral port then releases it, guaranteeing nothing is listening on it."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_send_ack_posts_expected_body_and_headers(
    httpserver: HTTPServer,
    builder_defaults: Dict[str, str],
    valid_payload_data: Dict[str, Any],
) -> None:
    original = _build_original_envelope(builder_defaults, valid_payload_data)
    ack = build_ack(original, job_id="job-12345678")
    httpserver.expect_request("/hooks/ack", method="POST").respond_with_data("", status=200)

    client = CallbackClient(max_attempts=3, backoff_base=0.01)
    result = client.send(httpserver.url_for("/hooks/ack"), ack)

    assert result.success
    assert result.attempts == 1

    request = httpserver.log[0][0]
    assert request.headers["Content-Type"] == "application/ld+json"
    body = json.loads(request.get_data(as_text=True))
    envelope_node = next(item for item in body["@graph"] if item.get("@id") == "#envelope")
    assert envelope_node["action"] == "ack"
    assert envelope_node["identifier"] == "job-12345678"


def test_send_nack_posts_envelope_and_error_nodes(
    httpserver: HTTPServer,
    builder_defaults: Dict[str, str],
    valid_payload_data: Dict[str, Any],
) -> None:
    original = _build_original_envelope(builder_defaults, valid_payload_data)
    nack_envelope, error = build_nack(original, code=PCLErrorCode.SCHEMA_MISMATCH, reason="bad envelope")
    httpserver.expect_request("/hooks/nack", method="POST").respond_with_data("", status=200)

    client = CallbackClient(max_attempts=3, backoff_base=0.01)
    result = client.send(httpserver.url_for("/hooks/nack"), nack_envelope, content=error)

    assert result.success
    body = json.loads(httpserver.log[0][0].get_data(as_text=True))
    node_ids = {item.get("@id") for item in body["@graph"]}
    assert "#envelope" in node_ids
    assert "#error" in node_ids


def test_transient_status_retries_then_succeeds(
    httpserver: HTTPServer,
    builder_defaults: Dict[str, str],
    valid_payload_data: Dict[str, Any],
) -> None:
    original = _build_original_envelope(builder_defaults, valid_payload_data)
    ack = build_ack(original)
    httpserver.expect_ordered_request("/hooks/ack", method="POST").respond_with_data("", status=503)
    httpserver.expect_ordered_request("/hooks/ack", method="POST").respond_with_data("", status=503)
    httpserver.expect_ordered_request("/hooks/ack", method="POST").respond_with_data("", status=200)

    client = CallbackClient(max_attempts=3, backoff_base=0.01)
    result = client.send(httpserver.url_for("/hooks/ack"), ack)

    assert result.success
    assert result.attempts == 3


def test_transient_status_exhausts_retries_maps_to_temporary_failure(
    httpserver: HTTPServer,
    builder_defaults: Dict[str, str],
    valid_payload_data: Dict[str, Any],
) -> None:
    original = _build_original_envelope(builder_defaults, valid_payload_data)
    ack = build_ack(original)
    httpserver.expect_request("/hooks/ack", method="POST").respond_with_data("", status=503)

    client = CallbackClient(max_attempts=3, backoff_base=0.01)
    result = client.send(httpserver.url_for("/hooks/ack"), ack)

    assert not result.success
    assert result.attempts == 3
    assert result.error is not None
    assert result.error.code == PCLErrorCode.TEMPORARY_FAILURE
    assert result.error.retriable is True


def test_non_transient_status_fails_fast_as_internal_error(
    httpserver: HTTPServer,
    builder_defaults: Dict[str, str],
    valid_payload_data: Dict[str, Any],
) -> None:
    original = _build_original_envelope(builder_defaults, valid_payload_data)
    ack = build_ack(original)
    httpserver.expect_request("/hooks/ack", method="POST").respond_with_data("", status=400)

    client = CallbackClient(max_attempts=3, backoff_base=0.01)
    result = client.send(httpserver.url_for("/hooks/ack"), ack)

    assert not result.success
    assert result.attempts == 1
    assert result.error is not None
    assert result.error.code == PCLErrorCode.INTERNAL_ERROR
    assert result.error.http_status == 400
    assert result.error.retriable is False


def test_connection_error_exhausts_retries_maps_to_temporary_failure(
    builder_defaults: Dict[str, str],
    valid_payload_data: Dict[str, Any],
) -> None:
    original = _build_original_envelope(builder_defaults, valid_payload_data)
    ack = build_ack(original)
    unreachable_url = f"http://127.0.0.1:{_unused_port()}/hooks/ack"

    client = CallbackClient(max_attempts=2, backoff_base=0.01, timeout=1.0)
    result = client.send(unreachable_url, ack)

    assert not result.success
    assert result.attempts == 2
    assert result.error is not None
    assert result.error.code == PCLErrorCode.TEMPORARY_FAILURE
