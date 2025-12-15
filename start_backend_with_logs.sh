#!/bin/bash
# Start script voor Hienfeld backend met logging naar bestand

cd "$(dirname "$0")"

LOG_FILE="backend.log"
echo "🚀 Starting Hienfeld backend server..."
echo "📝 Logs worden geschreven naar: $LOG_FILE"
echo "📋 Druk Ctrl+C om te stoppen"
echo ""

# Start met mise exec en log naar bestand
mise exec -- uvicorn hienfeld_api.app:app --reload --port 8000 --log-level info 2>&1 | tee "$LOG_FILE"

