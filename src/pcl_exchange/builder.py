import uuid
from datetime import datetime, timezone
from .models import PCLMessage, PCLEnvelope, PCLActionContent, ROCrateMetadata, ROCrateRoot

class PCLMessageBuilder:
    def __init__(self, sender_id: str, receiver_id: str):
        self.sender = sender_id
        self.receiver = receiver_id
        self.envelope_uuid = f"urn:uuid:{uuid.uuid4()}"
        self.creation_timestamp = datetime.now(timezone.utc)        
        self.payload = None
        self.action_type = "request_measurement"
        self.capabilities = []
        self.project_id = "doi:10.1234/placeholder" 
        self.sample_id = ""
        self.authz = None 
        
    def set_content(self, instrument: str, sample: str, method: str, params: dict):
        self.sample_id = sample
        self.payload = PCLActionContent.create(
            instrument_id=instrument,
            sample_id=sample,
            method_id=method,
            params=params
        )
        return self

    def add_capability(self, capability: str):
        self.capabilities.append(capability)
        return self

    def _create_envelope_model(self, authz_data=None) -> PCLEnvelope:
        """
        Creates the PCLEnvelope model.
        """
        return PCLEnvelope(
            id="#envelope",
            sender=self.sender,
            receiver=self.receiver,
            action=self.action_type,
            capabilities=self.capabilities,
            project=self.project_id,
            sample=self.sample_id,
            identifier=self.envelope_uuid,      # overrides default_factory=uuid
            date_created=self.creation_timestamp, # overrides default_factory=datetime    
            contentRef={"@id": "#content"},
            authz=authz_data
        )

    def sign(self, signer):
        temp_envelope = self._create_envelope_model(authz_data=None)
        envelope_data = temp_envelope.model_dump(
            mode='json', 
            by_alias=True, 
            exclude_none=True
        )
        
        jws_string = signer.sign(envelope_data)
        
        self.authz = {
            "type": "DetachedJWS",
            "jws": jws_string
        }

    def build(self) -> PCLMessage:
        if not self.payload:
            raise ValueError("Message content has not been set. Call set_content() before building.")

        envelope = self._create_envelope_model(authz_data=self.authz)
        
        graph_items = [
            ROCrateMetadata(),
            ROCrateRoot(),
            envelope,
            self.payload
        ]
        
        context = [
            "https://w3id.org/ro/crate/1.1/context",
            {
                "prov": "http://www.w3.org/ns/prov#", 
                "qudt": "http://qudt.org/schema/qudt/",
                "parameter": "http://schema.org/parameter",
                "unitText": "http://schema.org/unitText"
            }
        ]
        
        return PCLMessage(context=context, graph=graph_items)