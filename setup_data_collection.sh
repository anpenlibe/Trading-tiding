#!/bin/bash

echo "=================================="
echo "DATA COLLECTION SETUP"
echo "=================================="

# Check if in trading-tiding directory
if [[ ! -f "requirements.txt" ]]; then
    echo "❌ Error: Run this script from the trading-tiding directory"
    exit 1
fi

# Install/update dependencies
echo "📦 Installing dependencies..."
pip install --upgrade pip
pip install tabulate  # Add missing dependency
pip install -r requirements.txt

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p data/reports

# Make scripts executable
echo "🔧 Making scripts executable..."
chmod +x test_data_collector.py
chmod +x scheduler.py
chmod +x monitor.py

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Test single symbol:    python test_data_collector.py"
echo "2. Run scheduler:         python scheduler.py"
echo "3. Monitor data:          python monitor.py"
echo ""
echo "For automatic collection during market hours:"
echo "   python scheduler.py"
echo ""
echo "Check logs in: data/logs/"
echo "=================================="
