#!/bin/bash
echo "Installing dependencies..."
pip install -U -r requirements.txt

echo "Creating necessary directories..."
mkdir -p cache downloads anony/cookies

echo "Build completed!"
