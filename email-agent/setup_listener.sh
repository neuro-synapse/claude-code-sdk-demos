#!/bin/bash

echo "Setting up Accounting Email Listener..."
echo "========================================"

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

echo ""
echo "Setup complete!"
echo ""
echo "IMPORTANT: Before running the listener, you need to:"
echo "1. Enable Gmail API in Google Cloud Console"
echo "2. Download credentials.json from Google Cloud Console"
echo "3. Place credentials.json in this directory"
echo ""
echo "To run the listener:"
echo "  source venv/bin/activate"
echo "  python accounting_email_listener.py"
echo ""
echo "The listener will:"
echo "- Check for accounting-related emails every 5 minutes"
echo "- Label them with 'finance' label (green color)"
echo "- Keep track of processed emails to avoid duplicates"