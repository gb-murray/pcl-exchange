import json
import logging
from typing import Dict, Any, Union
from jwcrypto import jws, jwk
from jwcrypto.common import json_encode

logger = logging.getLogger(__name__)

def canonicalize(data: Dict[str, Any]) -> bytes:
    """
    Prepares a dictionary for signing/hashing by ensuring a 
    consistent string representation (JCS-like).
    
    1. Removes 'authz' field (since that holds the signature).
    2. Sorts keys.
    3. Removes whitespace (separators=(',', ':')).
    """
    
    clean_data = data.copy()
    
    # remove 'authz' if present
    if 'authz' in clean_data:
        del clean_data['authz']
        
    # JSON canonicalization
    return json.dumps(clean_data, sort_keys=True, separators=(',', ':'),ensure_ascii=False).encode('utf-8')

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
        # canonicalize the data
        payload_bytes = canonicalize(payload)
        
        # create JWS object
        # uses EdDSA by default
        signer = jws.JWS(payload_bytes)
        
        # add signature
        signer.add_signature(
            self.key, 
            protected=json_encode({"alg": "EdDSA"})
        )
        
        # serialize to compact form
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
            # extract the JWS signature
            if hasattr(envelope_model, 'model_dump'):
                data = envelope_model.model_dump(by_alias=True)
            else:
                data = envelope_model
            
            if 'authz' not in data or not data['authz'].get('jws'):
                logger.warning("Verification failed: No signature found in the envelope.")
                return False
                
            signature_str = str(data['authz']['jws']).strip()
            
            # prepare the payload for verification
            expected_payload = canonicalize(data)
            
            # verify the JWS
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