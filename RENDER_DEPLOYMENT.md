# Deploying to Render with Docker

This guide walks you through deploying the Ministering Interviews app to Render for **$1/month** (free web service + $1 persistent disk for SQLite).

**Important**: This app uses **Docker** to deploy because it requires Chrome and ChromeDriver for the LCR scraping feature. See `DOCKER_DEPLOYMENT.md` for technical details about why Docker is needed.

## Prerequisites

- GitHub account with this repository
- Render account (free signup at https://render.com)
- Repository must be pushed to GitHub with the `Dockerfile`

## Step 1: Verify Repository Files

Make sure these files are in your repository:
- ✅ `Dockerfile` - Defines the Docker image (includes Chrome/ChromeDriver)
- ✅ `requirements.txt` - Python dependencies (includes gunicorn)
- ✅ `.dockerignore` - Excludes unnecessary files from Docker build

**The `Dockerfile` is automatically detected and used by Render!**

## Step 2: Deploy to Render

### 2.1 Create New Web Service

1. Go to https://dashboard.render.com
2. Click **"New +"** → **"Web Service"** (NOT Blueprint!)
3. Connect your GitHub account if you haven't already
4. Select your `Ministering-Interviews` repository
5. Click **"Connect"**

### 2.2 Configure the Service

Render automatically detects the `Dockerfile` and configures for Docker deployment.

**Basic Settings**:
- **Name**: `ministering-interviews` (or customize for your subdomain)
  - This becomes: `https://ministering-interviews.onrender.com`
- **Region**: Oregon (US West) or closest to your users
- **Branch**: `main` (or your default branch)
- **Runtime**: Docker (auto-detected)

**Build & Deploy**:
- **Dockerfile Path**: `./Dockerfile` (auto-detected)
- **Docker Command**: Uses `CMD` from Dockerfile (gunicorn)

**Instance Type**:
- **Plan**: Free ($0/month)
  - Includes: 750 hours/month, 512 MB RAM, shared CPU
  - Perfect for ward/stake use

### 2.3 Configure Environment Variables

Scroll to **"Environment Variables"** section and add:

| Key | Value | Notes |
|-----|-------|-------|
| `SECRET_KEY` | Click "Generate" | Used for sessions and database encryption |
| `PORT` | (leave empty) | Auto-provided by Render |

**Important**: Email and SMS settings are configured in the app UI, NOT as environment variables!

### 2.4 Configure Persistent Disk (REQUIRED!)

Scroll to **"Disk"** section and click **"Add Disk"**:

- **Name**: `sqlite-data`
- **Mount Path**: `/app/instance`
- **Size**: 1 GB
- **Cost**: $1/month

This disk stores your SQLite database and persists across deployments.

### 2.5 Review and Create

1. Review all settings
2. Click **"Create Web Service"**

Render will now:
1. Clone your repository
2. Build Docker image (5-10 minutes first time)
   - Installs Python, Chrome, ChromeDriver, dependencies
3. Deploy the container
4. Assign you a URL: `https://your-service-name.onrender.com`

**First build takes 5-10 minutes** (subsequent builds are faster due to Docker caching)

## Step 3: Your App URL and SSL (HTTPS)

**Free Subdomain** (Recommended for most users):
- **URL Format**: `https://your-service-name.onrender.com`
- **SSL/HTTPS**: ✅ Automatically enabled and FREE
- **Certificate**: Auto-renewed Let's Encrypt certificate
- **No setup required**: Works immediately after deployment

Example: `https://ministering-interviews.onrender.com`

**Changing Your Subdomain**:
1. Go to your service dashboard
2. Click **"Settings"** → **"General"**
3. Edit the **"Name"** field
4. Your URL will update to: `https://[new-name].onrender.com`
5. SSL certificate automatically updates

**Using a Custom Domain** (Optional):

If you want a custom domain like `interviews.yourward.org` or `ministering.churchofjesuschrist.org`:

1. **Purchase a domain** (~$10-15/year from Namecheap, Google Domains, etc.)

2. **Add domain in Render**:
   - Go to your service dashboard
   - Click **"Settings"** → **"Custom Domain"**
   - Click **"Add Custom Domain"**
   - Enter your domain (e.g., `interviews.yourward.org`)
   - Click **"Save"**

3. **Configure DNS**:
   - Render will show you DNS records to add
   - Typically a CNAME record:
     ```
     Type: CNAME
     Name: interviews (or @ for root domain)
     Value: your-service-name.onrender.com
     ```
   - Add this record in your domain registrar's DNS settings

4. **Wait for SSL**:
   - SSL certificate auto-provisions in 5-10 minutes
   - Once ready, `https://interviews.yourward.org` will work with SSL

**Note**: Both the Render subdomain and custom domain work simultaneously. You can use both!

## Step 4: Configure Application Settings

### 4.1 Set Up Admin Account

1. Visit your Render URL: `https://your-app-name.onrender.com`
2. You'll be redirected to `/setup_admin`
3. Create your admin account:
   - **Name**: Your name
   - **Email**: Your email
   - **Password**: Secure password (min 6 characters)
   - **Confirm Password**: Same password

### 4.2 Configure Email Settings

1. Log in with your admin account
2. Click **"⚙️ Settings"** in the top menu
3. Go to **"Email Settings"** tab
4. Enter your SMTP details:
   - **SMTP Server**: `smtp.gmail.com` (for Gmail)
   - **SMTP Port**: `587`
   - **SMTP Username**: Your Gmail address
   - **SMTP Password**: Your Gmail app password (see below)
   - **From Email**: Your Gmail address
   - **From Name**: e.g., "Ward Ministering"
5. Click **"Save Email Settings"**

#### Getting a Gmail App Password

If using Gmail:
1. Go to https://myaccount.google.com/security
2. Enable 2-Factor Authentication (required)
3. Go to https://myaccount.google.com/apppasswords
4. Create an app password for "Mail"
5. Use this 16-character password in the settings

### 4.3 Configure SMS Settings (Optional)

1. Go to **"⚙️ Settings"** → **"SMS Settings"** tab
2. If you want SMS notifications:
   - Sign up for Twilio (or SignalWire) account
   - Enter your credentials:
     - **Account SID**
     - **Auth Token**
     - **From Phone Number**
   - Click **"Save SMS Settings"**
3. If you don't want SMS, leave it blank

## Step 5: Import Your Data

Choose one of these methods:

### Option A: Scrape from LCR (Recommended)
1. Click **"Scrape from LCR"** in the menu
2. Enter your LDS.org credentials
3. The system will automatically import all districts, companionships, and members

### Option B: Import from CSV
1. Click **"Import from CSV"** in the menu
2. Upload your CSV file with the required format
3. Review and confirm the import

## Step 6: Set Up Interview Slots

1. Click **"Manage Districts"**
2. For each district, click **"View Details"**
3. Click **"Generate Recurring Slots"**
4. Configure:
   - **Day of week** (e.g., Sunday)
   - **Start time** (e.g., 9:00 AM)
   - **Duration** (e.g., 15 minutes)
   - **Slots per day** (e.g., 20)
   - **Number of weeks** (e.g., 4)
   - **Max members per slot** (e.g., 10)
5. Click **"Generate Slots"**

## Ongoing Maintenance

### Database Backups

**IMPORTANT**: Render doesn't automatically backup your SQLite database. You should:

1. Periodically download backups from Render's dashboard:
   - Go to your service → **"Shell"** tab
   - Run: `cp instance/interviews.db /tmp/backup.db`
   - Download via SFTP or by adding a download endpoint

2. Or add a backup route to your app (recommended):
   ```python
   @app.route('/admin/backup_database')
   @admin_required
   def backup_database():
       return send_file('instance/interviews.db', as_attachment=True,
                       download_name=f'interviews-backup-{datetime.now().strftime("%Y%m%d")}.db')
   ```

### Monitoring

- Check logs in Render dashboard: Your Service → **"Logs"** tab
- Monitor disk usage: Your Service → **"Metrics"** tab
- Set up notifications for service failures in Render settings

### Updating the App

When you push changes to GitHub:
1. Render will automatically detect the changes
2. It will rebuild and redeploy your app
3. Your database will persist through deployments
4. Check the **"Events"** tab to monitor deployment progress

## Troubleshooting

### App Won't Start
- Check logs in Render dashboard
- Verify `requirements.txt` has all dependencies
- Ensure `gunicorn` is in requirements.txt

### Database Not Persisting
- Verify the disk is mounted at `/opt/render/project/src/instance`
- Check disk status in Render dashboard
- The `instance/` folder must match the mount path

### Email Not Sending
- Verify SMTP settings in ⚙️ Settings
- For Gmail, ensure 2FA is enabled and you're using an app password
- Check less secure app access is NOT required (use app password instead)

### ChromeDriver/Selenium Issues (LCR Scraping)
- Render's free tier includes Chrome/ChromeDriver
- If scraping fails, check logs for version mismatches
- May need to update ChromeDriver version in `app_scraper.py` lines 54-55

## Cost Breakdown

### Monthly Costs
- **Web Service**: $0/month (Free tier - runs 24/7, no cold starts)
- **Persistent Disk (1GB)**: $1/month
- **Total**: **$1/month**

### What's Included (Free)
- ✅ **Render Subdomain**: `https://your-app.onrender.com`
- ✅ **SSL/HTTPS Certificate**: Auto-renewed, no configuration needed
- ✅ **Custom Domain Support**: Add unlimited custom domains
- ✅ **SSL for Custom Domains**: Free auto-provisioned certificates
- ✅ **Automatic HTTPS Redirect**: HTTP requests redirect to HTTPS
- ✅ **Auto-Deploy**: Automatic deployments from GitHub

### Additional Costs (Optional)
- **Custom Domain Registration**: $10-15/year (if you want `interviews.yourward.org` instead of `.onrender.com`)
  - Purchase from Namecheap, Google Domains, Cloudflare, etc.
  - Not required - the free `.onrender.com` subdomain works perfectly

## Security Notes

1. **Never commit secrets**: Email passwords, Twilio credentials are stored in the database (encrypted), not in code
2. **Use strong admin password**: This protects access to all data
3. **HTTPS included**: Render provides free SSL certificates automatically
4. **Database encryption**: SystemConfig uses Fernet encryption for sensitive data

## Support

- Render Documentation: https://render.com/docs
- Render Community: https://community.render.com
- App Issues: Check your GitHub repository issues page
