#!/usr/bin/env bash
# ==============================================================================
# DELL MCP - Automated Testing & CI Script
# ==============================================================================
# This script ensures the environment is clean, the mock server is up-to-date
# with the latest OpenAPI spec, and all tests pass.
set -e

echo "🚀 Starting Automated Test Suite..."

echo "📦 1. Syncing dependencies..."
# Ensure uv is installed or fallback to pip
if command -v uv &> /dev/null; then
    uv pip install -r requirements.txt
else
    echo "uv not found, ensuring .venv is active..."
    if [ ! -d ".venv" ]; then
        python3 -m venv .venv
    fi
    source .venv/bin/activate
    pip install -r requirements.txt
fi

echo "🐳 2. Restarting Mock API Server with latest OpenAPI specs..."
docker-compose down
docker-compose up -d --build

echo "⏳ Waiting for Prism server to boot..."
sleep 3

echo "🩺 3. Verifying Mock Server Health..."
# Hit the Redfish root to ensure Prism parsed the OpenAPI file correctly
CURL_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:4010/redfish/v1 || echo "failed")
if [ "$CURL_STATUS" != "200" ]; then
    echo "❌ Mock server failed to respond with 200 OK (Got: $CURL_STATUS)."
    echo "Fetching Docker logs for debugging:"
    docker logs dell_mcp_prism-mock_1
    exit 1
fi
echo "✅ Mock server is healthy!"

echo "🧪 4. Running Pytest Suite..."
if command -v uv &> /dev/null; then
    uv run pytest tests/ -v
else
    pytest tests/ -v
fi

echo "🧹 5. Checking Code Quality (Linting)..."
if command -v uv &> /dev/null; then
    uv run black --check src/ tests/ || echo "⚠️ Black formatting issues found."
    uv run flake8 src/ tests/ || echo "⚠️ Flake8 linting issues found."
fi

echo "🎉 All critical testing gates passed successfully!"
