# Refactoring Plan for Ministering Interviews App

## Current Status

✅ **Completed:**
- Created `models.py` with all database models
- Created `utils/` directory with:
  - `encryption.py` - EncryptionHelper class
  - `decorators.py` - @admin_required decorator
- Created `config.py` with configuration classes

⏳ **In Progress:**
- Updating `app.py` to use new modules

📋 **TODO:**
- Extract services (email, SMS, scraper)
- Split routes into Blueprints
- Update all imports
- Test thoroughly

---

## Phase 1: Models (✅ COMPLETE)

**File:** `models.py`

**Models Extracted:**
- User
- UserInvitation
- SystemConfig
- IncomingSMS
- District
- Companionship
- Member
- InterviewSlot
- Booking
- NotificationLog

---

## Phase 2: Utils (✅ COMPLETE)

**Directory:** `utils/`

**Files Created:**
- `__init__.py` - Package initialization
- `encryption.py` - EncryptionHelper for sensitive data
- `decorators.py` - Route protection decorators

---

## Phase 3: Config (✅ COMPLETE)

**File:** `config.py`

**Classes:**
- `Config` - Base configuration
- `DevelopmentConfig` - Development settings
- `ProductionConfig` - Production settings

---

## Phase 4: Services (TODO)

**Directory:** `services/`

### Files to Create:

#### `services/__init__.py`
```python
from .email_service import EmailService
from .sms_service import SMSService
from .scraper_service import ScraperService

__all__ = ['EmailService', 'SMSService', 'ScraperService']
```

#### `services/email_service.py`
Extract from app.py:
- `send_email_notification()` function
- `apply_email_config()` function
- Email sending logic

#### `services/sms_service.py`
Extract from app.py:
- `send_sms_notification()` function
- `apply_sms_config()` function
- SMS provider logic (Twilio, AWS SNS, SignalWire)

#### `services/scraper_service.py`
Move from `app_scraper.py`:
- Web scraping logic for LCR
- ChromeDriver setup
- Progress tracking

---

## Phase 5: Routes (TODO)

**Directory:** `routes/`

Split routes using Flask Blueprints:

### `routes/__init__.py`
Register all blueprints

### `routes/admin.py`
Routes:
- `/admin` - Admin calendar
- `/admin/send_notifications/<district_id>`
- `/admin/send_individual_notification/<member_id>`

### `routes/districts.py`
Routes:
- `/admin/districts` - Manage districts
- `/admin/district/<id>` - District detail
- `/admin/add_district` - Add district
- `/admin/update_district/<id>` - Update district
- `/admin/delete_district/<id>` - Delete district

### `routes/companionships.py`
Routes:
- `/admin/add_companionship/<district_id>`
- `/admin/delete_companionship/<id>`
- `/admin/reassign_member/<member_id>`

### `routes/slots.py`
Routes:
- `/admin/slots/<district_id>` - Manage slots
- `/admin/add_slot/<district_id>` - Add slot
- `/admin/delete_slot/<id>` - Delete slot
- `/admin/generate_slots/<district_id>` - Generate recurring slots

### `routes/bookings.py`
Routes:
- `/admin/add_booking/<slot_id>` - Admin add booking
- `/admin/remove_booking/<booking_id>` - Remove booking
- `/book/<slot_id>/<token>` - Member book slot
- `/unbook/<token>` - Member cancel booking

### `routes/schedule.py`
Routes:
- `/schedule/<token>` - Member scheduling page

### `routes/notifications.py`
Routes:
- `/admin/notification_report` - Notification report

### `routes/scraper.py`
Routes:
- `/admin/scrape` - Scraper interface
- `/admin/scrape_progress/<job_id>` - Progress tracking
- `/admin/confirm_import` - Import confirmation

### `routes/settings.py`
Routes:
- `/admin/settings` - System settings
- `/admin/save_email_config` - Save email config
- `/admin/save_sms_config` - Save SMS config
- `/admin/test_email` - Test email
- `/admin/test_sms` - Test SMS

### `routes/auth.py`
Routes:
- `/login_redirect` - Custom login handler
- `/admin/users` - User management
- `/admin/invite_user` - Invite user

---

## Phase 6: Update app.py (IN PROGRESS)

### Steps:

1. **Update Imports**
   ```python
   from config import config
   from models import db, User, District, Companionship, Member, InterviewSlot, Booking, NotificationLog, SystemConfig, UserInvitation, IncomingSMS
   from utils import EncryptionHelper, admin_required
   ```

2. **Initialize App with Config**
   ```python
   app = Flask(__name__)
   app.config.from_object(config['development'])
   ```

3. **Initialize Extensions**
   ```python
   db.init_app(app)
   migrate = Migrate(app, db)
   mail = Mail(app)
   ```

4. **Register Blueprints**
   ```python
   from routes import admin_bp, districts_bp, slots_bp, bookings_bp, schedule_bp, notifications_bp, scraper_bp, settings_bp, auth_bp

   app.register_blueprint(admin_bp)
   app.register_blueprint(districts_bp)
   # ... etc
   ```

5. **Remove Extracted Code**
   - Remove model definitions (now in models.py)
   - Remove EncryptionHelper (now in utils/)
   - Remove admin_required (now in utils/)
   - Remove route definitions (will be in routes/)
   - Remove service functions (will be in services/)

---

## Phase 7: Testing (TODO)

### Test Checklist:

- [ ] App starts without errors
- [ ] Database migrations work
- [ ] Login/logout works
- [ ] Admin dashboard loads
- [ ] Can create/edit districts
- [ ] Can create/edit companionships
- [ ] Can create/edit time slots
- [ ] Members can book slots
- [ ] Email notifications work
- [ ] SMS notifications work
- [ ] Scraper works
- [ ] Settings save/load correctly
- [ ] All existing functionality preserved

---

## Migration Strategy

### Option A: All at Once (Risky)
- Complete all phases
- Update app.py completely
- Test everything
- **Risk:** Hard to debug if something breaks

### Option B: Incremental (Recommended)
1. Keep app.py working
2. Create new modules alongside
3. Update app.py to import from new modules gradually
4. Test after each change
5. Remove old code only when new code is confirmed working

### Option C: Parallel Branch
1. Create a `refactor` branch
2. Do all work there
3. Test thoroughly
4. Merge when confident

---

## Rollback Plan

If refactoring causes issues:

1. **Git Revert:**
   ```bash
   git checkout main
   ```

2. **Keep Both Versions:**
   - `app.py` - Original (working)
   - `app_new.py` - Refactored (testing)
   - Switch between them as needed

---

## Benefits After Refactoring

✨ **Code Organization:**
- Clear separation of concerns
- Easier to find specific functionality

✨ **Maintainability:**
- Smaller files are easier to understand
- Changes isolated to relevant modules

✨ **Testing:**
- Can test services independently
- Mock external dependencies easily

✨ **Team Collaboration:**
- Multiple developers can work on different files
- Less merge conflicts

✨ **Scalability:**
- Easy to add new routes/services
- Clear patterns to follow

---

## Next Steps

**Choose One:**

1. **Continue Incremental Refactoring**
   - Complete Phase 4 (Services)
   - Test services work
   - Continue to Phase 5 (Routes)

2. **Pause and Test Current Progress**
   - Update app.py to use models, utils, config
   - Test that everything still works
   - Continue later

3. **Start Fresh on a Branch**
   - Create refactor branch
   - Do all work there
   - Merge when done

**Recommendation:** Option 2 - Test what we have now before continuing.

