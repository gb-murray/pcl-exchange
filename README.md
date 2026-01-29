# PCL Exchange Data Model using RO-Crate Profile, Schemas, and Shapes
<a href="https://github.com/htmdec/pcl-exchange" target="_blank" rel="noopener noreferrer">
  <img width="191" height="20" alt="image" src="https://github.com/user-attachments/assets/d7aafa45-ba2c-452a-adef-2132b839d49e" />
</a>



This repository captures the MADICES Week conception for a minimal, interoperable PCL-to-PCL exchange pattern.  
It benefited from conversations with Peter Kraus (TU Berlin), Matthew Evans (Cambridge), and Simon Stier (Fraunhofer).

It uses:

- RO-Crate as the packaging and JSON-LD context carrier  
- JSON Schema for validating the *envelope* and *error contract*  
- SHACL shapes for validating *content nodes* such as measurement requests and workflow launches  

--

## Overview

The goal of this work is to define a **minimum viable contract** for structured, machine-actionable exchange between programmable cloud laboratories (PCLs).  
It aims to balance minimalism with interoperability, enabling autonomous or semi-autonomous lab-to-lab operations using well-established web standards and persistent identifiers (PIDs).

--

## What is the Minimum Viable Contract for a Receiving PCL?

*(Reflective question: Can the following list be minimized?)*

### 1. Who and Where
- Identifiers for sending PCL (**ROR**), person (**ORCID**), and public key reference (**DID**)
- Intended receiver identifier (**ROR**) *(maybe? not sure really)*  
- Stable message ID, creation time, and protocol/profile version

### 2. Payload Understandability
- Canonical schema identifier and version for the payload body
- Encoding and optional compression or encryption info *(?)*
- Content checksum for verification check

### 3. Intent (What to Do with the Content)
- Action verb from a **closed vocabulary**, e.g.  
  `register_data`, `request_measurement`, `launch_workflow`, `update_metadata`, `cancel_job`  
  *(Reflective: can we agree a simple schema or can this be done by context interpretation?)*
- Minimal capability requirement expressed as a **feature tag**, e.g.  
  `capability: xrd/powder/θ–2θ`, `workflow: cwl@v1.2`

### 4. About Which Research Object
- Project PID (**DataCite DOI** or **RAiD**)
- Sample PID (**IGSN**)
- Optional: workflow, instrument, and facility identifiers

### 5. Authorization
- Token or other credential with defined scope
- Data use constraints *(there will be users who want their data to be private; may need an ontology for the options so a receiver can decide if they can honor the constraints)*

### 6. Routing and Responses
- Acknowledge receipt with a callback channel
- Schedule constraints such as deadline and priority

### 7. Provenance Crumbs
- Who constructed the payload
- When
- From which upstream artifacts

--

## Optional Additions for Version 2

*(Reflective: Not necessary but useful?)*

- Version negotiation workflows  
- Replay protection for action requests  
- Validation hooks (JSON Schema or SHACL shape URI)  
- Explicit time zone and units  
- Error contract  
- Data sensitivity tagging  

--

## Ontology Stack

**Do not** invent a new ontology.  
Compose a small, interoperable stack and use an **RO-Crate Profile** to bundle it.

- **RO-Crate** as the container and JSON-LD context carrier, with a profile URI that says “this is a PCL-to-PCL action crate.”
- **W3C PROV-O** for provenance of the message and any included data or workflow
- **schema.org** types for high-level objects (`Dataset`, `SoftwareSourceCode`, `CreativeWork`)
- **CWL**, **CWLProv**, or **WfProv/WfDesc** for workflows and runs when the intent is to execute
- **Persistent Identifiers (PIDs):**
  - Project: DOI or RAiD
  - Sample: IGSN
  - People: ORCID
  - Organizations: ROR
  - Instruments or facilities: PIDInst (DataCite) and RRID
  - Units: QUDT or OM for quantities and units
  - Verifiable credentials: W3C Verifiable Credentials / Presentations
  - Data use policy: ODRL (Open Digital Rights Language)
