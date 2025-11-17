# Running with Docker Locally

This guide shows you how to run the app in Docker on your local machine (optional - you can also just run `python app.py`).

## Why Use Docker Locally?

**You probably don't need to!** Docker is mainly for production deployment (Render). However, you might want to test Docker locally if:
- You want to verify the Docker build works before deploying
- You want to test the exact production environment
- You're on a non-Windows machine and want to test Linux ChromeDriver

## Quick Start with Docker Compose

### 1. Build and Run

```bash
docker-compose up --build
```

This will:
1. Build the Docker image (includes Chrome, ChromeDriver, Python)
2. Start the container
3. Mount your local `instance/` folder (database persists)
4. Run on http://localhost:8181

### 2. Stop

Press `Ctrl+C` or:
```bash
docker-compose down
```

### 3. View Logs

```bash
docker-compose logs -f
```

## Configuration

The `docker-compose.yml` file is configured to:
- **Port**: Expose 8181 (same as `python app.py`)
- **Database**: Mount `./instance` folder (SQLite persists on your machine)
- **SECRET_KEY**: Uses value from `.env` file (same as non-Docker)
- **Auto-restart**: Restarts if crashes

## Key Differences: Local Docker vs python app.py

| Feature | `python app.py` | `docker-compose up` |
|---------|-----------------|---------------------|
| **ChromeDriver** | Uses Windows `.exe` | Uses Linux binary |
| **Setup** | Just works | Requires Docker installed |
| **Database** | `instance/interviews.db` | `instance/interviews.db` (same!) |
| **URL** | http://localhost:8181 | http://localhost:8181 (same!) |
| **Environment** | Windows | Linux (in container) |
| **Speed** | Instant start | ~2 seconds start time |
| **Production Match** | Different OS | Matches production exactly |

## Common Commands

```bash
# Build without starting
docker-compose build

# Start in background
docker-compose up -d

# Stop background containers
docker-compose down

# Rebuild from scratch (no cache)
docker-compose build --no-cache

# View running containers
docker-compose ps

# Execute command in running container
docker-compose exec ministering-app bash
```

## Troubleshooting

### Port Already in Use
If port 8181 is already taken (maybe you have `python app.py` running):

```bash
# Stop any python app.py processes first
# Or change the port in docker-compose.yml:
ports:
  - "8182:8181"  # Use 8182 on host, 8181 in container
```

### Database Permission Issues
If you get permission errors:

```bash
# Make sure instance folder exists
mkdir -p instance

# On Linux/Mac, fix permissions
chmod 777 instance
```

### Build Fails
```bash
# Clear Docker cache and rebuild
docker-compose down
docker system prune -f
docker-compose build --no-cache
```

## Do I Need Docker Locally?

**No!** Just use `python app.py` for local development:

✅ **Use `python app.py` if**:
- You're developing normally
- You want fast startup
- Windows ChromeDriver works fine

✅ **Use `docker-compose up` if**:
- You want to test the production Docker image
- You're debugging Docker-specific issues
- You want to match Render's environment exactly

## For Production Deployment

See `RENDER_DEPLOYMENT.md` - Render handles Docker automatically, you don't run these commands.
