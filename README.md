# 📅 Ministering Interview Scheduler

> A comprehensive web application for managing ministering interviews in LDS church wards. Built with Flask, featuring automated scheduling, notifications, and optional LCR data scraping.

[![Built with AI](https://img.shields.io/badge/Built%20with-AI%20(Claude)-5865F2?style=flat-square)](https://claude.ai)
[![Python](https://img.shields.io/badge/Python-3.9+-blue?style=flat-square)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0+-green?style=flat-square)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

---

## 🎯 Overview

This application streamlines the process of scheduling and conducting quarterly ministering interviews in LDS wards. It manages interview time slots, sends notifications via email (and optionally SMS), and allows members to self-schedule their interviews online.

---

## 📦 Two Editions Available

The app comes in two editions to fit your deployment needs:

| Feature | Minimal App (`app.py`) | Full App (`app_full.py`) |
|---------|------------------------|--------------------------|
| Core scheduling & booking | ✅ | ✅ |
| Email notifications | ✅ | ✅ |
| CSV data import | ✅ | ✅ |
| LCR data import | 📂 Use Local Scraper on your PC | ✅ Server-side scraping |
| SMS notifications | 📱 Use Flutter App on your phone | ✅ Twilio/AWS/SignalWire |
| Docker image size | ~400MB | ~1.2GB |
| Memory footprint | Low | Higher |
| **Best for** | Free-tier hosting (PythonAnywhere, Oracle Cloud) | Full-featured deployments |

### Minimal App Workflow

If you choose the Minimal App, you can still get full functionality using companion tools:

1. **LCR Data Import**: Use the **Local Scraper** (`local-scraper/`) on your Windows PC to scrape LCR data. It generates a CSV file you can upload through the web app's CSV import.

2. **SMS & Email Notifications**: Use the **Flutter Mobile App** to handle notifications. The app pulls pending notifications from the web API and sends them using your phone's native SMS and email capabilities - no SMS gateway costs!

### Full App Workflow

The Full App handles everything server-side:
- Scrapes LCR directly from the web interface
- Sends SMS via Twilio, AWS SNS, or SignalWire
- Sends email via SMTP

### Which Files to Use

| Edition | Entry Point | Requirements | Dockerfile |
|---------|-------------|--------------|------------|
| Minimal | `app.py` | `requirements.txt` | `Dockerfile` |
| Full | `app_full.py` | `requirements-full.txt` | `Dockerfile.full` |

**🤖 Note:** This application was created almost 100% using AI assistance (Initailly Grok Code fast 1 and then Claude Code by Anthropic). From the initial concept to the final implementation, AI guided the architecture, wrote the code, designed the database schema, and implemented features. This showcases the power of AI-assisted development in creating full-featured web applications.

---

## ✨ Key Features

### 👥 **Data Import**
- **LCR Web Scraping** *(Full App)*: Automatically extract companionship data from the Church's LCR website
- **Local Scraper** *(Minimal App)*: Run on your Windows PC to generate CSV for upload
- **CSV Import** *(Both)*: Manual import option for flexibility
- **Smart Matching**: Automatically matches and updates existing members by email to prevent duplicates
- **Preview Before Import**: Review all data before committing changes

### 📆 **Intelligent Scheduling**
- **Recurring Slot Generation**: Create multiple interview slots across weeks with a single form
- **Companionship-Based Restrictions**: Once a slot is booked, only companionship members can book the same slot
- **Capacity Management**: Set maximum members per slot (default: 10)
- **Quarter-Based Organization**: Automatically organizes slots by calendar quarters
- **Conflict Prevention**: Prevents overlapping or duplicate bookings

### 📧 **Notifications**
- **Email Notifications** *(Both)*: Configurable SMTP support (Gmail, Outlook, etc.)
- **Server-Side SMS** *(Full App)*: Support for three providers:
  - **AWS SNS** (Recommended - lowest cost ~$1.94/month)
  - **Twilio** (Most reliable - ~$4.47/month)
  - **SignalWire** (Best features/cost - ~$2.10/month)
- **Flutter Mobile App** *(Minimal App)*: Send SMS/email from your phone at zero cost
- **Personal Contact Info**: Include admin contact details in messages for direct replies
- **Test Functionality**: Send test emails and SMS with detailed error reporting

### 🔐 **Security & Privacy**
- **User Authentication**: Flask-User integration with role-based access control
- **Encrypted Credentials**: All API keys, passwords, and tokens encrypted with Fernet (AES)
- **Unique Member Tokens**: 32-character hex tokens for secure scheduling links
- **Admin-Only Access**: Restricted management functions

### 📊 **Admin Dashboard**
- **Calendar View**: Visual overview of all scheduled interviews
- **District Management**: Organize by districts with assigned interviewers
- **Companionship View**: See all companionships and members at a glance
- **Booking Status**: Track who has and hasn't scheduled interviews
- **Bulk Operations**: Send notifications to all members at once

### 🎨 **Modern User Interface**
- **Bootstrap 5**: Clean, responsive design that works on all devices
- **Interactive Modals**: HTML confirmation dialogs instead of browser alerts
- **Flash Messages**: Color-coded success/error notifications
- **Sticky Tabs**: Settings tabs remember your position across page reloads
- **Live Previews**: See formatted messages before sending

### 🛠️ **Advanced Features**
- **Progress Tracking**: Real-time progress indicators for long-running operations
- **Member Reassignment**: Move members between companionships with automatic booking cancellation
- **Automated Reminders**: Scheduled reminders for members who haven't booked (configurable day/time)
- **District-Specific Validation**: Only send notifications to districts with available slots
- **Badge System**: Visual indicators for "You Booked" and "Companion Booked" slots

---

## 🚀 Quick Start

### Prerequisites
- Python 3.9 or higher
- pip (Python package manager)
- Git (optional, for cloning)

### Installation

1. **Clone or download the repository:**
   ```bash
   git clone https://github.com/jtkelley/Ministering-Interviews.git
   cd Ministering-Interviews
   ```

2. **Choose your edition and install dependencies:**

   **For Minimal App** (recommended for most users):
   ```bash
   pip install -r requirements.txt
   python app.py
   ```

   **For Full App** (with LCR scraping and SMS):
   ```bash
   pip install -r requirements-full.txt
   python app_full.py
   ```

3. **Access the application:**
   Open your browser to `http://localhost:8181`

4. **Complete setup through the web interface:**
   - All configuration (email, SMS, scheduler) is done through the web UI
   - Navigate to **Admin → System Settings** after first login

### Docker Deployment

**Minimal App:**
```bash
docker build -f Dockerfile -t ministering-min .
docker run -p 8181:8181 ministering-min
```

**Full App:**
```bash
docker build -f Dockerfile.full -t ministering-full .
docker run -p 8181:8181 ministering-full
```

**Note**: The `.env` file is included in the repository with a development-only SECRET_KEY. When deployed to production, the platform provides its own secure SECRET_KEY that overrides the development value.

---

## 📖 Usage Guide

### First-Time Setup

1. **Configure Email Settings:**
   - Navigate to **Admin → System Settings → Email**
   - Enter your SMTP server details (e.g., Gmail: `smtp.gmail.com:587`)
   - Add your email and app password
   - Click "Send Test Email" to verify

2. **Configure SMS Settings (Full App only, or use Flutter App):**
   - Navigate to **Admin → System Settings → SMS**
   - Click "📖 SMS Provider Setup Guide & Cost Comparison" for detailed instructions
   - Choose your provider (AWS SNS recommended for lowest cost)
   - Select **1-Way Messaging** for simplest setup
   - Enter your personal contact info for member replies
   - Test with "Send Test SMS"
   - **Alternative**: Use the Flutter mobile app to send notifications from your phone (no SMS gateway costs!)

3. **Import Companionship Data:**

   **Full App:** Navigate to **Admin → Scrape from LCR**
   - Enter your LDS Account credentials
   - Select your ward
   - Review the preview and confirm import

   **Minimal App:** Use the Local Scraper + CSV Import
   - Run `local-scraper/run_local_scraper.bat` on your Windows PC
   - Log into LCR when the browser opens
   - Save the generated CSV file
   - Upload via **Admin → Import from CSV** in the web app

### Regular Usage Workflow

1. **Create Interview Slots:**
   - Navigate to **Admin Dashboard**
   - Click on a district
   - Click "Manage Slots"
   - Use the form to generate recurring slots:
     - Select day of week (e.g., Monday)
     - Set start time (e.g., 18:00)
     - Set duration (e.g., 30 minutes)
     - Set number of slots per day (e.g., 3)
     - Set date range (e.g., 3 months)

2. **Send Notifications:**
   - Click "Send All Notifications" in the navbar
   - Or send to individual districts from the dashboard
   - Members receive personalized links via email/SMS

3. **Monitor Bookings:**
   - View the Admin Dashboard calendar
   - Green = has slots available
   - Members with bookings show their scheduled time
   - Click districts to see detailed companionship views

4. **Member Scheduling:**
   - Members receive a unique link via email/SMS
   - They click to see available time slots
   - "Companion Booked" badge shows if their companion already scheduled
   - Book a slot with one click
   - Can cancel and reschedule if needed

---

## 🛠️ Companion Tools

These standalone tools extend the Minimal App to provide full functionality without server-side dependencies.

### Local Scraper (Windows)

A desktop tool that scrapes LCR data using your local Chrome browser and saves it as a CSV file for upload to the web app.

**Location:** `local-scraper/`

**Usage:**
```bash
cd local-scraper
run_local_scraper.bat
```

**Features:**
- Opens a visible Chrome window so you can log into LCR
- Extracts all companionship data (districts, members, contact info)
- Saves to CSV format compatible with the web app's import
- Runs entirely on your PC - no server-side Chrome needed

**Requirements:**
- Windows PC with Chrome installed
- Python 3.9+ with packages from `local_requirements.txt`

### Flutter Mobile App

A mobile app that handles notifications using your phone's native SMS and email capabilities.

**Location:** `flutter_app/`

**Features:**
- Pulls pending notifications from the web app's API
- Sends SMS using your phone's messaging app (no Twilio costs!)
- Sends email using your phone's email client
- Works offline - queue notifications and send when ready
- Push notifications for new booking activity

**Why use it:**
- **Zero SMS costs** - uses your phone's unlimited texting plan
- **No API keys needed** - no Twilio/AWS/SignalWire setup
- **Works with Minimal App** - full notification capability without server dependencies

---

## 🏗️ Architecture

### Technology Stack

**Core (Both Editions):**
- **Backend**: Flask 3.0 (Python web framework)
- **Database**: SQLite (PostgreSQL recommended for production)
- **ORM**: SQLAlchemy (database abstraction)
- **Authentication**: Flask-User (user management and roles)
- **Email**: Flask-Mail (SMTP integration)
- **Security**: cryptography (Fernet encryption for credentials)
- **Scheduling**: APScheduler (automated reminders)
- **Frontend**: Bootstrap 5, JavaScript, Jinja2 templates

**Full App Additional:**
- **Web Scraping**: Selenium + ChromeDriver
- **SMS**: boto3 (AWS SNS), twilio, signalwire

### Database Schema

**Core Models:**
- `User` - Admin users with authentication
- `District` - Organizational units with interviewers
- `Companionship` - Companionships within districts
- `Member` - Individual members with unique tokens
- `InterviewSlot` - Available time slots with capacity
- `Booking` - Junction table linking members to slots
- `SystemConfig` - Application settings (encrypted)
- `IncomingSMS` - SMS message tracking (Phase 2)

**Key Relationships:**
- District → Companionships (one-to-many)
- Companionship → Members (one-to-many)
- Member → Bookings (one-to-many)
- InterviewSlot → Bookings (one-to-many with capacity limit)

### Project Structure

```
Ministering-Interviews/
├── app.py                      # Minimal app entry point
├── app_full.py                 # Full app entry point (with scraping + SMS)
├── requirements.txt            # Minimal dependencies
├── requirements-full.txt       # Full dependencies (includes Selenium, Twilio, etc.)
├── Dockerfile                  # Minimal Docker build (~400MB)
├── Dockerfile.full             # Full Docker build (~1.2GB with Chrome)
│
├── core/                       # Shared code between both editions
│   ├── __init__.py
│   ├── config.py               # App configuration
│   ├── models.py               # All database models
│   ├── services.py             # Email notification services
│   ├── shared.py               # Shared resources (mail, progress_store)
│   ├── import_merge.py         # CSV/data import logic
│   ├── utils/                  # Utility functions
│   │   ├── decorators.py       # @admin_required decorator
│   │   ├── encryption.py       # EncryptionHelper for credentials
│   │   └── helpers.py          # Helper functions
│   └── routes/                 # Core route blueprints
│       ├── public.py           # Public scheduling routes
│       ├── admin.py            # Admin routes
│       └── api.py              # API routes for Flutter app
│
├── features/                   # Optional feature modules (Full app only)
│   ├── scraping/               # LCR web scraping
│   │   ├── scraper.py          # Selenium scraping logic
│   │   └── routes.py           # Scraping route blueprint
│   └── sms/                    # SMS notifications
│       └── services.py         # Twilio/AWS/SignalWire integration
│
├── local-scraper/              # Standalone Windows scraper tool
│   ├── local_scraper.py        # Run on your PC to generate CSV
│   ├── run_local_scraper.bat   # Windows batch launcher
│   └── local_requirements.txt  # Scraper-only dependencies
│
├── flutter_app/                # Mobile app for notifications
│   └── ...                     # Flutter project files
│
├── templates/                  # Jinja2 HTML templates
│   ├── base.html               # Base layout with navbar
│   ├── admin_dashboard.html    # Main admin view
│   ├── schedule.html           # Member scheduling
│   ├── system_settings.html    # Configuration
│   └── ...
│
├── instance/                   # Database (gitignored)
│   └── interviews.db           # SQLite database
│
├── docs/                       # Documentation
│   └── MODULAR_ARCHITECTURE.md # Architecture details
├── CLAUDE.md                   # AI coding instructions
├── README.md                   # This file
└── DEPLOYMENT.md               # Deployment guide
```

---

## 🔧 Configuration

### System Settings (All UI-Based - No Environment Variables!)

**Important:** All configuration is managed through the web UI at **Admin → System Settings**.
Email, SMS, and scheduler settings are stored encrypted in the database. No `.env` file or environment variables are needed for credentials!

#### **📧 Email Settings**
- SMTP server and port
- TLS/SSL options
- Username and password (encrypted)
- From address and display name
- Test email functionality

#### **📱 SMS Settings (Full App Only)**
- **SMS Mode:**
  - **1-Way**: Simple notifications, replies to personal phone
  - **2-Way**: Advanced automation with webhook support (Phase 2)
- **Provider Selection:** AWS SNS, Twilio, or SignalWire
- **Personal Contact:** Include admin name/phone for replies
- **Live Preview:** See exactly how messages will appear
- **Provider Setup Guide:** Built-in instructions and cost comparison
- **Test SMS:** Send test with detailed error reporting

> **Minimal App users:** Use the Flutter mobile app for SMS - no server-side SMS configuration needed!

#### **⏰ Scheduler Settings**
- Enable/disable automated reminders
- Set day of week and time for reminders
- Preview: "Reminders will be sent every Monday at 6:00 PM"

---

## 📱 SMS Provider Setup (Full App Only)

> **Using Minimal App?** Skip this section! Use the Flutter mobile app to send SMS notifications from your phone at zero cost.

The Full App includes a comprehensive in-app guide with cost comparisons and setup instructions. Here's a quick overview:

### Recommended: AWS SNS (1-Way Messaging)

**Cost:** ~$1.94/month for 400 messages

**Setup Steps:**
1. Create AWS account
2. Create IAM user with `AmazonSNSFullAccess` policy
3. Save Access Key ID and Secret Access Key
4. Complete A2P 10DLC registration as "Sole Proprietor" (~$2 one-time + $1/month)
5. Configure in System Settings → SMS → AWS SNS

**Why AWS?**
- Lowest cost for small volume
- Free tier: 100 SMS/month for first 12 months
- Simple API integration
- No phone number required for 1-way messaging

### Alternative: Twilio

**Cost:** ~$4.47/month for 400 messages

**Best For:** Maximum reliability and support

### Alternative: SignalWire

**Cost:** ~$2.10/month for 400 messages

**Best For:** Best features-to-cost ratio, advanced features

**📖 Full comparison and step-by-step instructions available in-app at System Settings → SMS tab**

---

## 🚢 Deployment

### Choosing Your Deployment

| Platform | Best For | Edition | Cost |
|----------|----------|---------|------|
| **PythonAnywhere** | Beginners, free tier | Minimal | Free |
| **Oracle Cloud** | Free tier with more resources | Minimal | Free |
| **Render** | Easy deployment, free tier | Minimal | Free |
| **DigitalOcean** | Full features, reliable | Full | ~$5/mo |
| **Self-hosted VPS** | Full control | Either | Varies |

### PythonAnywhere (Free - Minimal App)

Great for getting started with zero cost:

1. **Create account** at [PythonAnywhere](https://www.pythonanywhere.com)
2. **Open a Bash console** and clone the repo:
   ```bash
   git clone https://github.com/jtkelley/Ministering-Interviews.git
   cd Ministering-Interviews
   pip install --user -r requirements.txt
   ```
3. **Create a Web App:**
   - Go to Web tab → Add new web app
   - Choose Flask and Python 3.9+
   - Set source code path to `/home/yourusername/Ministering-Interviews`
   - Set WSGI file to point to `app.py`
4. **Reload** and access your app!

**Note:** Free tier doesn't support SSH/SFTP, but you can clone from GitHub directly.

### Docker Deployment (Any Platform)

**Minimal App (~400MB image):**
```bash
docker build -f Dockerfile -t ministering-min .
docker run -p 8181:8181 -v ./instance:/app/instance ministering-min
```

**Full App (~1.2GB image with Chrome):**
```bash
docker build -f Dockerfile.full -t ministering-full .
docker run -p 8181:8181 -v ./instance:/app/instance ministering-full
```

### DigitalOcean App Platform (Full App)

1. **Push to GitHub** (if not already)
2. **Create DigitalOcean App:**
   - Sign up at [DigitalOcean](https://www.digitalocean.com)
   - Create new App from GitHub repository
   - Set Dockerfile path: `Dockerfile.full`
3. **Configure Environment Variables:**
   - `DATABASE_URL` - PostgreSQL connection string (recommended)
4. **Deploy and configure** via web UI

### Other Options

- **Oracle Cloud Free Tier**: 1GB memory ARM instances - use Minimal App
- **Render**: Free tier available - use Minimal App
- **Heroku**: Supports both editions with appropriate buildpacks
- **VPS (Linux)**: Full control with DigitalOcean Droplet, Linode, etc.

See `DEPLOYMENT.md` for detailed deployment instructions.

---

## 🤖 Built with AI

This entire application was developed using **AI-assisted programming** with Claude Code (Anthropic's AI coding assistant). Here's how AI contributed:

### What AI Did:
- **Architecture Design**: Suggested Flask + SQLAlchemy structure with proper MVC pattern
- **Database Schema**: Designed normalized schema with appropriate relationships
- **Web Scraping**: Implemented sophisticated LCR scraping with JSON extraction and HTML fallback
- **Security**: Implemented AES encryption for credentials and secure token generation
- **UI/UX Design**: Created responsive Bootstrap 5 templates with modern interactions
- **Multi-Provider SMS**: Integrated three different SMS APIs with unified interface
- **Error Handling**: Comprehensive try-catch blocks with helpful error messages
- **Testing Guidance**: Suggested edge cases and debugging approaches
- **Documentation**: Wrote this README, CLAUDE.md, and inline comments
- **Deployment**: Provided deployment guides for multiple platforms

### What This Demonstrates:
- AI can build **production-ready applications** with complex features
- AI understands **best practices** (security, error handling, user experience)
- AI can integrate **multiple third-party APIs** effectively
- AI creates **maintainable code** with proper structure and documentation
- AI handles both **backend logic** and **frontend presentation**

### Human Contributions:
- Initial concept and requirements ("I need to schedule ministering interviews")
- Testing and feedback ("The button should stay enabled but show a badge")
- Configuration and deployment (AWS keys, email credentials, etc.)
- Domain knowledge (LDS Church structure, interview process)
- Final approval and decision-making

**🎓 Learning Point:** This project shows that AI can be a powerful coding partner, dramatically accelerating development while maintaining quality. The key is clear communication of requirements and iterative refinement.

---

## 🛡️ Security

### Implemented Security Measures:
- ✅ **Encrypted Credentials**: All API keys and passwords encrypted with Fernet (AES) in database
- ✅ **Secure Tokens**: 32-character random hex tokens for member scheduling links
- ✅ **Role-Based Access**: Admin-only routes protected with `@admin_required` decorator
- ✅ **Password Hashing**: User passwords hashed with Flask-User
- ✅ **HTTPS Recommended**: Use SSL/TLS in production
- ✅ **Database Encryption**: All sensitive credentials stored encrypted in SystemConfig table
- ✅ **SQL Injection Prevention**: SQLAlchemy ORM with parameterized queries
- ✅ **XSS Prevention**: Jinja2 auto-escaping enabled



## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

**Summary:** You're free to use, modify, and distribute this software for any purpose, including commercial use. Just include the original license and copyright notice.

---

## 🤝 Contributing

Contributions are welcome! Since this was built with AI, it's a great opportunity to learn AI-assisted development.

### How to Contribute:
1. Fork the repository
2. Create a feature branch: `git checkout -b feature/AmazingFeature`
3. Make your changes
4. Test thoroughly
5. Commit: `git commit -m 'Add some AmazingFeature'`
6. Push: `git push origin feature/AmazingFeature`
7. Open a Pull Request

### Ideas for Contributions:
- [ ] Add support for more SMS providers (Vonage, MessageBird)
- [ ] Implement Phase 2: 2-Way SMS with webhook support
- [ ] Add calendar export (ICS files for Outlook/Google Calendar)
- [ ] Multi-language support (Spanish, Portuguese, etc.)
- [x] Mobile app (Flutter) - ✅ Implemented!
- [ ] Advanced reporting and analytics
- [ ] Integration with other LCR features
- [ ] Dark mode theme toggle
- [ ] macOS/Linux support for Local Scraper

---

## 🐛 Troubleshooting

### Common Issues:

**1. ChromeDriver version mismatch (Full App - web scraping fails)**
- **Solution**: The Docker build auto-downloads matching ChromeDriver
- For local development, update version in `features/scraping/scraper.py`

**2. SMS test fails with credentials error (Full App)**
- **Solution**: Check System Settings → SMS for correct API keys
- Use the "Send Test SMS" detailed error messages for troubleshooting hints
- **Alternative**: Use Flutter app for SMS instead

**3. Email not sending**
- **Gmail Users**: Enable "Less secure app access" or use App Password
- **Outlook Users**: May need to verify device
- **Test**: Use "Send Test Email" button in settings

**4. Database locked errors**
- **Cause**: SQLite doesn't handle concurrent writes well
- **Solution**: Switch to PostgreSQL for production

**5. Import errors on Minimal App**
- **Cause**: Trying to access scraping features that aren't available
- **Solution**: Use `app.py` (not `app_full.py`) and import via CSV

**6. Local Scraper won't start**
- **Cause**: Chrome not installed or wrong version
- **Solution**: Install latest Chrome, run `pip install -r local_requirements.txt`

---

## 📚 Additional Documentation

- **CLAUDE.md** - Instructions for AI when working with this codebase
- **DEPLOYMENT.md** - Detailed deployment guides for various platforms
- **docs/MODULAR_ARCHITECTURE.md** - Details on the min/full app architecture
- **sms_guide.md** - Comprehensive SMS provider comparison and setup guide (Full App)

---

## 💬 Support

- **Issues**: Report bugs or request features via [GitHub Issues](https://github.com/jtkelley/Ministering-Interviews/issues)
- **Documentation**: Check the in-app help guides and tooltips

---

## 🙏 Acknowledgments

- **Anthropic Claude And xAI Grok** - AI assistant that built 99% of this application
- **The LDS Church** - For the ministering program and LCR system
- **Flask Community** - For excellent web framework and extensions
- **Bootstrap Companionship** - For responsive UI components
- **Open Source Community** - For all the amazing libraries used in this project

---

## 📊 Project Stats

- **Lines of Code**: ~2,500+ (Python) + ~2,000+ (HTML/JS)
- **Development Time**: ~20 hours with AI assistance (would be 100+ hours manually)
- **Files**: 20+ templates, 3 Python modules
- **Features**: 50+ user-facing features
- **AI Contribution**: ~99% of code written by Claude Code
- **Human Contribution**: ~1% (requirements, testing, feedback, deployment, modifying text. 1 simple line of code when Grok got stuck)

---

<div align="center">

**⭐ If you found this project helpful, please star it on GitHub! ⭐**

Built with ❤️ and 🤖 AI

</div>
