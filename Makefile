# ============================================
# TorStream - Makefile
# ============================================

.PHONY: help build up down restart logs shell db-migrate db-upgrade test clean backup restore

# Default target
help:
	@echo "TorStream - Available Commands:"
	@echo ""
	@echo "  make build        - Build all Docker images"
	@echo "  make up           - Start all services"
	@echo "  make down         - Stop all services"
	@echo "  make restart      - Restart all services"
	@echo "  make logs         - View logs from all services"
	@echo "  make shell        - Open shell in app container"
	@echo "  make db-migrate   - Create new migration"
	@echo "  make db-upgrade   - Run database migrations"
	@echo "  make test         - Run tests"
	@echo "  make backup       - Create backup"
	@echo "  make restore      - Restore from backup (BACKUP_FILE=...)"
	@echo "  make init-admin   - Create admin user"
	@echo "  make clean        - Remove all containers and volumes"
	@echo "  make tor-hostname - Show Tor onion address"

# Build
build:
	docker-compose build

# Start services
up:
	docker-compose up -d
	@echo "Waiting for services to start..."
	@sleep 10
	@echo "Services started!"

# Stop services
down:
	docker-compose down

# Restart services
restart:
	docker-compose restart

# View logs
logs:
	docker-compose logs -f

# Shell into app
shell:
	docker-compose exec app /bin/sh

# Database migrations
db-migrate:
	@read -p "Migration message: " msg; \
	docker-compose exec app alembic revision --autogenerate -m "$$msg"

db-upgrade:
	docker-compose exec app alembic upgrade head

db-downgrade:
	docker-compose exec app alembic downgrade -1

# Tests
test:
	docker-compose exec app pytest tests/ -v

test-cov:
	docker-compose exec app pytest tests/ -v --cov=app --cov-report=html

# Backup and restore
backup:
	./scripts/backup.sh

restore:
	@if [ -z "$(BACKUP_FILE)" ]; then \
		echo "Usage: make restore BACKUP_FILE=backups/file.tar.gz"; \
		exit 1; \
	fi
	./scripts/restore.sh $(BACKUP_FILE)

# Initialize admin
init-admin:
	./scripts/init-admin.sh

# Tor
tor-hostname:
	@docker-compose exec tor cat /var/lib/tor/torstream/hostname 2>/dev/null || echo "Tor not ready yet"

# Clean everything
clean:
	docker-compose down -v
	docker system prune -f

# Development setup
dev-setup:
	cp .env.example .env
	@echo "Please edit .env with your configuration"
	@echo "Then run: make build && make up && make db-upgrade && make init-admin"

# Production setup
prod-setup:
	@echo "Setting up for production..."
	@read -p "Continue? (yes/no): " confirm; \
	if [ "$$confirm" != "yes" ]; then \
		echo "Aborted"; \
		exit 1; \
	fi
	docker-compose -f docker-compose.yml up -d
	@sleep 15
	docker-compose exec app alembic upgrade head
	./scripts/init-admin.sh
	@echo "Production setup complete!"
