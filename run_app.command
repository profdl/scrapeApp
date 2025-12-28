#!/bin/bash

# Navigate to the script's directory
cd "$(dirname "$0")"

echo "🚀 Starting Slides Creator App..."
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found!"
    echo "Creating virtual environment..."
    python3 -m venv venv

    echo "Installing dependencies..."
    source venv/bin/activate
    pip install -r requirements_slides.txt
    echo ""
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Start Streamlit
echo "Opening app in your browser..."
echo "Press Ctrl+C to stop the server"
echo ""

streamlit run app.py

# Keep terminal open if there's an error
if [ $? -ne 0 ]; then
    echo ""
    read -p "Press Enter to exit..."
fi
