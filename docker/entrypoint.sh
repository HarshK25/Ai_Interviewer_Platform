#!/bin/sh
# Wait for postgres to be ready, then create tables, then start server
set -e

echo "⏳ Waiting for PostgreSQL..."
until pg_isready -h postgres -U postgres -d ai_interviewer; do
  sleep 2
done
echo "✅ PostgreSQL is ready."

echo "📦 Creating/updating database tables..."
python scripts/create_tables.py

echo "🚀 Starting FastAPI server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

