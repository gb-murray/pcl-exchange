from pcl_exchange.builder import PCLMessageBuilder
from pcl_exchange.crypto import Signer, Verifier

def test_signature_verification_success(key_pair, builder_defaults, valid_payload_data):
    """A correctly signed message should verify True."""
    builder = PCLMessageBuilder(**builder_defaults)
    builder.set_content(**valid_payload_data)
    signer = Signer(private_key=key_pair) 
    builder.sign(signer)
    message = builder.build()
    
    verifier = Verifier(public_key=key_pair) 
    
    envelope = next(item for item in message.graph if item.id == "#envelope")
    assert verifier.verify(envelope) is True

def test_tampered_payload_fails(key_pair, builder_defaults, valid_payload_data):
    """Modifying signed envelope metadata after signing should cause verification to fail."""
    builder = PCLMessageBuilder(**builder_defaults)
    builder.set_content(**valid_payload_data)
    signer = Signer(private_key=key_pair)
    builder.sign(signer)
    message = builder.build()
    
    envelope_node = next(item for item in message.graph if item.id == "#envelope")
    envelope_node.receiver = "https://ror.org/000000000"
    
    verifier = Verifier(public_key=key_pair)
    envelope = envelope_node
    
    assert verifier.verify(envelope) is False