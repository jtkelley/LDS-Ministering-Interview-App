#!/bin/bash

# Docker helper script for Ministering Interviews app

set -e

IMAGE_NAME="ministering-interviews"
CONTAINER_NAME="ministering-app"

function build() {
    echo "🏗️  Building Docker image..."
    docker build -t $IMAGE_NAME .
    echo "✅ Build complete!"
}

function run() {
    echo "🚀 Starting container..."
    docker run -d \
        --name $CONTAINER_NAME \
        -p 8181:8181 \
        -v $(pwd):/app \
        -v /app/__pycache__ \
        -v /app/interviews.db \
        -e FLASK_ENV=development \
        $IMAGE_NAME
    echo "✅ Container started! Visit http://localhost:8181"
}

function stop() {
    echo "🛑 Stopping container..."
    docker stop $CONTAINER_NAME 2>/dev/null || true
    docker rm $CONTAINER_NAME 2>/dev/null || true
    echo "✅ Container stopped and removed"
}

function logs() {
    echo "📋 Showing container logs..."
    docker logs -f $CONTAINER_NAME
}

function shell() {
    echo "🐚 Opening shell in container..."
    docker exec -it $CONTAINER_NAME /bin/bash
}

function clean() {
    echo "🧹 Cleaning up..."
    docker stop $CONTAINER_NAME 2>/dev/null || true
    docker rm $CONTAINER_NAME 2>/dev/null || true
    docker rmi $IMAGE_NAME 2>/dev/null || true
    docker system prune -f
    echo "✅ Cleanup complete"
}

function test() {
    echo "🧪 Testing Chrome setup in container..."
    docker run --rm $IMAGE_NAME python -c "
import sys
sys.path.insert(0, '/app')
from app import test_chrome_setup
test_chrome_setup()
"
}

case "$1" in
    build)
        build
        ;;
    run)
        run
        ;;
    stop)
        stop
        ;;
    restart)
        stop
        run
        ;;
    logs)
        logs
        ;;
    shell)
        shell
        ;;
    clean)
        clean
        ;;
    test)
        test
        ;;
    *)
        echo "Usage: $0 {build|run|stop|restart|logs|shell|clean|test}"
        echo ""
        echo "Commands:"
        echo "  build   - Build the Docker image"
        echo "  run     - Start the container"
        echo "  stop    - Stop and remove the container"
        echo "  restart - Restart the container"
        echo "  logs    - Show container logs"
        echo "  shell   - Open shell in container"
        echo "  clean   - Remove containers and images"
        echo "  test    - Test Chrome setup"
        exit 1
esac