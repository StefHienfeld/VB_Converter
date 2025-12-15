#!/bin/bash
# Start script voor Hienfeld backend met mise

cd "$(dirname "$0")"

echo "🚀 Starting Hienfeld backend server..."
echo "📝 Using mise Python environment"
echo ""

# Start met mise exec
mise exec -- uvicorn hienfeld_api.app:app --reload --port 8000 --log-level info

