.PHONY: setup setup-wizard test lint run docker clean package ci scripts

setup:
	@echo "Installing dependencies with uv..."
	@if uv sync --native-tls; then \
		echo "✓ Dependencies installed with native TLS"; \
	else \
		echo "⚠ Native TLS failed, trying standard sync..."; \
		uv sync; \
	fi

setup-wizard:
	@echo "Running ActionPulse Interactive Setup..."
	@cd .. && ./digest-core/scripts/setup.sh

test:
	./scripts/test.sh

lint:
	./scripts/lint.sh

format:
	ruff check --fix src/ tests/
	black src/ tests/

run:
	python -m digest_core.cli run --from-date today --sources ews --out ./out

docker:
	docker build -t digest-core:latest -f docker/Dockerfile .

docker-run:
	docker run --rm \
		-e EWS_PASSWORD=$(EWS_PASSWORD) \
		-e LLM_TOKEN=$(LLM_TOKEN) \
		-v $(PWD)/out:/data/out \
		-v $(PWD)/.state:/data/.state \
		-p 9108:9108 \
		-p 9109:9109 \
		digest-core:latest

package:
	./scripts/build.sh

ci: lint test

scripts:
	@echo "Available scripts:"
	@ls -la scripts/

smoke:
	./scripts/smoke.sh

test-run:
	./scripts/test_run.sh

diagnose:
	python -m digest_core.cli diagnose

collect-logs:
	./scripts/collect_diagnostics.sh

deploy:
	./scripts/deploy.sh

rotate:
	./scripts/rotate_state.sh

env-check:
	./scripts/print_env.sh

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete
	rm -rf .pytest_cache .coverage htmlcov dist build *.egg-info

