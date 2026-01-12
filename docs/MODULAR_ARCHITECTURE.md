# Modular Flask App Architecture

## Problem

Currently maintaining two separate apps (main + app-min) with 92% code duplication. Changes to core features require updating both.

## Solution: Feature Flags + Optional Blueprints

Single codebase with configuration flags that enable/disable features at runtime.

## Proposed Architecture

```
Ministering-Interviews/
├── app.py                    # Main entry point with feature flags
├── config.py                 # Add FEATURES dict
├── models.py                 # Conditional SMS fields
├── services.py               # All services, conditionally imported
├── shared.py                 # Unchanged
├── requirements.txt          # Full deps (optional deps marked)
├── requirements-min.txt      # Minimal deps only
│
├── routes/
│   ├── __init__.py           # Blueprint registration logic
│   ├── public.py             # Public routes (always loaded)
│   ├── admin_core.py         # Core admin routes (always loaded)
│   ├── admin_scraping.py     # Scraping routes (optional)
│   ├── admin_sms.py          # SMS routes (optional)
│   └── api.py                # API routes (always loaded)
│
├── features/
│   ├── __init__.py           # Feature detection
│   ├── scraping/
│   │   ├── __init__.py
│   │   ├── routes.py         # Scrape routes blueprint
│   │   ├── scraper.py        # app_scraper.py logic
│   │   └── templates/
│   │       ├── scrape.html
│   │       └── scrape_progress.html
│   └── sms/
│       ├── __init__.py
│       ├── routes.py         # SMS test route
│       ├── services.py       # SMS send functions
│       └── models.py         # IncomingSMS model
│
├── templates/
│   ├── base.html             # Uses {% if features.scraping %}
│   ├── admin_calendar.html   # Conditional buttons
│   └── ...                   # Other shared templates
│
└── utils/                    # Unchanged
```

## Key Changes

### 1. config.py - Add Feature Flags

```python
# Feature flags - set via environment or here
FEATURES = {
    'scraping': os.environ.get('FEATURE_SCRAPING', 'true').lower() == 'true',
    'sms': os.environ.get('FEATURE_SMS', 'true').lower() == 'true',
}
```

### 2. app.py - Conditional Blueprint Registration

```python
from config import FEATURES

# Always register core blueprints
app.register_blueprint(public_bp)
app.register_blueprint(admin_core_bp)
app.register_blueprint(api_bp)

# Conditionally register feature blueprints
if FEATURES.get('scraping'):
    from features.scraping.routes import scraping_bp
    app.register_blueprint(scraping_bp)

if FEATURES.get('sms'):
    from features.sms.routes import sms_bp
    app.register_blueprint(sms_bp)

# Make features available to templates
@app.context_processor
def inject_features():
    return {'features': FEATURES}
```

### 3. Templates - Conditional Menus

```html
<!-- base.html -->
{% if features.scraping %}
<li class="nav-item">
    <a class="nav-link" href="{{ url_for('scraping.scrape_data') }}">Scrape from LCR</a>
</li>
{% endif %}

{% if features.sms %}
<li class="nav-item">
    <a class="nav-link" href="{{ url_for('sms.test_sms') }}">Test SMS</a>
</li>
{% endif %}
```

### 4. services.py - Conditional Imports

```python
def send_notifications(member, link):
    """Send email, and SMS if enabled"""
    send_email(member, link)  # Always

    if current_app.config.get('FEATURES', {}).get('sms'):
        from features.sms.services import send_sms
        send_sms(member, link)
```

### 5. Two Entry Points (Optional)

```python
# run_full.py
os.environ['FEATURE_SCRAPING'] = 'true'
os.environ['FEATURE_SMS'] = 'true'
from app import app
app.run()

# run_min.py
os.environ['FEATURE_SCRAPING'] = 'false'
os.environ['FEATURE_SMS'] = 'false'
from app import app
app.run()
```

## Files to Modify

| File | Change |
|------|--------|
| `config.py` | Add FEATURES dict |
| `app.py` | Conditional blueprint registration, context processor |
| `routes_admin.py` | Split into `admin_core.py` + move scrape routes to feature |
| `services.py` | Remove SMS functions, add conditional import |
| `models.py` | Keep SMS fields but make them optional |
| `templates/base.html` | Add `{% if features.X %}` conditionals |
| `templates/admin_calendar.html` | Conditional scrape button |
| `templates/system_settings.html` | Conditional SMS tab |

## New Files to Create

| File | Purpose |
|------|---------|
| `features/__init__.py` | Feature detection helpers |
| `features/scraping/__init__.py` | Scraping feature module |
| `features/scraping/routes.py` | Scraping blueprint |
| `features/sms/__init__.py` | SMS feature module |
| `features/sms/routes.py` | SMS test route |
| `features/sms/services.py` | SMS send functions |
| `requirements-min.txt` | Deps without selenium/twilio |

## Deployment

```bash
# Full version (default)
python app.py

# Minimal version
FEATURE_SCRAPING=false FEATURE_SMS=false python app.py

# Or use environment file
# .env.min
FEATURE_SCRAPING=false
FEATURE_SMS=false
```

## Benefits

1. **Single codebase** - No duplicate files to maintain
2. **Feature toggles** - Enable/disable via environment
3. **Clean separation** - Features isolated in their own modules
4. **Smaller deployments** - Use requirements-min.txt for low-memory VMs
5. **Easy testing** - Test each feature independently

## Migration Steps

1. Create `features/` directory structure
2. Move scraping code to `features/scraping/`
3. Move SMS code to `features/sms/`
4. Split `routes_admin.py` into core + features
5. Add feature flags to config
6. Update app.py with conditional registration
7. Update templates with conditionals
8. Create requirements-min.txt
9. Delete app-min/ folder
10. Test both configurations

## Current Code Duplication Analysis

| Category | Main App | Minimal App | Duplicated |
|----------|----------|-------------|------------|
| Python source | ~4,500 lines | ~3,100 lines | ~2,800 lines (62%) |
| Templates | ~2,000 lines | ~1,800 lines | ~1,700 lines (85%) |
| Utilities | ~200 lines | ~200 lines | ~200 lines (100%) |
| **TOTAL** | ~6,700 lines | ~5,100 lines | ~4,700 lines (92%) |

## Verification

```bash
# Test full version
python app.py
# Should see: Scrape menu, SMS settings, all features

# Test minimal version
FEATURE_SCRAPING=false FEATURE_SMS=false python app.py
# Should see: No scrape menu, no SMS settings, email only
```
