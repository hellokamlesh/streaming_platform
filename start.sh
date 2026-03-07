#!/bin/bash
# ============================================
# TorStream - Quick Start Script
# ============================================

set -e

echo "============================================"
echo "TorStream - Quick Start"
echo "============================================"
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "Creating .env from template..."
    cp .env.example .env
    echo "WARNING: Please edit .env and set secure values for:"
    echo "  - SECRET_KEY (min 32 characters)"
    echo "  - ADMIN_SECRET_KEY (min 32 characters, different from SECRET_KEY)"
    echo "  - POSTGRES_PASSWORD"
    echo "  - REDIS_PASSWORD"
    echo ""
    echo "Then run this script again."
    exit 1
fi

echo "Step 1: Building Docker images..."
docker-compose build

echo ""
echo "Step 2: Starting services..."
docker-compose up -d postgres redis

echo ""
echo "Step 3: Waiting for database to be ready..."
sleep 10

echo ""
echo "Step 4: Running database migrations..."
docker-compose run --rm app alembic upgrade head

echo ""
echo "Step 5: Starting remaining services..."
docker-compose up -d app nginx tor

echo ""
echo "Step 6: Creating admin user..."
echo "============================================"
./scripts/init-admin.sh || echo "Admin creation skipped (may already exist)"

echo ""
echo "============================================"
echo "TorStream is starting up!"
echo "============================================"
echo ""
echo "Access the application:"
echo "  - Local: http://localhost"
echo ""
sleep 2
echo "Tor Hidden Service address:"
docker-compose exec tor cat /var/lib/tor/torstream/hostname 2>/dev/null || echo "  (Tor is still starting, check with: docker-compose exec tor cat /var/lib/tor/torstream/hostname)"
echo ""
echo "View logs: docker-compose logs -f"
echo ""
