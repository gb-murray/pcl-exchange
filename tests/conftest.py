import pytest
from jwcrypto import jwk

@pytest.fixture(scope="session")
def key_pair():
    """
    Generates a temporary Ed25519 key pair for testing signatures.
    """
    key = jwk.JWK.generate(kty='OKP', crv='Ed25519')
    return key

@pytest.fixture
def valid_payload_data():
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
def builder_defaults():
    return {
        "sender_id": "https://ror.org/03yrm5c26",
        "receiver_id": "https://ror.org/01bj3aw27"
    }