#!/bin/bash

# Build and run the Ministering Interviews app in Docker

echo "🏗️  Building Docker image..."
docker-compose build

echo "🚀 Starting the application..."
docker-compose up -d

echo "⏳ Waiting for the application to be healthy..."
sleep 10

echo "🔍 Checking application status..."
docker-compose ps

echo "🌐 Application should be available at: http://localhost:8181"
echo ""
echo "To view logs: docker-compose logs -f"
echo "To stop: docker-compose down"
echo "To rebuild: docker-compose up --build"