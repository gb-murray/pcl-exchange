# Simple validation harness for PCL Exchange repo

SHELL := /bin/bash

# JSON Schema tools via Node
AJV ?= npx ajv

# Python tools
PYTHON ?= python3
PIP ?= pip3
PYTEST ?= pytest

# Paths
SCHEMA_DIR := schemas
SHAPE_DIR := schemas/shapes
EXAMPLE := examples/pcl_action_crate_example.json

.PHONY: help install validate validate-json validate-shacl test clean build

help:
	@echo "Targets:"
	@echo "  make install        # Install CLI tools (ajv-cli and pyshacl)"
	@echo "  make validate       # Validate everything (JSON Schema and SHACL)"
	@echo "  make test 		 	 # Run unit tests"
	@echo "  make build          # Build the package"
	@echo "  make clean          # Clean caches"

install:
	$(PIP) install -e ".[dev]"
	# install Node tools if missing
	npm -v >/dev/null 2>&1 || (echo 'Node/npm required for ajv-cli' && exit 1)
	npx --yes ajv-cli --version >/dev/null || true

validate: validate-json validate-shacl

validate-json:
	@echo "--> Validating JSON Schema..."
	$(AJV) validate -s $(SCHEMA_DIR)/envelope.json -d $(EXAMPLE) --strict=false
	# Validate a dynamic error string
	$(AJV) validate -s $(SCHEMA_DIR)/error.json -d <(echo '{"type":"https://w3id.org/pcl-profile/action/v1#Error","timestamp":"2025-01-01T00:00:00Z","code":"INVALID_ENVELOPE","reason":"demo"}') --strict=false

validate-shacl:
	@echo "--> Validating SHACL..."
	$(PYTHON) scripts/validate_shacl.py --data $(EXAMPLE) --shapes $(SHAPE_DIR)/measurement_request.ttl $(SHAPE_DIR)/workflow_launch.ttl

test:
	@echo "--> Running Python Unit Tests..."
	$(PYTEST)

build:
	$(PIP) install build
	$(PYTHON) -m build

clean:
	rm -rf .pytest_cache node_modules build dist *.egg-info
	find . -type d -name "__pycache__" -exec rm -rf {} +
