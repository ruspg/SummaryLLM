.PHONY: setup setup-wizard test lint format run docker docker-run package ci smoke test-run diagnose collect-logs deploy rotate env-check clean

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
	PYTHONPATH=src uv run pytest tests/ -v

lint:
	uv run ruff check src/ tests/
	uv run black --check src/ tests/

format:
	uv run ruff check --fix src/ tests/
	uv run black src/ tests/

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
	uv build

ci: lint test

smoke:
	python -m digest_core.cli run --dry-run --window calendar_day

test-run:
	python -m digest_core.cli run --dry-run --from-date today

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
