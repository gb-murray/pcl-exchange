from __future__ import annotations
from typing import List, Optional, Union, Literal, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime, timezone
import uuid

ROR_PATTERN = r"^https://ror\.org/[0-9a-hjkmnp-z]{9}$"
ORCID_PATTERN = r"^https://orcid\.org/\d{4}-\d{4}-\d{4}-\d{3}[\dX]$"
IGSN_PATTERN = r"^igsn:[A-Za-z0-9./:-]{5,}$"
PROTOCOL_VERSION_DEFAULT = "0.1.1"

class PropertyValue(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    type: Literal["PropertyValue"] = Field("PropertyValue", alias="@type")
    name: str
    value: Union[str, float, int]
    unit_text: Optional[str] = Field(None, alias="unitText")
    
class PCLActionContent(BaseModel):
    """Represents the domain payload"""
    model_config = ConfigDict(populate_by_name=True)
    id: str = Field(alias="@id")
    type: Literal["Action"] = Field("Action", alias="@type")
    instrument: Dict[str, str] = Field(..., description="Pointer to Instrument IRI")
    object: Dict[str, str] = Field(..., description="Pointer to Sample (IGSN)")
    used: Dict[str, str] = Field(..., alias="prov:used", description="Pointer to Method")
    parameters: List[PropertyValue] = Field(..., alias="parameter")
    
    @classmethod
    def create(
        cls,
        instrument_id: str,
        sample_id: str,
        method_id: str,
        params: Dict[str, Dict[str, Any]]
    ) -> PCLActionContent:
        p_list = [
            PropertyValue(name=k, value=v["val"], unit_text=v.get("unit")) 
            for k, v in params.items()
        ]
        return cls(
            id="#content",
            instrument={"@id": instrument_id},
            object={"@id": sample_id},
            used={"@id": method_id},
            parameter=p_list
        )

class AuthZ(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    type: Literal["DetachedJWS"] = "DetachedJWS"
    jws: str

class PCLEnvelope(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")
    id: str = Field(alias="@id")
    type: Literal["PCLActionEnvelope"] = Field("PCLActionEnvelope", alias="@type")
    profile: str = "https://w3id.org/pcl-profile/action/v1"

    schema_: str = Field(
        "https://w3id.org/pcl-schema/measure-request/v1.0", 
        alias="schema"
    )

    identifier: str = Field(default_factory=lambda: f"urn:uuid:{uuid.uuid4()}")
    date_created: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), alias="dateCreated")
    
    sender: str = Field(..., pattern=f"{ROR_PATTERN}|{ORCID_PATTERN}")
    receiver: str
    action: Literal[
        "register_data",
        "request_measurement",
        "launch_workflow",
        "update_metadata",
        "cancel_job",
        "ack",
        "nack"
    ]
    
    capabilities: List[str]
    project: str
    sample: str
    
    content_ref: Union[Dict[str, str], str] = Field(..., alias="contentRef")
    authz: AuthZ = None

    respond_to: Optional[str] = Field(None, alias="respondTo")
    ttl: Optional[str] = None
    deadline: Optional[datetime] = None
    priority: Optional[int] = None
    correlation_id: Optional[str] = Field(None, alias="correlationId")
    idempotency_key: Optional[str] = Field(None, alias="idempotencyKey")
    protocol_version: Optional[str] = Field(PROTOCOL_VERSION_DEFAULT, alias="protocolVersion")
    schema_hash: Optional[Dict[str, str]] = Field(None, alias="schemaHash")

class PCLErrorCode(str, Enum):
    INVALID_ENVELOPE = "INVALID_ENVELOPE"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    SCHEMA_MISMATCH = "SCHEMA_MISMATCH"
    UNSUPPORTED_ACTION = "UNSUPPORTED_ACTION"
    CAPABILITY_MISMATCH = "CAPABILITY_MISMATCH"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    RATE_LIMITED = "RATE_LIMITED"
    TEMPORARY_FAILURE = "TEMPORARY_FAILURE"
    INTERNAL_ERROR = "INTERNAL_ERROR"

class PCLErrorFault(BaseModel):
    """Describes a single validation or processing fault."""
    model_config = ConfigDict(populate_by_name=True)
    path: Optional[str] = None
    schema: Optional[str] = None
    message: str

class PCLError(BaseModel):
    """Structured error response for PCL action processing."""
    model_config = ConfigDict(populate_by_name=True)
    type: Literal["https://w3id.org/pcl-profile/action/v1#Error"] = (
        "https://w3id.org/pcl-profile/action/v1#Error"
    )
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    code: PCLErrorCode
    reason: str
    correlation_id: Optional[str] = Field(None, alias="correlationId")
    idempotency_key: Optional[str] = Field(None, alias="idempotencyKey")
    http_status: Optional[int] = Field(None, alias="httpStatus")
    retriable: Optional[bool] = False
    retry_after: Optional[Union[int, datetime]] = Field(None, alias="retryAfter")
    faults: Optional[List[PCLErrorFault]] = None
    details: Optional[Dict[str, Any]] = None

class ROCrateMetadata(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str = Field("ro-crate-metadata.json", alias="@id")
    type: Literal["CreativeWork"] = Field("CreativeWork", alias="@type")
    about: Dict[str, str] = Field({"@id": "./"}, alias="about")
    conformsTo: Dict[str, str] = Field({"@id": "https://w3id.org/ro/crate/1.1"}, alias="conformsTo")

    identifier: str = "ro-crate-metadata.json"
    name: str = "RO-Crate Metadata"
    text: str = Field("Metadata descriptor for PCL Exchange", alias="text")

class ROCrateRoot(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str = Field("./", alias="@id")
    type: Literal["Dataset"] = Field("Dataset", alias="@type")
    hasPart: List[Dict[str, str]] = [{"@id": "#envelope"}, {"@id": "#content"}]

class PCLMessage(BaseModel):
    """The full JSON-LD document"""
    model_config = ConfigDict(populate_by_name=True)
    context: List[Any] = Field(..., alias="@context")
    graph: List[Union[ROCrateMetadata, ROCrateRoot, PCLEnvelope, PCLActionContent, Dict[str, Any]]] = Field(..., alias="@graph")

    def to_json(self) -> str:
        return self.model_dump_json(by_alias=True, indent=2, exclude_none=True)