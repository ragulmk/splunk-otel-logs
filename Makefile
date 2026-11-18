OTEL_IMAGE := otel/opentelemetry-collector-contrib:0.128.0

.PHONY: help setup up down ps logs status test validate test-loggen test-otel \
        incident-payment incident-bruteforce incident-slowdb incident-stop reset

help:                  ## Show available commands
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-20s %s\n", $$1, $$2}'

setup:                 ## Create .env with random Splunk password and HEC token
	@./scripts/setup.sh

up: setup              ## Start everything (Splunk needs 2-3 min on first start)
	docker compose up -d
	@echo "Splunk:  http://localhost:8000  (admin / see .env)"
	@echo "Grafana: http://localhost:3000"

down:                  ## Stop everything (keeps data)
	docker compose down

ps:                    ## Container status
	docker compose ps

logs:                  ## Follow collector logs (first place to look if data is missing)
	docker compose logs -f otel-collector

status:                ## Check that each stage of the pipeline is healthy
	@printf "loggen writing:   "; docker compose exec -T loggen sh -c 'tail -1 /logs/app.log | cut -c1-80'
	@printf "collector health: "; curl -s localhost:13133 && echo
	@printf "splunk HEC:       "; curl -sk https://localhost:8088/services/collector/health && echo

test: validate test-loggen test-otel  ## Run all offline checks

validate:              ## Validate Splunk conf/XML, YAML and JSON files
	python3 scripts/validate.py

test-loggen:           ## Unit tests for the log generator
	cd loggen && python3 -m unittest discover -s tests -v

test-otel:             ## Validate the OpenTelemetry Collector config
	docker run --rm -e SPLUNK_HEC_TOKEN=dummy -e DEPLOY_ENV=ci \
		-v "$(PWD)/otel/config.yaml:/etc/otelcol-contrib/config.yaml:ro" \
		$(OTEL_IMAGE) validate --config=/etc/otelcol-contrib/config.yaml

incident-payment:      ## Simulate a payment provider outage (10 min)
	./scripts/incident.sh payment_outage 600

incident-bruteforce:   ## Simulate a brute-force login attack (5 min)
	./scripts/incident.sh brute_force 300

incident-slowdb:       ## Simulate a slow database (10 min)
	./scripts/incident.sh slow_db 600

incident-stop:         ## Stop all simulated incidents
	./scripts/incident.sh stop

reset:                 ## DANGER: stop and delete all stored logs
	docker compose down -v
