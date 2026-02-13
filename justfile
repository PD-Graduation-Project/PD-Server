default:
    @just --list

# Run the Flask development server
run:
    python app.py

# Run with auto-reload using flask run
dev:
    flask --app app run --debug --host 0.0.0.0 --port 5000

# Database migrations
migrate:
    flask db upgrade

migration message="":
    flask db migrate -m "{{message}}"

migration-diff:
    flask db migrate

db-rollback:
    flask db downgrade

db-reset:
    @echo "⚠️  This will DELETE all data in test_sessions, test_inputs, and esp32_devices tables!"
    flask db downgrade
    flask db upgrade

# Run tests
test:
    pytest

test-watch:
    ptw

test-coverage:
    pytest --cov=. --cov-report=term-missing --cov-report=html

# Linting and formatting
lint:
    ruff check .

format:
    ruff check --fix . && isort .

typecheck:
    pyright .

# Install dependencies
install:
    pip install -r requirements.txt

install-dev:
    pip install -r requirements-dev.txt

# Clean up
clean-pycache:
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete 2>/dev/null || true

clean-coverage:
    rm -rf .coverage htmlcov/ .pytest_cache/ .hypothesis/ 2>/dev/null || true

clean: clean-pycache clean-coverage
    @echo "Cleaned up"

# Health check
health:
    curl http://localhost:5000/health

# Database console
db-console:
    psql $(grep DATABASE_URL .env | cut -d= -f2-)

# Create initial migration after model changes
prepare-migration:
    just db-rollback
    just migration-diff
    just migrate

# Full setup for fresh clone
setup: install install-dev migrate
    @echo "✓ Project setup complete!"
    @echo "Run 'just dev' to start the server"
