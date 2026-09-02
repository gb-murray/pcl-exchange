import json
from pathlib import Path
from typing import Any, Dict

import pytest
from jwcrypto import jwk

@pytest.fixture(scope="session")
def key_pair() -> jwk.JWK:
    """
    Generates a temporary Ed25519 key pair for testing signatures.
    """
    key = jwk.JWK.generate(kty='OKP', crv='Ed25519')
    return key

@pytest.fixture
def valid_payload_data() -> Dict[str, Any]:
    """
    Returns the dictionary of parameters needed to build a valid XRD request.
    """
    return {
        "instrument": "urn:aimd:instrument:proto-xrd-01",
        "sample": "igsn:XYZ12345",
        "method": "urn:aimd:method:xrd:powder:theta-2theta:v1",
        "params": {
            "scan_range": {"val": "10 90", "unit": "deg 2theta"},
            "step": {"val": 0.02, "unit": "deg"}
        }
    }

@pytest.fixture
def builder_defaults() -> Dict[str, str]:
    return {
        "sender_id": "https://ror.org/03yrm5c26",
        "receiver_id": "https://ror.org/01bj3aw27"
    }


@pytest.fixture(scope="session")
def example_action_crate() -> Dict[str, Any]:
    path = Path("examples") / "pcl_action_crate_example.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def example_sender_public_key() -> jwk.JWK:
    """Public key matching the DetachedJWS signature committed in pcl_action_crate_example.json."""
    return jwk.JWK(**{"crv": "Ed25519", "kty": "OKP", "x": "71FUvybwttZv-9IFCeyqnXaJd-Fhj7n8nal3-MB9Mnk"})