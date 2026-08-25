COMPOSE ?= docker compose
SCENARIO ?= bad-payment-deploy

INVESTIGATOR_URL ?= http://localhost:8080

.PHONY: up down logs traffic incident investigate mcp mcp-smoke test test-integration lint

up:
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down -v

logs:
	$(COMPOSE) logs -f --tail=100

traffic:
	$(COMPOSE) up -d traffic

incident:
	python demo/fault_injection/inject.py --scenario $(SCENARIO)

investigate:
	python scripts/investigate_demo.py --url $(INVESTIGATOR_URL)

mcp:
	python -m investigator.mcp

mcp-smoke:
	python scripts/mcp_smoke.py

test:
	pytest tests/unit -q

test-integration:
	pytest tests/integration -q -m integration

lint:
	ruff check .
