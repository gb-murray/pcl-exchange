import json
import importlib.resources
from typing import Union, Dict, Tuple, Optional

from rdflib import Graph
from pyshacl import validate
import jsonschema

from . import schemas

def get_schema_text(filename: str) -> str:
    """
    Helper to read a schema file from inside the package.
    Example: get_schema_text('envelope.json')
    """
    try:
        parts = filename.split('/')
        resource = importlib.resources.files(schemas)
        for part in parts:
            resource = resource / part
        return resource.read_text(encoding='utf-8')
    except FileNotFoundError:
        raise FileNotFoundError(f"Schema file '{filename}' not found in package resources.")

def validate_structure(data: Dict, schema_filename: str = "envelope.json") -> Tuple[bool, Optional[str]]:
    """
    Validates the pure JSON structure against the JSON Schema.
    
    Returns:
        (True, None) if valid
        (False, error_message) if invalid
    """
    try:
        schema_str = get_schema_text(schema_filename)
        schema_dict = json.loads(schema_str)
        jsonschema.validate(instance=data, schema=schema_dict)
        return True, None
    except jsonschema.ValidationError as e:
        return False, e.message
    except Exception as e:
        return False, str(e)

def validate_semantics(
    data: Union[str, Dict, Graph], 
    shape_filename: str = "shapes/measurement_request.ttl"
) -> Tuple[bool, str]:
    """
    Validates the RDF semantics (the "meaning") using SHACL.
    
    Args:
        data: The message as a Dict, JSON string, or existing RDFLib Graph.
        shape_filename: Path to the .ttl file relative to the schemas package.
    
    Returns:
        (conforms, report_text)
    """
    # convert input data to RDFLib Graph
    if isinstance(data, Graph):
        data_graph = data
    else:
        data_graph = Graph()
        if isinstance(data, dict):
            payload = json.dumps(data)
        else:
            payload = data
        
        try:
            data_graph.parse(data=payload, format="json-ld")
        except Exception as e:
            return False, f"JSON-LD Parsing Error: {str(e)}"

    # load SHACL shapes
    try:
        shape_text = get_schema_text(shape_filename)
    except FileNotFoundError as e:
        return False, str(e)

    shape_graph = Graph()
    # assume ttl
    fmt = "json-ld" if shape_filename.endswith(".json") else "turtle"
    shape_graph.parse(data=shape_text, format=fmt)

    # run validation
    conforms, _, report_text = validate(
        data_graph,
        shacl_graph=shape_graph,
        inference='rdfs',
        abort_on_first=False,
        advanced=True
    )
    
    return conforms, report_text