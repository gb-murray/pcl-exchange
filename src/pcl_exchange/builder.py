from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .crypto import compute_content_digest
from .models import PCLMessage, PCLEnvelope, PCLActionContent, ROCrateMetadata, ROCrateRoot


class PCLMessageBuilder:
    def __init__(self, sender_id: str, receiver_id: str) -> None:
        self.sender: str = sender_id
        self.receiver: str = receiver_id
        self.envelope_uuid: str = f"urn:uuid:{uuid.uuid4()}"
        self.creation_timestamp: datetime = datetime.now(timezone.utc)
        self.payload: Optional[PCLActionContent] = None
        self.action_type: str = "request_measurement"
        self.capabilities: List[str] = []
        self.project_id: str = "doi:10.1234/placeholder"
        self.sample_id: str = ""
        self.authz: Optional[Dict[str, str]] = None
        self.respond_to: Optional[str] = None
        self.correlation_id: Optional[str] = None
        self.idempotency_key: Optional[str] = None
        self.ttl: Optional[str] = None
        self.deadline: Optional[datetime] = None
        self.priority: Optional[int] = None
        self.protocol_version: Optional[str] = None
        self.schema_hash: Optional[Dict[str, str]] = None
        self._sealed: bool = False

    def _check_not_sealed(self) -> None:
        if self._sealed:
            raise RuntimeError("Cannot modify builder after sign() has been called.")
        
    def set_content(
        self,
        instrument: str,
        sample: str,
        method: str,
        params: Dict[str, Dict[str, Any]]
    ) -> PCLMessageBuilder:
        self._check_not_sealed()
        self.sample_id = sample
        self.payload = PCLActionContent.create(
            instrument_id=instrument,
            sample_id=sample,
            method_id=method,
            params=params
        )
        return self

    def add_capability(self, capability: str) -> PCLMessageBuilder:
        self._check_not_sealed()
        self.capabilities.append(capability)
        return self

    def set_respond_to(self, respond_to: str) -> PCLMessageBuilder:
        self._check_not_sealed()
        self.respond_to = respond_to
        return self

    def set_correlation_id(self, correlation_id: str) -> PCLMessageBuilder:
        self._check_not_sealed()
        self.correlation_id = correlation_id
        return self

    def set_idempotency_key(self, idempotency_key: str) -> PCLMessageBuilder:
        self._check_not_sealed()
        self.idempotency_key = idempotency_key
        return self

    def set_ttl(self, ttl: str) -> PCLMessageBuilder:
        self._check_not_sealed()
        self.ttl = ttl
        return self

    def set_deadline(self, deadline: datetime) -> PCLMessageBuilder:
        self._check_not_sealed()
        self.deadline = deadline
        return self

    def set_priority(self, priority: int) -> PCLMessageBuilder:
        self._check_not_sealed()
        self.priority = priority
        return self

    def set_protocol_version(self, protocol_version: str) -> PCLMessageBuilder:
        self._check_not_sealed()
        self.protocol_version = protocol_version
        return self

    def set_schema_hash(self, alg: str, value: str) -> PCLMessageBuilder:
        self._check_not_sealed()
        self.schema_hash = {"alg": alg, "value": value}
        return self

    def _create_envelope_model(self, authz_data: Optional[Dict[str, str]] = None) -> PCLEnvelope:
        """
        Creates the PCLEnvelope model.
        """
        content_digest: Optional[Dict[str, Any]] = None
        if self.payload is not None:
            payload_data = self.payload.model_dump(mode="json", by_alias=True, exclude_none=True)
            content_digest = compute_content_digest(payload_data)

        envelope_data: Dict[str, Any] = {
            "id": "#envelope",
            "sender": self.sender,
            "receiver": self.receiver,
            "action": self.action_type,
            "capabilities": self.capabilities,
            "project": self.project_id,
            "sample": self.sample_id,
            "identifier": self.envelope_uuid,      # overrides default_factory=uuid
            "date_created": self.creation_timestamp, # overrides default_factory=datetime
            "contentRef": {"@id": "#content"},
            "contentDigest": content_digest,
            "authz": authz_data,
            "respondTo": self.respond_to,
            "correlationId": self.correlation_id,
            "idempotencyKey": self.idempotency_key,
            "ttl": self.ttl,
            "deadline": self.deadline,
            "priority": self.priority,
            "protocolVersion": self.protocol_version,
            "schemaHash": self.schema_hash
        }
        filtered_data = {key: value for key, value in envelope_data.items() if value is not None}

        return PCLEnvelope(**filtered_data)

    def sign(self, signer: Any) -> None:
        if self._sealed:
            raise RuntimeError("Cannot call sign() more than once for the same builder.")
        if self.payload is None:
            raise RuntimeError("Message content has not been set. Call set_content() before signing.")

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
        self._sealed = True

    def build(self) -> PCLMessage:
        """Finalizes the message construction and returns a PCLMessage instance."""
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