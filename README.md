# Interview Scheduler

A simple web-based interview scheduling system built with Flask and SQLite.

## Features

- Admin panel to create districts and manage teams
- Set interview slots with dates, times, and capacities
- Send notification links to team members via email and SMS
- Team members can select available interview slots
- Multiple team members can book the same slot (group interviews)

## Setup

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Set up environment variables for email:
   ```
   export MAIL_USERNAME=your_email@gmail.com
   export MAIL_PASSWORD=your_app_password
   ```

3. Run the app:
   ```
   python app.py
   ```

## Deployment

### DigitalOcean App Platform (Recommended)
1. Push code to GitHub
2. Create app on DigitalOcean App Platform
3. Set environment variables for email and Twilio (if using SMS)
4. Deploy

### FTP Deployment
For shared hosting with Python support:
1. Upload all files
2. Ensure Python CGI is enabled
3. Modify app.py to work with CGI if needed

## SMS Integration

To enable SMS notifications, integrate Twilio:
1. Sign up for Twilio account
2. Install twilio library: `pip install twilio`
3. Add Twilio credentials to environment variables
4. Uncomment and configure the SMS sending code in app.py

## Usage

1. Access admin panel at `/admin`
2. Create districts and add teams with members
3. Set up interview slots
4. Send notifications to generate scheduling links
5. Team members use links to book slots