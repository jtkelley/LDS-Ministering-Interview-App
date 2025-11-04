# 📅 Ministering Interview Scheduler

> A comprehensive web application for managing ministering interviews in LDS church wards. Built with Flask, featuring automated scheduling, notifications, and intelligent data scraping from LCR.

[![Built with AI](https://img.shields.io/badge/Built%20with-AI%20(Claude)-5865F2?style=flat-square)](https://claude.ai) 
[![Python](https://img.shields.io/badge/Python-3.9+-blue?style=flat-square)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0+-green?style=flat-square)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

---

## 🎯 Overview

This application streamlines the process of scheduling and conducting quarterly ministering interviews in LDS wards. It automatically scrapes companionship data from the LDS Church's LCR website, manages interview time slots, sends notifications via email and SMS, and allows members to self-schedule their interviews online.

**🤖 Note:** This application was created almost 100% using AI assistance (Initailly Grok Code fast 1 and then Claude Code by Anthropic). From the initial concept to the final implementation, AI guided the architecture, wrote the code, designed the database schema, and implemented features. This showcases the power of AI-assisted development in creating full-featured web applications.

---

## ✨ Key Features

### 👥 **Automated Data Import**
- **LCR Web Scraping**: Automatically extract companionship data from the Church's LCR website using Selenium
- **CSV Import**: Alternative manual import option for flexibility
- **Smart Matching**: Automatically matches and updates existing members by email to prevent duplicates
- **Preview Before Import**: Review all data before committing changes

### 📆 **Intelligent Scheduling**
- **Recurring Slot Generation**: Create multiple interview slots across weeks with a single form
- **Team-Based Restrictions**: Once a slot is booked, only team members can book the same slot
- **Capacity Management**: Set maximum members per slot (default: 10)
- **Quarter-Based Organization**: Automatically organizes slots by calendar quarters
- **Conflict Prevention**: Prevents overlapping or duplicate bookings

### 📧 **Multi-Channel Notifications**
- **Email Notifications**: Configurable SMTP support (Gmail, Outlook, etc.)
- **SMS Integration**: Support for three providers:
  - **AWS SNS** (Recommended - lowest cost ~$1.94/month)
  - **Twilio** (Most reliable - ~$4.47/month)
  - **SignalWire** (Best features/cost - ~$2.10/month)
- **1-Way & 2-Way Messaging**: Choose between simple one-way notifications or advanced two-way communication
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
- **Companionship View**: See all teams and members at a glance
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
   git clone https://github.com/yourusername/Ministering-Interviews.git
   cd Ministering-Interviews
   ```

2. **Create a virtual environment (recommended):**
   ```bash
   # Windows
   python -m venv venv
   venv\Scripts\activate

   # Linux/Mac
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables:**
   Create a `.env` file in the root directory:
   ```env
   # Email Configuration (Required)
   MAIL_USERNAME=your-email@gmail.com
   MAIL_PASSWORD=your-app-password

   # Optional: SMS Configuration (choose one provider)
   # AWS SNS
   AWS_ACCESS_KEY_ID=your-access-key
   AWS_SECRET_ACCESS_KEY=your-secret-key
   AWS_REGION=us-east-1

   # Or Twilio
   TWILIO_ACCOUNT_SID=your-account-sid
   TWILIO_AUTH_TOKEN=your-auth-token
   TWILIO_PHONE_NUMBER=+1234567890

   # Or SignalWire
   SIGNALWIRE_PROJECT_ID=your-project-id
   SIGNALWIRE_AUTH_TOKEN=your-auth-token
   SIGNALWIRE_SPACE_URL=yourspace.signalwire.com
   SIGNALWIRE_PHONE_NUMBER=+1234567890
   ```

5. **Run the application:**
   ```bash
   python app.py
   ```

6. **Access the application:**
   Open your browser to `http://localhost:8181`

---

## 📖 Usage Guide

### First-Time Setup

1. **Configure Email Settings:**
   - Navigate to **Admin → System Settings → Email**
   - Enter your SMTP server details (e.g., Gmail: `smtp.gmail.com:587`)
   - Add your email and app password
   - Click "Send Test Email" to verify

2. **Configure SMS Settings (Optional but Recommended):**
   - Navigate to **Admin → System Settings → SMS**
   - Click "📖 SMS Provider Setup Guide & Cost Comparison" for detailed instructions
   - Choose your provider (AWS SNS recommended for lowest cost)
   - Select **1-Way Messaging** for simplest setup
   - Enter your personal contact info for member replies
   - Test with "Send Test SMS"

3. **Import Companionship Data:**
   - Navigate to **Admin → Scrape from LCR** (recommended)
     - Enter your LDS Account credentials
     - Select your ward
     - Review the preview
     - Confirm import
   - Or use **Admin → Import from CSV** for manual upload

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

## 🏗️ Architecture

### Technology Stack
- **Backend**: Flask 3.0 (Python web framework)
- **Database**: SQLite 
- **ORM**: SQLAlchemy (database abstraction)
- **Authentication**: Flask-User (user management and roles)
- **Web Scraping**: Selenium (Chrome/ChromeDriver)
- **Email**: Flask-Mail (SMTP integration)
- **SMS**: boto3 (AWS), twilio, signalwire (SMS providers)
- **Security**: cryptography (Fernet encryption)
- **Scheduling**: APScheduler (automated reminders)
- **Frontend**: Bootstrap 5, JavaScript, Jinja2 templates

### Database Schema

**Core Models:**
- `User` - Admin users with authentication
- `District` - Organizational units with interviewers
- `Team` - Companionships within districts
- `Member` - Individual members with unique tokens
- `InterviewSlot` - Available time slots with capacity
- `Booking` - Junction table linking members to slots
- `SystemConfig` - Application settings (encrypted)
- `IncomingSMS` - SMS message tracking (Phase 2)

**Key Relationships:**
- District → Teams (one-to-many)
- Team → Members (one-to-many)
- Member → Bookings (one-to-many)
- InterviewSlot → Bookings (one-to-many with capacity limit)

### Project Structure
```
Ministering-Interviews/
├── app.py                      # Main Flask application
├── app_scraper.py              # Web scraping module
├── local_scraper.py            # Local testing scraper
├── requirements.txt            # Python dependencies
├── CLAUDE.md                   # AI coding instructions
├── README.md                   # This file
├── DEPLOYMENT.md               # Deployment guide
├── sms_guide.md                # SMS provider comparison
├── templates/                  # Jinja2 HTML templates
│   ├── base.html              # Base layout with navbar
│   ├── admin_dashboard.html   # Main admin view
│   ├── district_detail.html   # District management
│   ├── manage_slots.html      # Slot generation
│   ├── schedule.html          # Member scheduling
│   ├── system_settings.html   # Configuration
│   └── ...
├── static/                     # CSS, JS, images (if any)
├── instance/                   # Database and instance files
│   └── interviews.db          # SQLite database (gitignored)
└── csv/                        # CSV import files (gitignored)
```

---

## 🔧 Configuration

### System Settings

All configuration is managed through the web UI at **Admin → System Settings**:

#### **📧 Email Settings**
- SMTP server and port
- TLS/SSL options
- Username and password (encrypted)
- From address and display name
- Test email functionality

#### **📱 SMS Settings**
- **SMS Mode:**
  - **1-Way**: Simple notifications, replies to personal phone
  - **2-Way**: Advanced automation with webhook support (Phase 2)
- **Provider Selection:** AWS SNS, Twilio, or SignalWire
- **Personal Contact:** Include admin name/phone for replies
- **Live Preview:** See exactly how messages will appear
- **Provider Setup Guide:** Built-in instructions and cost comparison
- **Test SMS:** Send test with detailed error reporting

#### **⏰ Scheduler Settings**
- Enable/disable automated reminders
- Set day of week and time for reminders
- Preview: "Reminders will be sent every Monday at 6:00 PM"

---

## 📱 SMS Provider Setup

The application includes a comprehensive in-app guide with cost comparisons and setup instructions. Here's a quick overview:

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

### DigitalOcean App Platform (Recommended)

1. **Push to GitHub:**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin https://github.com/yourusername/Ministering-Interviews.git
   git push -u origin main
   ```

2. **Create DigitalOcean App:**
   - Sign up at [DigitalOcean](https://www.digitalocean.com)
   - Create new App from GitHub repository
   - Choose "Web Service" type
   - Set build command: `pip install -r requirements.txt`
   - Set run command: `python app.py`

3. **Configure Environment Variables:**
   - Add all variables from `.env` file
   - Set `DATABASE_URL` for PostgreSQL (optional)

4. **Deploy:**
   - Click "Deploy" and wait for build to complete
   - Access your app at the provided URL

### Other Deployment Options

- **Heroku**: Similar to DigitalOcean, supports PostgreSQL
- **PythonAnywhere**: Good for small projects, SQLite works
- **AWS Elastic Beanstalk**: Enterprise-grade, more complex
- **VPS (Linux)**: DigitalOcean Droplet, Linode, etc.

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
- ✅ **Encrypted Credentials**: All API keys and passwords encrypted with Fernet (AES)
- ✅ **Secure Tokens**: 32-character random hex tokens for member scheduling links
- ✅ **Role-Based Access**: Admin-only routes protected with `@admin_required` decorator
- ✅ **Password Hashing**: User passwords hashed with Flask-User
- ✅ **HTTPS Recommended**: Use SSL/TLS in production
- ✅ **Environment Variables**: Sensitive data in `.env` file (not committed to Git)
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
- [ ] Mobile app (React Native or Flutter)
- [ ] Advanced reporting and analytics
- [ ] Integration with other LCR features
- [ ] Dark mode theme toggle

---

## 🐛 Troubleshooting

### Common Issues:

**1. ChromeDriver version mismatch (web scraping fails)**
- **Solution**: Update Chrome and ChromeDriver version numbers in `app_scraper.py:54-55`

**2. SMS test fails with credentials error**
- **Solution**: Check System Settings → SMS for correct API keys
- Use the "Send Test SMS" detailed error messages for troubleshooting hints

**3. Flash messages appearing on wrong pages**
- **Fixed**: Removed duplicate `get_flashed_messages()` calls from templates

**4. Email not sending**
- **Gmail Users**: Enable "Less secure app access" or use App Password
- **Outlook Users**: May need to verify device
- **Test**: Use "Send Test Email" button in settings

**5. Database locked errors**
- **Cause**: SQLite doesn't handle concurrent writes well
- **Solution**: Switch to PostgreSQL for production

**6. Tabs reset after saving settings**
- **Fixed**: Implemented sticky tabs with URL hash fragments

---

## 📚 Additional Documentation

- **CLAUDE.md** - Instructions for AI when working with this codebase
- **DEPLOYMENT.md** - Detailed deployment guides for various platforms
- **sms_guide.md** - Comprehensive SMS provider comparison and setup guide

---

## 💬 Support

- **Issues**: Report bugs or request features via [GitHub Issues](https://github.com/yourusername/Ministering-Interviews/issues)
- **Email**: contact@example.com
- **Documentation**: Check the in-app help guides and tooltips

---

## 🙏 Acknowledgments

- **Anthropic Claude And xAI Grok** - AI assistant that built 99% of this application
- **The LDS Church** - For the ministering program and LCR system
- **Flask Community** - For excellent web framework and extensions
- **Bootstrap Team** - For responsive UI components
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
