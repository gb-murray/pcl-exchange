# Simple validation harness for PCL Exchange repo

SHELL := /bin/bash

# Python tools
PYTHON ?= python3
PIP ?= pip3
PYTEST ?= pytest

# Paths
SCHEMA_DIR := schemas
SHAPE_DIR := schemas/shapes
EXAMPLE := examples/pcl_action_crate_example.json
WORKFLOW_EXAMPLE := examples/pcl_workflow_crate_example.json

.PHONY: help install validate validate-json validate-shacl validate-shacl-measurement validate-shacl-workflow test clean build

help:
	@echo "Targets:"
	@echo "  make install        # Install package and dev dependencies"
	@echo "  make validate       # Validate everything (JSON Schema and SHACL)"
	@echo "  make test 		 	 # Run unit tests"
	@echo "  make build          # Build the package"
	@echo "  make clean          # Clean caches"

install:
	$(PYTHON) -m pip install -e ".[dev]"

validate: validate-json validate-shacl

validate-json:
	@echo "--> Validating JSON Schema..."
	$(PYTHON) -c "import json; from pathlib import Path; from jsonschema import Draft202012Validator, FormatChecker; schema_dir=Path('$(SCHEMA_DIR)'); ex=Path('$(EXAMPLE)'); env_schema=json.loads((schema_dir/'envelope.json').read_text(encoding='utf-8')); err_schema=json.loads((schema_dir/'error.json').read_text(encoding='utf-8')); crate=json.loads(ex.read_text(encoding='utf-8')); env=next((n for n in crate.get('@graph',[]) if n.get('@id')=='#envelope'), None); assert env is not None, 'Example crate missing #envelope node'; err={'type':'https://w3id.org/pcl-profile/action/v1#Error','timestamp':'2025-01-01T00:00:00Z','code':'INVALID_ENVELOPE','reason':'demo'}; e1=list(Draft202012Validator(env_schema, format_checker=FormatChecker()).iter_errors(env)); e2=list(Draft202012Validator(err_schema, format_checker=FormatChecker()).iter_errors(err)); assert not e1, 'Envelope schema failed: ' + e1[0].message; assert not e2, 'Error schema failed: ' + e2[0].message; print('JSON schema validation passed')"

validate-shacl:
	@echo "--> Validating SHACL (measurement case)..."
	$(MAKE) validate-shacl-measurement
	@echo "--> Validating SHACL (workflow case)..."
	$(MAKE) validate-shacl-workflow

validate-shacl-measurement:
	@echo "--> Validating SHACL..."
	$(PYTHON) -c "exec(\"import sys\\nfrom rdflib import Graph\\nfrom pyshacl import validate\\n\\ndata_graph = Graph()\\ndata_graph.parse('$(EXAMPLE)', format='json-ld')\\nshape_graph = Graph()\\nshape_graph.parse('$(SHAPE_DIR)/measurement_request.ttl', format='turtle')\\nconforms, _, report = validate(data_graph, shacl_graph=shape_graph, inference='rdfs', abort_on_first=False, allow_infos=True, allow_warnings=True)\\nprint(('SHACL passed: ' if conforms else 'SHACL failed: ') + '$(SHAPE_DIR)/measurement_request.ttl')\\nif not conforms:\\n    print(report)\\nsys.exit(0 if conforms else 1)\")"

validate-shacl-workflow:
	@echo "--> Validating SHACL..."
	$(PYTHON) -c "exec(\"import sys\\nfrom rdflib import Graph\\nfrom pyshacl import validate\\n\\ndata_graph = Graph()\\ndata_graph.parse('$(WORKFLOW_EXAMPLE)', format='json-ld')\\nshape_graph = Graph()\\nshape_graph.parse('$(SHAPE_DIR)/workflow_launch.ttl', format='turtle')\\nconforms, _, report = validate(data_graph, shacl_graph=shape_graph, inference='rdfs', abort_on_first=False, allow_infos=True, allow_warnings=True)\\nprint(('SHACL passed: ' if conforms else 'SHACL failed: ') + '$(SHAPE_DIR)/workflow_launch.ttl')\\nif not conforms:\\n    print(report)\\nsys.exit(0 if conforms else 1)\")"

test:
	@echo "--> Running Python Unit Tests..."
	$(PYTEST)

build:
	$(PIP) install build
	$(PYTHON) -m build

clean:
	rm -rf .pytest_cache node_modules build dist *.egg-info
	find . -type d -name "__pycache__" -exec rm -rf {} +
