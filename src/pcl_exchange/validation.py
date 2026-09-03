import json
import importlib.resources
from typing import Union, Dict, Tuple, Optional

from rdflib import Graph
from pyshacl import validate
import jsonschema

from . import schemas


def _get_schema_resource(filename: str):
    resource = importlib.resources.files(schemas)
    for part in filename.split("/"):
        resource = resource / part
    return resource


def get_shape_for_action(action: str) -> Optional[str]:
    """Return 'shapes/{action}.ttl' if that shape file exists in the package, else None."""
    candidate = f"shapes/{action}.ttl"
    return candidate if _get_schema_resource(candidate).is_file() else None

def get_schema_text(filename: str) -> str:
    """
    Helper to read a schema file from inside the package.
    Example: get_schema_text('envelope.json')
    """
    try:
        return _get_schema_resource(filename).read_text(encoding='utf-8')
    except FileNotFoundError:
        raise FileNotFoundError(f"Schema file '{filename}' not found in package resources.")

def validate_structure(data: Dict, schema_filename: str = "envelope.json") -> Tuple[bool, Optional[str]]:
    """
    Validates the pure JSON structure against the JSON Schema.

    Args:
        data: The message as a dictionary.
        schema_filename: Path to the schema file relative to the schemas package.
    
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
    shape_filename: str = "shapes/request_measurement.ttl"
) -> Tuple[bool, str]:
    """
    Validates the RDF semantics using SHACL.
    
    Args:
        data: The message as a Dict, JSON string, or existing RDFLib Graph.
        shape_filename: Path to the .ttl file relative to the schemas package.
    
    Returns:
        (True, None) if valid
        (False, error_message) if invalid
    """

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

    try:
        shape_text = get_schema_text(shape_filename)
    except FileNotFoundError as e:
        return False, str(e)

    shape_graph = Graph()

    fmt = "json-ld" if shape_filename.endswith(".json") else "turtle"
    shape_graph.parse(data=shape_text, format=fmt)

    is_valid, _, error_message = validate(
        data_graph,
        shacl_graph=shape_graph,
        inference='rdfs',
        abort_on_first=False,
        advanced=True
    )
    
    return is_valid, error_message