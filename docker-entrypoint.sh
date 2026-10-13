#!/bin/bash
set -e

echo "Starting Docker Entrypoint..."

# Ensure dependencies are up to date
if [ -f "requirements.txt" ]; then
    echo "Installing dependencies..."
    pip install --no-cache-dir -r requirements.txt
fi

# Ensure database is up to date
if [ -f "migrate_db.py" ]; then
    echo "Running database auto-migrations..."
    python migrate_db.py
fi
if [ -d "migrations" ]; then
    echo "Running database migrations..."
    flask db upgrade
fi

echo "Starting WSGI Server (Waitress)..."
exec python run_prod.py
