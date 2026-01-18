#!/bin/bash
set -e

# Wait for database to be ready
echo "Waiting for database..."
python -c "
import time
import os
from sqlalchemy import create_engine, text

database_url = os.getenv('DATABASE_URL')
engine = create_engine(database_url)

for i in range(30):
    try:
        with engine.connect() as conn:
            conn.execute(text('SELECT 1'))
        print('Database is ready!')
        break
    except Exception as e:
        print(f'Waiting for database... ({i+1}/30)')
        time.sleep(1)
else:
    print('Database connection failed!')
    exit(1)
"

# Check if we should load seed data
# We do the actual check and loading AFTER the API starts and creates tables
if [ "$LOAD_SAMPLE_DATA" = "true" ]; then
    echo "Sample data loading enabled - will check after API starts"
    export _PENDING_SEED=true
fi

# Start the API server in background first to create tables
echo "Starting Reconly API (initializing database)..."
uvicorn reconly_api.main:app --host 0.0.0.0 --port 8000 &
API_PID=$!

# Wait for API to be healthy (tables created)
echo "Waiting for API to be ready..."
for i in $(seq 1 60); do
    if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        echo "API is ready!"
        break
    fi
    sleep 1
done

# Load seed data if enabled and database is empty
if [ "$_PENDING_SEED" = "true" ]; then
    echo "Checking if seed data should be loaded..."
    python -c "
import os
from sqlalchemy import create_engine, text

database_url = os.getenv('DATABASE_URL')
engine = create_engine(database_url)

try:
    with engine.connect() as conn:
        result = conn.execute(text('SELECT COUNT(*) FROM sources')).scalar()
        if result == 0:
            print('NEEDS_SEED')
        else:
            print(f'Database already has {result} sources, skipping seed')
except Exception as e:
    print(f'Error checking database: {e}')
    print('NEEDS_SEED')
" > /tmp/seed_check.txt 2>&1

    if grep -q "NEEDS_SEED" /tmp/seed_check.txt; then
        echo "Loading sample data..."
        python /app/scripts/load_demo_seed.py
        echo "Sample data loaded successfully!"
    else
        cat /tmp/seed_check.txt
    fi
fi

# Wait for the API process
echo "Reconly is ready!"
wait $API_PID
