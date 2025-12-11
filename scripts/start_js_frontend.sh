#!/bin/bash

# Navigate to the frontend directory
cd "$(dirname "$0")/../medsam_js_viewer"

# Check if node_modules exists, if not install dependencies
if [ ! -d "node_modules" ]; then
    echo "Installing dependencies..."
    npm install
fi

# Start the development server with cache clearing
echo "Starting MedSAM JS Frontend (clearing cache)..."
npm run dev -- --force
