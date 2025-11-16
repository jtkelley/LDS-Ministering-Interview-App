# Refactoring Plan - Option 2A

## Final Structure

```
ministering-interviews/
├── app.py                 # Flask app initialization, config loading (~200 lines)
├── models.py             # All database models (✅ DONE - ~300 lines)
├── config.py             # Configuration classes (✅ DONE - ~70 lines)
├── utils.py              # Encryption, decorators (~100 lines)
├── services.py           # Email, SMS, notification helpers (~300 lines)
├── routes_admin.py       # Admin routes: calendar, districts, slots (~800 lines)
├── routes_member.py      # Member routes: scheduling, booking (~400 lines)
├── routes_settings.py    # Settings, users, scraper, system (~700 lines)
└── app_scraper.py        # Web scraping (already exists)
```

---

## Phase 1: Create utils.py ✅ (Partially Done)

Consolidate `utils/` directory into single file:

### utils.py Contents:
- EncryptionHelper class
- admin_required decorator
- Any other utility functions

---

## Phase 2: Create services.py

### Extract from app.py (lines ~136-395):

**Functions to Move:**
- `apply_email_config()` - Load email config from database
- `apply_sms_config()` - Load SMS config from database
- `format_sms_message()` - Format SMS with link and contact info
- `send_sms()` - Send SMS via configured provider
- `send_email_notification()` - Send email to member
- `send_sms_notification()` - Send SMS to member
- `reschedule_reminder_job()` - Update scheduler with new settings
- `send_booking_reminders()` - Automated reminder job

**Global Variables to Move:**
- `sms_config` - SMS client storage

**Imports Needed:**
- Flask app context
- Models
- Mail, Message
- SMS providers (Twilio, AWS, SignalWire)

---

## Phase 3: Create routes_admin.py

### Routes to Include (~800 lines):

#### Admin Calendar & Dashboard
- `/admin` - Main admin calendar view
- `/admin/delete_old_slots` - Delete old slots

#### District Management
- `/admin/districts` - List all districts
- `/admin/district/<id>` - District detail view
- `/admin/add_district` - Create new district
- `/admin/update_district/<id>` - Update district
- `/admin/delete_district/<id>` - Delete district

#### Companionship Management
- `/admin/add_companionship/<district_id>` - Add companionship
- `/admin/delete_companionship/<id>` - Delete companionship
- `/admin/reassign_member/<member_id>` - Reassign member to different companionship
- `/admin/toggle_sms/<int:member_id>` - Toggle SMS for member

#### Slot Management
- `/admin/slots/<district_id>` - Manage time slots
- `/admin/add_slot/<district_id>` - Add single slot
- `/admin/delete_slot/<id>` - Delete slot
- `/admin/generate_slots/<district_id>` - Generate recurring slots

#### Booking Management (Admin Side)
- `/admin/add_booking/<slot_id>` - Admin add member to slot
- `/admin/remove_booking/<booking_id>` - Remove member from slot

#### Notifications
- `/admin/send_notifications/<district_id>` - Send notifications to district
- `/admin/send_individual_notification/<member_id>` - Send to single member
- `/admin/notification_report` - Notification report view

**Blueprint Name:** `admin_bp` with url_prefix='/admin'

---

## Phase 4: Create routes_member.py

### Routes to Include (~400 lines):

#### Member Scheduling Interface
- `/schedule/<token>` - Member scheduling page (view available slots)

#### Member Booking Actions
- `/book/<slot_id>/<token>` - Member books a slot
- `/unbook/<token>` - Member cancels booking

**Blueprint Name:** `member_bp` (no prefix, these are public routes)

---

## Phase 5: Create routes_settings.py

### Routes to Include (~700 lines):

#### Authentication & Setup
- `/login_redirect` - Custom login redirect handler
- `/setup_admin` - Initial admin setup (first run)
- `/` - Index/landing page
- `/dashboard` - Interviewer dashboard

#### User Management
- `/admin/users` - Manage users
- `/admin/invite_user` - Create user invitation
- `/admin/accept_invite/<token>` - Accept invitation
- `/admin/delete_user/<int:user_id>` - Delete user
- `/admin/revoke_invite/<int:invite_id>` - Revoke invitation

#### System Settings
- `/admin/settings` - System settings page
- `/admin/settings/save` - Save system settings
- `/admin/settings/test-email` - Test email configuration
- `/admin/settings/test-sms` - Test SMS configuration

