# DigitalOcean App Platform Deployment Guide

This guide covers deploying the Ministering Interviews application to DigitalOcean App Platform with two storage options.

## Table of Contents
- [Prerequisites](#prerequisites)
- [Option 1: Managed PostgreSQL (Recommended)](#option-1-managed-postgresql-recommended)
- [Option 2: SQLite with Persistent Disk](#option-2-sqlite-with-persistent-disk)
- [Environment Variables](#environment-variables)
- [Post-Deployment Setup](#post-deployment-setup)
- [Database Migrations](#database-migrations)
- [Troubleshooting](#troubleshooting)
- [Cost Comparison](#cost-comparison)
- [Backup Strategies](#backup-strategies)

---

## Prerequisites

### 1. GitHub Repository
Your code must be in a GitHub repository:
```bash
cd C:\dev\Ministering-Interviews
git init  # If not already a git repo
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR-USERNAME/ministering-interviews.git
git push -u origin main
```

### 2. DigitalOcean Account
- Sign up at https://www.digitalocean.com
- Add payment method (credit card or PayPal)
- Consider using a referral code for $200 free credit

### 3. Update Configuration Files
Edit `.do/app-postgres.yaml` or `.do/app-sqlite-disk.yaml`:
- Replace `your-username/ministering-interviews` with your actual GitHub repo path
- Example: `jsmith/ministering-interviews`

### 4. Generate SECRET_KEY
Run this command to generate a secure secret key:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```
Save this value - you'll need it for environment variables.

---

## Option 1: Managed PostgreSQL (Recommended)

### Advantages
✅ **Automatic backups** - Daily snapshots with point-in-time recovery
✅ **Better performance** - Optimized for concurrent access
✅ **Horizontal scaling** - Can add more app instances
✅ **Production-ready** - Industry standard for web apps
✅ **Connection pooling** - Better resource management

### Disadvantages
❌ **Higher cost** - Starts at $15/mo (vs $5/mo for app only)
❌ **More complex** - Requires database management knowledge

### Deployment Steps

#### Step 1: Deploy via DigitalOcean Dashboard

1. **Log in to DigitalOcean** → Go to https://cloud.digitalocean.com

2. **Create App**
   - Click "Create" → "Apps"
   - Select "GitHub" as source
   - Authorize DigitalOcean to access your GitHub
   - Select your repository: `your-username/ministering-interviews`
   - Select branch: `main`

3. **Configure App**
   - **Source Directory**: `/` (root)
   - **Autodeploy**: Enable (deploys automatically on git push)
   - Click "Next"

4. **Import from app.yaml**
   - Click "Import from" → "Upload file"
   - Upload `.do/app-postgres.yaml`
   - OR click "Edit" and paste the contents manually

5. **Set Environment Variables** (in App Platform dashboard)
   - Click on the "web" component
   - Go to "Environment Variables" section
   - Add/edit these variables:

   ```
   SECRET_KEY = <paste the key you generated earlier>
   MAIL_USERNAME = your-smtp-email@example.com
   MAIL_PASSWORD = your-smtp-app-password
   ```

   **Optional SMS Variables** (if using Twilio/SignalWire/AWS SNS):
   ```
   # For Twilio:
   TWILIO_ACCOUNT_SID = ACxxxxxxxxxxxxxxxxx
   TWILIO_AUTH_TOKEN = your_twilio_auth_token
   TWILIO_PHONE_NUMBER = +15551234567

   # For SignalWire:
   SIGNALWIRE_PROJECT_ID = your_project_id
   SIGNALWIRE_AUTH_TOKEN = PTxxxxxxxxxxxxxx
   SIGNALWIRE_SPACE_URL = your-space.signalwire.com
   SIGNALWIRE_PHONE_NUMBER = +15551234567

   # For AWS SNS:
   AWS_ACCESS_KEY_ID = AKIAXXXXXXXXX
   AWS_SECRET_ACCESS_KEY = your_secret_key
   AWS_REGION = us-east-1
   AWS_SNS_SENDER_ID = YourSenderID
   ```

6. **Review Database Configuration**
   - The database should be automatically configured from the YAML
   - Name: `ministering-db`
   - Engine: PostgreSQL 15
   - Size: `db-s-dev-database` (free) or `db-s-1vcpu-1gb` ($15/mo)
   - **Important**: Change `production: false` to `production: true` for daily backups

7. **Review and Launch**
   - Review all settings
   - Click "Create Resources"
   - Wait 5-10 minutes for build and deployment

#### Step 2: Deploy via doctl CLI (Alternative)

If you prefer command-line deployment:

```bash
# Install doctl
# Windows (via chocolatey):
choco install doctl

# macOS:
brew install doctl

# Authenticate
doctl auth init

# Create app from spec
doctl apps create --spec .do/app-postgres.yaml

# Get app ID
doctl apps list

# Set environment variables (replace APP_ID)
doctl apps update APP_ID --env SECRET_KEY="your-secret-key-here"
doctl apps update APP_ID --env MAIL_USERNAME="your-email@example.com"
doctl apps update APP_ID --env MAIL_PASSWORD="your-password"
```

### Step 3: Verify Deployment

1. **Check Build Logs**
   - Go to your app in DO dashboard
   - Click on "Runtime Logs" tab
   - Look for successful startup messages

2. **Access Your App**
   - URL will be: `https://ministering-interviews-xxxxx.ondigitalocean.app`
   - First load may take 30-60 seconds (cold start)

3. **Verify Database Connection**
   - Check logs for "Connected to database" message
   - Should show PostgreSQL connection, not SQLite

---

## Option 2: SQLite with Persistent Disk

### Advantages
✅ **Lower cost** - Only $5/mo for app ($0 for storage up to 5GB)
✅ **Simpler** - No database to manage
✅ **Easier local development** - Same database type as local
✅ **Zero configuration** - Works out of the box

### Disadvantages
❌ **No automatic backups** - Must implement manual backup strategy
❌ **Cannot scale horizontally** - Limited to 1 instance
❌ **Single file limitations** - Write locks can cause slowdowns
❌ **Manual backup required** - Risk of data loss

### Deployment Steps

#### Step 1: Deploy via DigitalOcean Dashboard

1. **Follow same steps as Option 1**, but use `.do/app-sqlite-disk.yaml` instead

2. **Key Differences**:
   - No database component (removed from YAML)
   - Persistent storage mounted at `/data`
   - SQLite database will be at `/data/interviews.db`

3. **Important**: In the YAML, ensure `instance_count: 1`
   - Persistent disks only work with single instances
   - Cannot scale to multiple instances

#### Step 2: Verify Persistent Storage

After deployment:

1. Check logs to confirm database location:
   ```
   Using SQLite database at: /data/interviews.db
   ```

2. Verify persistent disk is mounted:
   - Go to App → Settings → Storage
   - Should show "interviews-data" mounted at `/data`

---

## Environment Variables

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `SECRET_KEY` | Flask session encryption key | Generate with `secrets.token_hex(32)` |
| `MAIL_USERNAME` | SMTP email address | `noreply@yourdomain.com` |
| `MAIL_PASSWORD` | SMTP app password | `abcd efgh ijkl mnop` |

### Optional Variables (SMS)

#### Twilio
| Variable | Description |
|----------|-------------|
| `TWILIO_ACCOUNT_SID` | Twilio account SID |
| `TWILIO_AUTH_TOKEN` | Twilio auth token |
| `TWILIO_PHONE_NUMBER` | Your Twilio phone number |

#### SignalWire
| Variable | Description |
|----------|-------------|
| `SIGNALWIRE_PROJECT_ID` | SignalWire project ID |
| `SIGNALWIRE_AUTH_TOKEN` | SignalWire auth token |
| `SIGNALWIRE_SPACE_URL` | Your space URL (e.g., `yourspace.signalwire.com`) |
| `SIGNALWIRE_PHONE_NUMBER` | Your SignalWire phone number |

#### AWS SNS
| Variable | Description |
|----------|-------------|
| `AWS_ACCESS_KEY_ID` | AWS access key |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key |
| `AWS_REGION` | AWS region (e.g., `us-east-1`) |
| `AWS_SNS_SENDER_ID` | Optional sender ID |

### Email Configuration (Gmail Example)

For Gmail SMTP:
```
MAIL_USERNAME = your.email@gmail.com
MAIL_PASSWORD = <16-character app password>
```

**How to get Gmail App Password**:
1. Go to https://myaccount.google.com/security
2. Enable 2-Step Verification
3. Go to "App passwords"
4. Generate password for "Mail"
5. Copy the 16-character password (no spaces)

---

## Post-Deployment Setup

### 1. Create First Admin User

Visit your app URL for the first time:
```
https://your-app-name.ondigitalocean.app
```

You'll be redirected to the admin setup page:
1. Enter admin email address
2. Set admin password
3. Click "Create Admin User"

### 2. Configure System Settings

After logging in:
1. Go to **System Settings** (gear icon)
2. Configure email settings:
   - SMTP server
   - Port (587 for TLS, 465 for SSL)
   - Username and password
   - Test email send
3. Configure SMS settings (optional):
   - Select provider (Twilio/SignalWire/AWS SNS)
   - Enter credentials
   - Configure SMS mode (one-way/two-way)
4. Configure reminder schedule:
   - Day of week
   - Time of day
   - Enable/disable reminders

### 3. Import Your Data

Choose one of three methods:

#### Method 1: Scrape from LCR (Church Members)
1. Go to **Admin** → **Scrape from LCR**
2. Enter your LDS.org credentials
3. System will import districts, companionships, and members
4. Review data and confirm import

#### Method 2: CSV Upload
1. Prepare CSV file with headers:
   ```
   District,Interviewer,Companionship Name,Member Name,Phone,Email
   ```
2. Go to **Admin** → **Import from CSV**
3. Upload file
4. Review and confirm import

#### Method 3: Manual Entry
1. Go to **Manage Districts**
2. Create districts manually
3. Add companionships
4. Add members

### 4. Create Interview Slots

For each district:
1. Go to **Manage Districts** → Select district → **Manage Slots**
2. Configure slot settings:
   - Day of week
   - Start time
   - Duration (minutes)
   - Number of consecutive slots
   - Number of weeks
3. Click **Generate Slots**
4. Review and adjust as needed

### 5. Send Notifications

1. Go to **Admin Calendar** or **Notification Report**
2. Click **Send All Notifications** to send to all members
3. Or send individually from Notification Report

---

## Database Migrations

### Automatic Migrations (Recommended)

Flask-Migrate is configured to run automatically on deployment. Database schema will be created/updated on first run.

### Manual Migration (if needed)

If you need to run migrations manually:

```bash
# Access your app's console (via DO dashboard or doctl)
doctl apps logs APP_ID --type run

# Run migrations
flask db upgrade

# Create new migration (after model changes)
flask db migrate -m "Description of changes"
```

### PostgreSQL Only: Access Database Directly

```bash
# Get database connection string
doctl apps list
doctl apps spec get APP_ID

# Connect with psql
doctl databases db shell DATABASE_ID

# Or get connection details
doctl databases connection DATABASE_ID
```

---

## Troubleshooting

### Build Failures

**Issue**: Docker build fails with Chrome/ChromeDriver errors

**Solution**: Check Dockerfile Chrome version matching:
```dockerfile
# Line 45-46 in Dockerfile
CHROME_VERSION=$(google-chrome --version | grep -oP '\d+\.\d+\.\d+\.\d+' | cut -d'.' -f1)
```
Chrome and ChromeDriver versions must match. Update if needed.

---

### Application Won't Start

**Issue**: App shows "Failed to start" or crashes immediately

**Solutions**:
1. Check Runtime Logs for error messages
2. Verify all required environment variables are set
3. Check SECRET_KEY is properly set
4. For PostgreSQL: Verify DATABASE_URL is automatically set by DO
5. For SQLite: Verify persistent disk is mounted at `/data`

---

### Database Connection Errors (PostgreSQL)

**Issue**: `psycopg2.OperationalError: could not connect to server`

**Solutions**:
1. Verify database is running (check DO dashboard)
2. Check DATABASE_URL environment variable is set
3. Wait 1-2 minutes for database to fully provision
4. Check database cluster health in DO dashboard

---

### SQLite Permission Errors

**Issue**: `OperationalError: unable to open database file`

**Solutions**:
1. Verify persistent disk is mounted (`doctl apps list --format ID,Name,ActiveDeployment.Storage`)
2. Check `/data` directory exists and is writable
3. Verify `instance_count: 1` (SQLite doesn't work with multiple instances)
4. Check logs for filesystem errors

---

### Chrome/Selenium Errors During Scraping

**Issue**: Scraping fails with Chrome errors

**Solutions**:
1. Increase timeout in app.yaml: `timeout_seconds: 120`
2. Upgrade instance size to `basic-xs` or higher (more memory)
3. Check Chrome is installed: Look for "Chrome version: XXX" in build logs
4. Verify ChromeDriver matches Chrome version

---

### Email Not Sending

**Issue**: Email notifications fail silently

**Solutions**:
1. Go to **System Settings** → Test email send
2. Check SMTP credentials are correct
3. For Gmail: Verify app password (not regular password)
4. Check SMTP port: 587 (TLS) or 465 (SSL)
5. Review Runtime Logs for email errors

---

### Performance Issues

**Issue**: App is slow or times out

**Solutions**:
1. Upgrade instance size:
   - `basic-xs` ($12/mo): 512MB RAM, 1 vCPU
   - `basic-s` ($24/mo): 1GB RAM, 1 vCPU
2. For PostgreSQL: Upgrade database size
3. Add more workers to gunicorn (in run_command):
   ```yaml
   run_command: gunicorn --bind 0.0.0.0:8080 --workers 4 --timeout 120 app:app
   ```
4. Enable Redis caching (requires separate Redis instance)

---

## Cost Comparison

### Option 1: PostgreSQL

| Component | Size | Monthly Cost |
|-----------|------|--------------|
| App (Basic XXS) | 512MB RAM | $5.00 |
| PostgreSQL (Dev) | 10MB storage | FREE |
| **Total (Development)** | | **$5.00/mo** |
| | | |
| App (Basic XS) | 1GB RAM | $12.00 |
| PostgreSQL (Production) | 10GB storage | $15.00 |
| **Total (Production)** | | **$27.00/mo** |

### Option 2: SQLite + Persistent Disk

| Component | Size | Monthly Cost |
|-----------|------|--------------|
| App (Basic XXS) | 512MB RAM | $5.00 |
| Persistent Disk | 5GB | FREE |
| **Total** | | **$5.00/mo** |

### Cost Optimization Tips

1. **Start with free PostgreSQL tier** for testing ($5/mo total)
2. **Use SQLite for low-traffic deployments** (1 ward, <100 members)
3. **Upgrade to paid PostgreSQL** when:
   - You need backups
   - Traffic increases (>50 concurrent users)
   - You want to scale horizontally
4. **Reserve instances** for 10-40% discount (1-3 year commitment)

---

## Backup Strategies

### PostgreSQL (Automatic)

**Included Backups**:
- Daily automated backups (when `production: true`)
- 7-day retention on basic plan
- Point-in-time recovery available
- Stored in DO's object storage

**Manual Backups**:
```bash
# Create backup via doctl
doctl databases backup create DATABASE_ID

# List backups
doctl databases backup list DATABASE_ID

# Download backup
pg_dump DATABASE_URL > backup.sql
```

### SQLite (Manual Required)

**Important**: You MUST implement manual backups for SQLite!

#### Option A: Scheduled Backups via DO Functions

Create a DigitalOcean Function that runs daily:

```python
# backup_function.py
import subprocess
import datetime
from digitalocean import Manager

def main(args):
    # Download database from persistent disk
    subprocess.run(['doctl', 'apps', 'exec', 'APP_ID',
                   '--', 'cp', '/data/interviews.db', './backup.db'])

    # Upload to Spaces (DO's S3-compatible storage)
    date = datetime.date.today().strftime('%Y-%m-%d')
    filename = f'backup-{date}.db'
    # Upload code here

    return {"status": "success"}
```

#### Option B: Manual Weekly Backups

```bash
# 1. Access app console
doctl apps exec APP_ID

# 2. Copy database file
cp /data/interviews.db /tmp/backup.db

# 3. Download to local machine
doctl apps exec APP_ID -- cat /data/interviews.db > backup-$(date +%Y-%m-%d).db
```

#### Option C: Export to CSV

Use the app's built-in export feature:
1. Go to **Admin** → **Export Data**
2. Download CSV files
3. Store in version control or cloud storage

**Recommended Schedule**:
- **Daily**: Automated if using PostgreSQL
- **Weekly**: Manual download if using SQLite
- **Before major changes**: Always create backup before:
  - Software updates
  - Data imports
  - Configuration changes

---

## Next Steps

1. ✅ Deploy app using your chosen option
2. ✅ Configure environment variables
3. ✅ Create admin user
4. ✅ Configure system settings (email, SMS)
5. ✅ Import your data
6. ✅ Create interview slots
7. ✅ Send test notifications
8. ✅ Set up backup strategy
9. ✅ Monitor logs for errors
10. ✅ Upgrade resources as needed

## Support Resources

- **DigitalOcean Docs**: https://docs.digitalocean.com/products/app-platform/
- **Flask Docs**: https://flask.palletsprojects.com/
- **PostgreSQL Docs**: https://www.postgresql.org/docs/
- **DO Community**: https://www.digitalocean.com/community/

---

## Migration from Local to Production

If you have local data you want to migrate:

### PostgreSQL Option
```bash
# 1. Export local SQLite database
sqlite3 instance/interviews.db .dump > local_data.sql

# 2. Convert to PostgreSQL format (may need adjustments)
# Install pgloader: https://github.com/dimitri/pgloader
pgloader instance/interviews.db postgresql://user:pass@host/db

# Or manually:
# - Export data to CSV
# - Use CSV import feature in the app
```

### SQLite Option
```bash
# 1. Copy local database to server
doctl apps exec APP_ID -- mkdir -p /data
cat instance/interviews.db | doctl apps exec APP_ID -- tee /data/interviews.db

# 2. Restart app
doctl apps restart APP_ID
```

---

**Last Updated**: 2025-01-16
**App Version**: 1.0
**Tested on**: DigitalOcean App Platform (2025)
