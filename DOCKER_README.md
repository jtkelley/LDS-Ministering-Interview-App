# Ministering Interviews - Docker Setup

This application is now fully containerized for cross-platform compatibility and easy deployment.

## 🚀 Quick Start

### Using Docker Compose (Recommended)

```bash
# Build and start the application
docker-compose up --build

# Access the app at http://localhost:8181
```

### Using Docker Commands

```bash
# Build the image
docker build -t ministering-interviews .

# Run the container
docker run -d -p 8181:8181 -v $(pwd):/app ministering-interviews

# View logs
docker logs -f <container-id>
```

### Using Helper Script

```bash
# Make script executable (first time only)
chmod +x docker-helper.sh

# Build and run
./docker-helper.sh build
./docker-helper.sh run

# Other commands
./docker-helper.sh logs    # View logs
./docker-helper.sh shell   # Open container shell
./docker-helper.sh stop    # Stop container
./docker-helper.sh clean   # Clean up
```

## 🐳 What's Included

- **Python 3.11** with all dependencies
- **Google Chrome** stable version
- **ChromeDriver** matching Chrome version
- **All system libraries** needed for Selenium
- **Non-root user** for security
- **Health checks** and proper configuration

## 🔧 Development

### Local Development with Live Reload

```bash
# Use docker-compose for development
docker-compose up --build

# Code changes will be reflected immediately due to volume mounting
```

### Testing Chrome Setup

```bash
# Test Chrome functionality in container
./docker-helper.sh test
```

### Accessing Container

```bash
# Open shell in running container
./docker-helper.sh shell

# Or directly with docker
docker exec -it ministering-app /bin/bash
```

## 🚀 Production Deployment

### Digital Ocean App Platform

1. Push code to GitHub
2. Connect repository to DO App Platform
3. DO will automatically detect and build the Dockerfile
4. Set environment variables in DO dashboard

### Other Platforms

The Dockerfile works with:
- **Heroku** (with heroku.yml)
- **AWS ECS/Fargate**
- **Google Cloud Run**
- **Azure Container Instances**

## 🔍 Troubleshooting

### Chrome Issues
```bash
# Check Chrome installation
docker run --rm ministering-interviews google-chrome --version
docker run --rm ministering-interviews chromedriver --version
```

### Container Logs
```bash
# View application logs
./docker-helper.sh logs

# View Chrome/Selenium debug info
docker logs ministering-app | grep -i chrome
```

### Import Functionality
- The import feature now uses the container's ChromeDriver
- No more Windows-specific issues
- Works identically in development and production

## 📁 File Structure

```
.
├── Dockerfile              # Container definition
├── docker-compose.yml      # Local development setup
├── docker-helper.sh        # Utility script
├── .dockerignore          # Files to exclude from build
├── requirements.txt        # Python dependencies
└── app.py                 # Main application
```

## 🎯 Benefits

- ✅ **Cross-platform**: Works on Windows, macOS, Linux
- ✅ **No dependency issues**: Everything included in container
- ✅ **Production ready**: Same container runs everywhere
- ✅ **Easy deployment**: Push to GitHub, deploy anywhere
- ✅ **Isolated**: No conflicts with system packages

## 🔒 Security

- Runs as non-root user
- Minimal attack surface
- No unnecessary packages
- Regular security updates via base image