#### Import & Scraper
- `/admin/scrape` - Web scraper interface
- `/admin/scrape_progress/<job_id>` - Scraper progress tracking
- `/admin/import_csv` - CSV import interface
- `/admin/upload_csv` - Handle CSV upload
- `/admin/confirm_import` - Confirm import after preview

#### SMS Webhooks (2-way messaging)
- `/sms/webhook/twilio` - Twilio incoming webhook
- `/sms/webhook/signalwire` - SignalWire incoming webhook
- `/admin/incoming_sms` - View incoming messages
- `/admin/mark_sms_read/<int:sms_id>` - Mark SMS as read
- `/admin/respond_sms/<int:sms_id>` - Respond to SMS

**Blueprint Name:** `settings_bp` with url_prefix='' (mixed prefixes)

---

## Phase 6: Update app.py

### New app.py Structure (~200 lines):

```python
# Imports
from flask import Flask
from flask_migrate import Migrate
from flask_mail import Mail
from flask_user import UserManager
from dotenv import load_dotenv
import os

# Load environment
load_dotenv()

# Import from our modules
from config import config
from models import db, User
from utils import admin_required
import services

# Create Flask app
app = Flask(__name__)
app.config.from_object(config['development'])

# Ensure instance directory exists
os.makedirs('instance', exist_ok=True)

# Initialize extensions
db.init_app(app)
migrate = Migrate(app, db)
mail = Mail(app)

# Initialize Flask-User
user_manager = UserManager(app, db, User)

# Initialize scheduler
from apscheduler.schedulers.background import BackgroundScheduler
scheduler = BackgroundScheduler()
scheduler.start()

# Register Blueprints
from routes_admin import admin_bp
from routes_member import member_bp
from routes_settings import settings_bp

app.register_blueprint(admin_bp)
app.register_blueprint(member_bp)
app.register_blueprint(settings_bp)

# Context processors and other app-level config
@app.context_processor
def inject_now():
    return {'now': datetime.now()}

# Initialize database and load config
with app.app_context():
    db.create_all()
    services.apply_email_config()
    services.apply_sms_config()

    # Schedule reminders
    from models import SystemConfig
    config = SystemConfig.query.first()
    if config:
        services.reschedule_reminder_job(config)

# Run app
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8181)
```

---

## Phase 7: Blueprint Structure

Each route file will follow this pattern:

```python
from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db, District, Companionship, Member, InterviewSlot, Booking
from utils import admin_required
import services

# Create blueprint
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# Routes
@admin_bp.route('/')
@admin_required
def admin_calendar():
    # ... route logic ...
    pass

@admin_bp.route('/districts')
@admin_required
def manage_districts():
    # ... route logic ...
    pass

# ... more routes ...
```

---

## Migration Steps

1. ✅ Create `models.py` (DONE)
2. ✅ Create `config.py` (DONE)
3. Create `utils.py` (consolidate utils/ directory)
4. Create `services.py` (extract service functions)
5. Create `routes_admin.py` (extract admin routes)
6. Create `routes_member.py` (extract member routes)
7. Create `routes_settings.py` (extract settings routes)
8. Update `app.py` (slim down to ~200 lines)
9. Test thoroughly
10. Delete old `utils/` directory
11. Update `REFACTORING_PLAN.md` with completion notes

---

## Testing Checklist

After each phase:
- [ ] App starts without import errors
- [ ] Can access admin calendar
- [ ] Can create/edit districts
- [ ] Can create/edit slots
- [ ] Members can book slots
- [ ] Email notifications work
- [ ] SMS notifications work
- [ ] Settings save properly
- [ ] Scraper works
- [ ] All 48 routes accessible

---

## Rollback Plan

- Keep git commits small (one phase at a time)
- Can revert to working state after each phase
- Keep backup of original app.py as `app_backup.py`

---

## Estimated Time

- Phase 1 (utils.py): 10 minutes
- Phase 2 (services.py): 20 minutes
- Phase 3 (routes_admin.py): 30 minutes
- Phase 4 (routes_member.py): 15 minutes
- Phase 5 (routes_settings.py): 30 minutes
- Phase 6 (update app.py): 20 minutes
- Phase 7 (testing): 30 minutes

**Total: ~2.5 hours**

---

## Ready to Start?

Next steps:
1. Create `utils.py`
2. Create `services.py`
3. Create route files
4. Update `app.py`
5. Test!

