# Deploying to PythonAnywhere (Free Tier)

This guide walks you through deploying the **Minimal App** to PythonAnywhere's free tier.

> **Note:** The Full App (with Selenium/Chrome) will NOT work on PythonAnywhere. Use the Minimal App with the Local Scraper and Flutter App for full functionality.

---

## ⚠️ Important: Monthly Renewal Required

Free accounts require you to **log in once per month** and click the **"Run until 1 month from today"** button on the Web tab to keep your site running.

- PythonAnywhere will email you a week before the site is disabled
- If you forget, your site goes offline (but your files remain)
- Paid accounts ($5/mo) stay up forever without this step

---

## ⚠️ Important: Email Limitations on Free Tier

**Before you begin**, be aware that PythonAnywhere's free tier has strict outbound network restrictions:

| Email Method | Works on Free Tier? |
|--------------|---------------------|
| **Gmail SMTP** | ✅ Yes (special exception) |
| Outlook/Office365 SMTP | ❌ Blocked |
| Yahoo SMTP | ❌ Blocked |
| Other SMTP servers | ❌ Blocked |
| Mailgun/SendGrid (HTTP API) | ✅ Yes |
| **Flutter App** (from your phone) | ✅ Yes - recommended! |

### Your Options:

1. **Use Gmail** - Configure Gmail SMTP with an App Password (see Email Configuration section below)

2. **Use the Flutter App** - The mobile app can send individual SMS and emails directly from your phone.
   - **Individual notifications**: Sent from your phone (bypasses server restrictions)
   - **Bulk notifications**: Still uses the server's email settings (requires Gmail on free tier)

3. **Upgrade to paid account** ($5/month) - Removes all outbound restrictions

**Bottom line:** If you want to send any email from the server (including bulk notifications), you need Gmail configured.

---

## Prerequisites

- Windows PC with the project files
- Web browser

---

## Step 1: Create a Free PythonAnywhere Account

