import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Union
from jwcrypto import jws, jwk
from jwcrypto.common import json_encode

logger = logging.getLogger(__name__)


def _drop_none(data: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in data.items() if value is not None}

def canonicalize(data: Dict[str, Any]) -> bytes:
    """Prepares a dictionary for signing/hashing by ensuring a consistent string representation (JCS-like)."""

    clean_data = _drop_none(data.copy())
    clean_data.pop("authz", None)

    return json.dumps(
        clean_data,
        sort_keys=True,
        separators=(',', ':'),
        ensure_ascii=False
    ).encode('utf-8')


class Signer:
    """
    Handles cryptographic signing using a private key.
    """
    def __init__(self, private_key: Union[jwk.JWK, dict]):
        """
        Args:
            private_key: A jwcrypto.jwk.JWK object or a dict representing the key.
        """
        if isinstance(private_key, dict):
            self.key = jwk.JWK(**private_key)
        else:
            self.key = private_key

    def sign(self, payload: Dict[str, Any]) -> str:
        """
        Generates a Detached JWS for the given payload dictionary.
        
        Args:
            payload: The dictionary (Envelope) to sign.
            
        Returns:
            str: The serialized JWS (Compact Serialization).
        """

        payload_bytes = canonicalize(payload)
        signer = jws.JWS(payload_bytes)
        signer.add_signature(
            self.key, 
            protected=json_encode({"alg": "EdDSA"})
        )
        
        full_jws = signer.serialize(compact=True)
        header, payload, signature = full_jws.split('.')
        
        return f"{header}..{signature}"


class Verifier:
    """
    Handles cryptographic verification using a public key.
    """
    def __init__(self, public_key: Union[jwk.JWK, dict]):
        if isinstance(public_key, dict):
            self.key = jwk.JWK(**public_key)
        else:
            self.key = public_key

    def verify(self, envelope_model) -> bool:
        """
        Verifies the 'authz.jws' signature against the Envelope fields.
        
        Args:
            envelope_model: An instance of PCLEnvelope (or a dict equivalent).
            
        Returns:
            True if valid, False otherwise.
        """
        signature_str = ''
        try:
            if hasattr(envelope_model, 'model_dump'):
                data = envelope_model.model_dump(by_alias=True, mode='json')
            else:
                data = envelope_model
            
            if not isinstance(data, dict) or 'authz' not in data or not isinstance(data.get('authz'), dict) or not data['authz'].get('jws'):
                logger.warning("Verification failed: No signature found in the envelope.")
                return False
                
            signature_str = str(data.get('authz', {}).get('jws', '')).strip()
           
            expected_payload = canonicalize(data)
            
            verifier = jws.JWS()            
            verifier.deserialize(signature_str)
            verifier.verify(self.key, detached_payload=expected_payload)
            
            return True
            
        except jws.InvalidJWSSignature:
            logger.warning("Verification failed: Signature does not match.")
            return False
        except Exception as e:
            logger.error(f"An unexpected error occurred during verification: {e}")
            return False