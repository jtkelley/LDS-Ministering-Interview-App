# Ministering Interviews - Digital Ocean App Platform Deployment

## Prerequisites
- Digital Ocean account
- GitHub repository with this code
- SMTP email service (Gmail, SendGrid, etc.)
- Twilio account (optional, for SMS)

## Deployment Steps

### 1. Prepare Your Repository
1. Push this code to a GitHub repository
2. Update `.do/app.yaml` with your actual GitHub repo URL

### 2. Set Up Database
- The app.yaml includes a PostgreSQL database configuration
- Digital Ocean will automatically create and connect the database

### 3. Configure Environment Variables
In Digital Ocean App Platform, set these secrets:
- `SECRET_KEY`: A random secret key for Flask sessions
- `MAIL_USERNAME`: Your email service username
- `MAIL_PASSWORD`: Your email service password/app password
- `TWILIO_ACCOUNT_SID`: Your Twilio account SID
- `TWILIO_AUTH_TOKEN`: Your Twilio auth token
- `TWILIO_PHONE_NUMBER`: Your Twilio phone number

### 4. Deploy
1. Go to Digital Ocean App Platform
2. Create a new app from GitHub
3. Select your repository
4. Use the provided Dockerfile for build configuration
5. Set environment variables
6. Deploy

## Chrome/Selenium Configuration

The app is configured to:
- Use system-installed ChromeDriver on DO App Platform
- Fall back to ChromeDriverManager for local development
- Run Chrome in headless mode
- Include necessary Chrome options for containerized environments

## Resource Considerations

- **Memory**: Web scraping requires ~500MB+ RAM
- **CPU**: Chrome initialization is CPU-intensive
- **Timeouts**: DO App Platform has execution time limits (25 seconds for free tier)
- **Storage**: File system is read-only except /tmp

## Troubleshooting

### Chrome Setup Issues
- Check container logs for ChromeDriver errors
- Ensure Chrome and ChromeDriver versions match
- Verify outbound network access

### Import Functionality
- The import process runs in background threads
- Progress is tracked via global storage (not Flask sessions)
- Timeouts may occur for large imports

### Database Issues
- Use PostgreSQL in production (not SQLite)
- Ensure database migrations run on deployment

## Local Development vs Production

The code automatically detects the environment:
- **Local**: Uses ChromeDriverManager for easy setup
- **DO App Platform**: Uses system ChromeDriver from Docker container

## Cost Considerations

- **App Platform**: $12/month minimum for professional-xs
- **Database**: $7/month for basic PostgreSQL
- **Bandwidth**: Web scraping may incur data transfer costs