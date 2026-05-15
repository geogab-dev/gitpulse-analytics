.PHONY: \
	help up down restart logs ps reset \
	install \
	format lint typecheck rmcache

help:
	@echo
	@echo "Gitpulse Analytics Commands:"
	@echo ""
	@echo "[INFRASTRUCTURE]"
	@echo "   make up:       Start Docker Compose and set up MinIO buckets"
	@echo "   make down:     Stop the infrastructure"
	@echo "   make restart:  Restart the infrastructure"
	@echo "   make logs:     View the infrastructure logs"
	@echo "   make ps:       List running containers"
	@echo "   make reset:    Remove all data and volumes. WARNING: destructive!"
	@echo ""
	@echo "[APPLICATION]"
	@echo "   make install:  Install dependencies with uv"
	@echo ""
	@echo "[DEVELOPMENT]"
	@echo "   make format:    Format code with ruff"
	@echo "   make lint:      Check code with ruff"
	@echo "   make typecheck: Check types with pyrefly"
	@echo "   make rmcache:   Remove __pycache__ and .ruff_cache directories"
	@echo

up:
	docker compose up -d --wait
	uv run python infra/scripts/init_minio.py

down:
	docker compose down

restart:
	docker compose down
	docker compose up -d

logs:
	docker compose logs -f

ps:
	docker compose ps

reset:
	docker compose down -v --remove-orphans
	docker system prune -f

install:
	uv sync

format:
	uv run ruff format .

lint:
	uv run ruff check .

typecheck:
	uv run pyrefly check .

rmcache:
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@echo "Cache cleaned!"
