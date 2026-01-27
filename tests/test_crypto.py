from pcl_exchange.builder import PCLMessageBuilder
from pcl_exchange.crypto import Signer, Verifier

def test_signature_verification_success(key_pair, builder_defaults, valid_payload_data):
    """A correctly signed message should verify True."""
    
    # build and sign the message
    builder = PCLMessageBuilder(**builder_defaults)
    builder.set_content(**valid_payload_data)
    signer = Signer(private_key=key_pair) 
    builder.sign(signer)
    message = builder.build()
    
    # verify signature and envelope
    verifier = Verifier(public_key=key_pair) 
    
    envelope = next(item for item in message.graph if item.id == "#envelope")
    assert verifier.verify(envelope) is True

def test_tampered_payload_fails(key_pair, builder_defaults, valid_payload_data):
    """Modifying the payload after signing should cause verification to fail."""
    
    # build and sign the message
    builder = PCLMessageBuilder(**builder_defaults)
    builder.set_content(**valid_payload_data)
    signer = Signer(private_key=key_pair)
    builder.sign(signer)
    message = builder.build()
    
    # change the payload
    content_node = next(item for item in message.graph if item.id == "#content")
    content_node.instrument["@id"] = "urn:malicious:instrument"
    
    # verify signature and envelope
    verifier = Verifier(public_key=key_pair)
    envelope = next(item for item in message.graph if item.id == "#envelope")
    
    # should fail because the envelope signature covers the content hash
    assert verifier.verify(envelope) is False