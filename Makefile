.PHONY: \
	help up down restart logs ps clean reset \
	format lint typecheck

help:
	@echo
	@echo "Gitpulse Analytics Commands:"
	@echo ""
	@echo "[INFRASTRUCTURE]"
	@echo "   make up: Start the infrastructure using Docker Compose and set up MinIO buckets"
	@echo "   make down: Stop the infrastructure"
	@echo "   make restart: Restart the infrastructure"
	@echo "   make logs: View the logs for the infrastructure"
	@echo "   make ps: List the running containers for the infrastructure"
	@echo "   make reset: Reset the infrastructure. WARNING: This will remove all data and volumes!"
	@echo ""
	@echo "[DEVELOPMENT]"
	@echo "   make format: Format the code using ruff"
	@echo "   make lint: Check the code for issues using ruff"
	@echo "   make typecheck: Check the code for type issues using pyrefly"
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

clean:
	docker compose rm -f

reset:
	docker compose down -v --remove-orphans
	docker system prune -f

format:
	uv run ruff format .

lint:
	uv run ruff check .

typecheck:
	uv run pyrefly check .