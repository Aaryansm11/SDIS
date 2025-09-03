# File: Makefile
# Development and deployment commands for SDIS

.PHONY: help install dev test clean build deploy

help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $1, $2}'

install: ## Install dependencies
	pip install -r requirements.txt
	python -m spacy download en_core_web_sm

dev-setup: ## Set up development environment
	cp .env.example .env
	docker-compose up -d postgres redis
	sleep 5
	alembic upgrade head
	@echo "Development environment ready. Update .env with your settings."

dev: ## Run development server
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test: ## Run all tests
	pytest tests/ -v --tb=short

test-unit: ## Run unit tests only
	pytest tests/unit/ -v

test-integration: ## Run integration tests only
	pytest tests/integration/ -v

clean: ## Clean up temporary files
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +

build: ## Build Docker image
	docker build -t sdis:latest -f infra/Dockerfile .

run-docker: ## Run with Docker Compose
	docker-compose -f infra/docker-compose.yml up -d

stop-docker: ## Stop Docker Compose
	docker-compose -f infra/docker-compose.yml down

logs: ## View Docker logs
	docker-compose -f infra/docker-compose.yml logs -f app

migrate: ## Run database migrations
	alembic upgrade head

migrate-create: ## Create new migration (use: make migrate-create MSG="description")
	alembic revision --autogenerate -m "$(MSG)"

lint: ## Run code linting
	flake8 app/ tests/
	black --check app/ tests/
	isort --check-only app/ tests/

format: ## Format code
	black app/ tests/
	isort app/ tests/

security-scan: ## Run security scan
	bandit -r app/

type-check: ## Run type checking
	mypy app/

generate-keys: ## Generate RSA key pair for signing
	@echo "Generating RSA key pair..."
	@openssl genrsa -out private_key.pem 2048
	@openssl rsa -in private_key.pem -pubout -out public_key.pem
	@echo "Keys generated: private_key.pem, public_key.pem"
	@echo "Add these to your .env file"

seed-data: ## Seed database with sample data
	python scripts/seed_data.py

backup-db: ## Backup database
	pg_dump $(DATABASE_URL) > backup_$(shell date +%Y%m%d_%H%M%S).sql

deploy-staging: ## Deploy to staging
	docker build -t sdis:staging .
	# Add your staging deployment commands here

deploy-prod: ## Deploy to production
	docker build -t sdis:prod .
	# Add your production deployment commands here

health-check: ## Check application health
	curl -f http://localhost:8000/health || exit 1