1. Go to [https://www.pythonanywhere.com](https://www.pythonanywhere.com)
2. Click **"Pricing & signup"**
3. Click **"Create a Beginner account"** (Free)
4. Fill in username, email, and password
5. Verify your email address

Your site will be available at: `https://YOURUSERNAME.pythonanywhere.com`

---

## Step 2: Create the Web App

1. Log into PythonAnywhere
2. Go to the **Web** tab
3. Click **"Add a new web app"**
4. Click **Next** (accept the free `yourusername.pythonanywhere.com` domain)
5. Select **Flask**
6. Select **Python 3.13**
7. Accept the default path it suggests and click **Next**
8. You'll configure the correct paths in Steps 8 and 9

---

## Step 3: Create the Deployment Zip File

On your **Windows PC**:

1. Navigate to your project folder
2. Run the zip script:
   ```
   deploy-scripts\zip\zip-minimal.bat
   ```
3. When prompted "Include .env file?", type **N** and press Enter
4. This creates `deploy-minimal-YYYYMMDD-HHMM.zip` in your project root

---

## Step 4: Upload the Zip File

1. In PythonAnywhere, go to the **Files** tab
2. Navigate to `/home/YOURUSERNAME/mysite/`
   - If the `mysite` folder doesn't exist, click **"New directory"** to create it
3. Click **"Upload a file"**
4. Select your `deploy-minimal-XXXXXXXX-XXXX.zip` file
5. Wait for upload to complete

---

## Step 5: Unzip the Files

1. Go to the **Consoles** tab
2. Under "Start a new console", click **Bash**
3. Run these commands:

```bash
# Navigate to your site folder
cd ~/mysite

# Unzip the deployment file (replace with your actual filename)
unzip deploy-minimal-*.zip

# Verify files are there
ls -la
```

You should see:
- `app.py`
- `requirements.txt`
- `core/` folder
- `templates/` folder

---

## Step 6: Create the Instance Folder

The database needs a folder to live in. In the **Bash console**:

```bash
mkdir -p ~/mysite/instance
```

---

## Step 7: Install Python Dependencies

Still in the **Bash console**:

```bash
cd ~/mysite
pip install --user -r requirements.txt
```

Wait for all packages to install. You may see some warnings about dependency conflicts - these can usually be ignored if the install completes successfully.

---

## Step 8: Configure the WSGI File

1. Go to the **Web** tab
2. Scroll down to **Code** section
3. Click on the **WSGI configuration file** link
   - It will be something like `/var/www/yourusername_pythonanywhere_com_wsgi.py`
4. Replace the entire contents with:

```python
import sys

# Add your project directory to the sys.path
project_home = '/home/YOURUSERNAME/mysite'
if project_home not in sys.path:
    sys.path = [project_home] + sys.path

# Import Flask app (must be called "application" for WSGI)
from app import app as application  # noqa
```

> **Important:** Replace `YOURUSERNAME` with your actual PythonAnywhere username!

5. Click **Save**

---

## Step 9: Update Web App Settings

On the **Web** tab, verify these settings:

| Setting | Value |
|---------|-------|
| **Source code** | `/home/YOURUSERNAME/mysite` |
| **Working directory** | `/home/YOURUSERNAME/mysite` |
| **WSGI configuration file** | `/var/www/yourusername_pythonanywhere_com_wsgi.py` |
| **Python version** | 3.10 or 3.13 |

---

## Step 10: Reload and Test

1. On the **Web** tab, click the green **Reload** button
2. Click the link to your site: `https://yourusername.pythonanywhere.com`
3. You should see the login page!

---

## Troubleshooting

### Check the Error Log

If you see "Something went wrong", check the error log:

1. Go to **Web** tab
2. Scroll to **Log files**
3. Click **Error log**

### Common Errors

| Error | Solution |
|-------|----------|
| `ModuleNotFoundError: No module named 'flask'` | Run `pip install --user -r requirements.txt` |
| `ModuleNotFoundError: No module named 'flask_user'` | Run `pip install --user -r requirements.txt` |
| `unable to open database file` | Run `mkdir -p ~/mysite/instance` |
| `No module named 'app'` | Check WSGI file path matches your actual file location |
| `ImportError` from core module | Make sure `core/` folder was unzipped correctly |

### Verify Files Exist

In Bash console:
```bash
ls -la ~/mysite/
ls -la ~/mysite/core/
ls -la ~/mysite/templates/
```

### Re-upload if Needed

If files are missing, you can delete and re-upload:
```bash
cd ~/mysite
rm -rf app.py requirements.txt core/ templates/
# Then upload and unzip again
```

---

## Email Configuration (Important!)

**Free PythonAnywhere accounts can ONLY send email via Gmail SMTP.**

Other email providers (Outlook, Yahoo, etc.) are blocked by their firewall.

### Gmail Setup:

1. In your app's System Settings → Email, use these settings:
   - SMTP Server: `smtp.gmail.com`
   - Port: `587`
   - TLS: Yes
   - Username: `youremail@gmail.com`
   - Password: (use an App Password - see below)

### Alternative: Use Flutter App

If you can't use Gmail, use the **Flutter mobile app** to send notifications from your phone instead. This bypasses all server-side email restrictions.

---

## How to Create a Gmail App Password

Gmail requires an **App Password** instead of your regular password for SMTP access. Here's how to create one:

### Step 1: Enable 2-Step Verification (Required)

1. Go to [https://myaccount.google.com](https://myaccount.google.com)
2. Click **Security** in the left sidebar
3. Under "How you sign in to Google", click **2-Step Verification**
4. Follow the prompts to enable it (you'll need your phone)

### Step 2: Generate an App Password

1. Go to [https://myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
   - Or: Google Account → Security → 2-Step Verification → App passwords (at the bottom)
2. You may need to sign in again
3. Click **Select app** → choose **Mail**
4. Click **Select device** → choose **Other** → type "Ministering App"
5. Click **Generate**
6. Google will show a **16-character password** (like `abcd efgh ijkl mnop`)
7. **Copy this password** - you won't be able to see it again!

### Step 3: Use the App Password

In your app's **System Settings → Email**:

| Setting | Value |
|---------|-------|
| SMTP Server | `smtp.gmail.com` |
| Port | `587` |
| Use TLS | Yes |
| Username | `youremail@gmail.com` |
| Password | `abcdefghijklmnop` (the 16-char App Password, no spaces) |

### Troubleshooting Gmail

| Problem | Solution |
|---------|----------|
| "App passwords" option not visible | Enable 2-Step Verification first |
| Authentication failed | Make sure you're using the App Password, not your regular password |
| Still not working | Try generating a new App Password |
| "Less secure apps" message | Ignore - App Passwords are the secure method |

---

## Updating Your Deployment

To deploy updates:

1. Create a new zip file on your Windows PC
2. Upload to PythonAnywhere via Files tab
3. In Bash console:
   ```bash
   cd ~/mysite
   unzip -o deploy-minimal-*.zip
   ```
   (The `-o` flag overwrites existing files)
4. Go to Web tab and click **Reload**

---

## Quick Reference Commands

```bash
# Navigate to site
cd ~/mysite

# Check what's there
ls -la

# Unzip (first time)
unzip deploy-minimal-*.zip

# Unzip (update - overwrite)
unzip -o deploy-minimal-*.zip

# Create instance folder
mkdir -p instance

# Install dependencies
pip install --user -r requirements.txt

# Check Python version
python --version

# View recent errors
tail -50 /var/log/yourusername.pythonanywhere.com.error.log
```

---

## Limitations of Free Tier

| Feature | Free Tier |
|---------|-----------|
| Custom domain | ❌ No |
| Always-on | ✅ Yes (but requires monthly button click) |
| CPU/bandwidth | Limited |
| Outbound connections | Whitelist only |
| Email | Gmail SMTP or HTTP APIs (SendGrid, Mailgun) |
| SSH/SFTP access | ❌ No |
| Storage | 512 MB |

For production use with more features, consider upgrading to a paid account ($5/month) or using a different host like Render or DigitalOcean.

---

## Next Steps

1. **Create admin account** - Visit your site and set up the first admin user
2. **Configure email** - System Settings → Email (Gmail only on free tier)
3. **Import data** - Use Local Scraper to create CSV, then import via web interface
4. **Setup interview time slots** - Click on a district → Manage Slots → Create recurring slots
5. **Send notifications** - Use Flutter App on your phone, or Gmail from the server