- **Events:** map the envelope to **CloudEvents** fields so you can move it over Kafka, NATS, or HTTP consistently.

--

## Two Layers Inside the RO-Crate

The RO-Crate structure for PCL exchange consists of **two distinct layers**:

### 1. Envelope Entity (Machine Routing and Validation)
Defines the outer envelope that carries metadata required for validation and routing.

| Field | Description |
|-----|----------|
| `type` | `PCLActionEnvelope` (a profile class) |
| `profile` | URI of the RO-Crate profile |
| `id`, `time`, `sender`, `receiver` | Identification and timing info |
| `schema` | URI for the body schema and version |
| `hash`, `size`, `encoding`, `encryption` | Verification and transfer info |
| `action` | Controlled vocabulary term |
| `capabilities` | List of required features |
| `authz` | JWT in detached JWS form, or a Verifiable Presentation reference |

### 2. Content Entity (Domain Payload)
The payload itself, typically one of the following:

| Use Case | Entity Type | Key Fields |
|--------|----------|--------|
| **Data Registration** | `Dataset` | Distributions, checksums, and PIDs, plus PROV links |
| **Workflow Launch** | `SoftwareSourceCode` or `ComputationalWorkflow` | CWL file, parameters, optional tool references |
| **Measurement Request** | `Action` | Instrument, sample, method, parameters, and acceptance criteria |

--

## Example PCL Exchange Message (JSON-LD)

```json
{
  "@context": [
    "https://w3id.org/ro/crate/1.1/context",
    {
      "prov": "http://www.w3.org/ns/prov#",
      "qudt": "http://qudt.org/schema/qudt/",
      "parameter": "http://schema.org/parameter",
      "unitText": "http://schema.org/unitText"
    }
  ],
  "@graph": [
    {
      "@id": "ro-crate-metadata.json",
      "@type": "CreativeWork",
      "about": { "@id": "./" },
      "conformsTo": { "@id": "https://w3id.org/ro/crate/1.1" },
      "identifier": "ro-crate-metadata.json",
      "name": "RO-Crate Metadata",
      "text": "Metadata descriptor for PCL Exchange"
    },
    {
      "@id": "./",
      "@type": "Dataset",
      "hasPart": [
        { "@id": "#envelope" },
        { "@id": "#content" }
      ]
    },
    {
      "@id": "#envelope",
      "@type": "PCLActionEnvelope",
      "profile": "https://w3id.org/pcl-profile/action/v1",
      "schema": "https://w3id.org/pcl-schema/measure-request/v1.0",
      "identifier": "urn:uuid:6fc2f305-ce1e-4059-890d-428428b979dd",
      "dateCreated": "2026-01-29T16:10:49.713657Z",
      "sender": "https://ror.org/03yrm5c26",
      "receiver": "https://ror.org/01bj3aw27",
      "action": "request_measurement",
      "capabilities": ["xrd.powder.theta-2theta"],
      "project": "doi:10.1234/placeholder",
      "sample": "igsn:XYZ12345",
      "contentRef": { "@id": "#content" },
      "authz": {
        "type": "DetachedJWS",
        "jws": "eyJhbGciOiJFZERTQSJ9..[SIGNATURE_GOES_HERE]"
      }
    },
    {
      "@id": "#content",
      "@type": "Action",
      "instrument": { "@id": "urn:aimd:instrument:proto-xrd-01" },
      "object": { "@id": "igsn:XYZ12345" },
      "prov:used": { "@id": "urn:aimd:method:xrd:powder:theta-2theta:v1" },
      "parameter": [
        {
          "@type": "PropertyValue",
          "name": "scan_range",
          "value": "10 90",
          "unitText": "deg 2theta"
        },
        {
          "@type": "PropertyValue",
          "name": "step",
          "value": 0.02,
          "unitText": "deg"
        }
      ]
    }
  }
}
