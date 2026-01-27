from __future__ import annotations
from typing import List, Optional, Union, Literal, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime, timezone
import uuid

# primitive patterns
ROR_PATTERN = r"^https://ror\.org/[0-9a-hjkmnp-z]{9}$"
ORCID_PATTERN = r"^https://orcid\.org/\d{4}-\d{4}-\d{4}-\d{3}[\dX]$"
IGSN_PATTERN = r"^igsn:[A-Za-z0-9./:-]{5,}$"

# content entity
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
    
    # helper to construct from strings
    @classmethod
    def create(cls, instrument_id: str, sample_id: str, method_id: str, params: dict):
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

# envelope entity
class AuthZ(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    type: Literal["DetachedJWS"] = "DetachedJWS"
    jws: str

class PCLEnvelope(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str = Field(alias="@id")
    type: Literal["PCLActionEnvelope"] = Field("PCLActionEnvelope", alias="@type")
    profile: str = "https://w3id.org/pcl-profile/action/v1"

    schema_: str = Field(
        "https://w3id.org/pcl-schema/measure-request/v1.0", 
        alias="schema"
    )

    identifier: str = Field(default_factory=lambda: f"urn:uuid:{uuid.uuid4()}")
    date_created: datetime = Field(default_factory=datetime.now(timezone.utc), alias="dateCreated")
    
    sender: str = Field(..., pattern=f"{ROR_PATTERN}|{ORCID_PATTERN}")
    receiver: str
    action: Literal["request_measurement", "register_data", "ack", "nack"]
    
    capabilities: List[str]
    project: str
    sample: str
    
    content_ref: Union[Dict[str, str], str] = Field(..., alias="contentRef")
    authz: Optional[AuthZ] = None

# root RO-crate
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

    def to_json(self):
        return self.model_dump_json(by_alias=True, indent=2)