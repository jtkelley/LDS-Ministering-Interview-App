# Modular Flask App Architecture

## Current State

The codebase has two separate applications:
- **Main app** (root): Full features including scraping (Selenium/ChromeDriver) and SMS (Twilio/AWS/SignalWire)
- **app-min**: Stripped-down version without scraping or SMS dependencies

### What's Changed Since This Doc Was Originally Written

1. **MessageTemplates feature added** - New model and routes shared between both apps
2. **API routes added** - `routes_api.py` for Flutter mobile app integration
3. **HTML email templates** - More sophisticated email rendering with HTML/plain text
4. **Actual duplication is ~50%**, not 92% as originally estimated:
   - Main app: ~3,675 lines Python
   - app-min: ~1,836 lines Python
   - Templates are nearly identical with minor conditionals

### Key Differences Between Apps

| Feature | Main App | app-min |
|---------|----------|---------|
| Scraping (Selenium) | Yes | No |
| SMS (Twilio/AWS/SignalWire) | Yes | No |
| ChromeDriver | Yes | No |
| Dependencies | ~45 packages | ~25 packages |
| Docker image size | ~1.2GB | ~400MB |

## Approaches Evaluated

### Option 1: Feature Flags (Original Plan)

**How it works:** Single codebase with `FEATURES = {'scraping': True, 'sms': True}` flags controlling blueprint registration.

**Pros:**
- Simple concept
- Single codebase
- Runtime toggleable

**Cons:**
- Heavy dependencies still installed (Selenium, ChromeDriver) even when disabled
- Docker image stays large
- Conditional imports scattered throughout code
- Oracle Cloud's free tier has 1GB memory - unused Selenium still impacts footprint

### Option 2: Factory Pattern with create_app()

**How it works:** `create_app(config_name='full')` or `create_app(config_name='minimal')` builds app with different blueprints.

**Pros:**
- Clean separation
- Standard Flask pattern
- Testable configurations

**Cons:**
- Still has dependency problem - all packages must be installed
- Doesn't solve the deployment size issue

### Option 3: Shared Modules + Separate Entry Points (Recommended)

**How it works:** Extract shared code to a `core/` package. Main app and minimal app import from core but have their own entry points and requirements files.

**Pros:**
- **Solves dependency problem** - minimal deployment doesn't need Selenium installed
- **Small Docker images** - minimal version stays ~400MB
- **True code sharing** - one source of truth for core functionality
- **Easy maintenance** - change once in core, applies to both

**Cons:**
- Restructuring effort required
- Two entry points to maintain

### Option 4: Keep Separate Apps (Current State)

**Pros:**
- Works today
- Clear separation

**Cons:**
- **Every feature change requires updating both apps** (like MessageTemplates)
- Growing drift between implementations
- 50% duplicated code

## Implemented Architecture: Option 3

**Status: IMPLEMENTED** - This architecture has been built and tested.

```
Ministering-Interviews/
├── core/                       # Shared code (models, services, config)
│   ├── __init__.py
│   ├── config.py               # App configuration
│   ├── models.py               # All database models (shared)
│   ├── services.py             # Email-only services
│   ├── shared.py               # Shared resources (mail, progress_store)
│   ├── utils/                  # Utility functions
│   │   ├── __init__.py
│   │   ├── decorators.py       # @admin_required decorator
│   │   ├── encryption.py       # EncryptionHelper
│   │   └── helpers.py          # group_results_by_district
│   └── routes/                 # Core routes
│       ├── __init__.py
│       ├── public.py           # Public routes (shared)
│       ├── admin.py            # Admin routes (shared, no scraping)
│       └── api.py              # API routes (shared)
│
├── features/
│   ├── __init__.py
│   ├── scraping/               # Scraping-specific code
│   │   ├── __init__.py
│   │   ├── scraper.py          # Main scraping logic
│   │   └── routes.py           # Scraping routes blueprint
│   │
│   └── sms/                    # SMS-specific code
│       ├── __init__.py
│       └── services.py         # SMS send functions
│
├── templates/                  # All templates (stay at root for simplicity)
│   ├── base.html
│   ├── scrape.html             # Only used by full app
│   ├── scrape_progress.html    # Only used by full app
│   ├── system_settings.html    # Different tabs shown based on features
│   └── ...
│
├── app_full.py                 # Full app entry (imports core + scraping + sms)
├── app_minimal.py              # Minimal app entry (imports core only)
├── local-scraper/              # Self-contained local debugging tool
│   ├── local_scraper.py        # Imports from features.scraping.scraper
│   ├── local_requirements.txt
│   ├── run_local_scraper.bat
│   ├── chromedriver-win64/
│   └── chrome_user_data/
├── requirements.txt            # Full dependencies
└── requirements-min.txt        # Core dependencies only
```

**Implementation notes:**
1. Templates stay at root (simpler Flask configuration)
2. Core routes are in `core/routes/` subdirectory
3. `core/shared.py` contains mail instance and progress_store
4. All models stay in `core/models.py` (IncomingSMS included, just not used by minimal app)

## Implementation Plan

### Phase 1: Create Core Package

1. Create `core/` directory
2. Move shared models to `core/models.py`
3. Move shared routes (public, admin base, api) to `core/routes/`
4. Move shared services (email only) to `core/services.py`
5. Move shared templates to `core/templates/`

### Phase 2: Extract Optional Features

1. Create `features/scraping/` with scraper code
   - Move `app_scraper.py` to `features/scraping/scraper.py`
   - Move scraping routes from `routes_admin.py`
   - Move scraping templates
2. Create `features/sms/` with SMS services
   - Extract SMS functions from `services.py`
   - Move SMS-related routes
3. Update `local-scraper/local_scraper.py` import path only (keep folder as-is)
   - Change: `from app_scraper import ...`
   - To: `from features.scraping.scraper import setup_chrome_driver, login_to_lcr`
   - Folder structure, batch script, venv, chromedriver all stay unchanged
4. Update imports to use lazy loading where needed

### Phase 3: Create Entry Points

1. Create `app_full.py` that imports core + all features
2. Create `app_minimal.py` that imports core only
3. Update Docker configurations for both

### Phase 4: Cleanup

1. Delete `app-min/` folder
2. Delete `local-scraper/` folder
3. Update documentation
4. Test both configurations

## Files to Modify

| File | Change |
|------|--------|
| `app.py` | Refactor into `app_full.py`, extract core to `core/` |
| `app_scraper.py` | Move to `features/scraping/scraper.py` |
| `routes_admin.py` | Split into `core/routes_admin.py` + `features/scraping/routes.py` |
| `services.py` | Split into `core/services_base.py` + `features/sms/services.py` |
| `models.py` | Move to `core/models.py` |
| `local-scraper/local_scraper.py` | Update import path only (folder stays as-is) |

## New Files to Create

| File | Purpose |
|------|---------|
| `core/__init__.py` | Core package init |
| `core/models.py` | All database models |
| `core/services.py` | Email-only notification services |
| `core/routes/public.py` | Public scheduling routes |
| `core/routes/admin.py` | Core admin routes |
| `core/routes/api.py` | API routes for Flutter app |
| `features/scraping/__init__.py` | Scraping feature module |
| `features/scraping/scraper.py` | LCR scraping logic |
| `features/scraping/routes.py` | Scraping blueprint |
| `features/sms/__init__.py` | SMS feature module |
| `features/sms/services.py` | SMS send functions |
| `app_full.py` | Full-featured entry point |
| `app_minimal.py` | Minimal entry point |
| `requirements-min.txt` | Core dependencies only |

## Files to Delete (after migration)

- `app-min/` (entire folder)
- `app_scraper.py` (moved to `features/scraping/scraper.py`)

## Verification

```bash
# 1. Test full version
python app_full.py
# Verify: Scrape menu visible, SMS settings tab, all features work

# 2. Test minimal version
python app_minimal.py
# Verify: No scrape menu, no SMS tab, email notifications work
# Verify: No import errors for missing selenium/twilio

# 3. Test local scraper (debugging tool)
cd local-scraper
run_local_scraper.bat
# Verify: Prompts for LCR credentials
# Verify: Browser window appears (if selected)
# Verify: CSV output saves correctly

# 4. Build minimal Docker image
docker build -f Dockerfile.min -t app-minimal .
# Verify: Image size ~400MB (not 1.2GB)

# 5. Deploy minimal to Oracle Cloud
# Verify: Memory footprint acceptable for free tier (1GB limit)

# 6. Run existing functionality tests on both configurations
```

## Why Option 3 Over Feature Flags

Given Oracle Cloud free tier constraints (1GB memory) and the recent pattern of features needing duplication (MessageTemplates, API routes, HTML emails), the Shared Modules approach provides:

1. **Real dependency isolation** - Minimal app truly doesn't ship Selenium
2. **Single source of truth** - Core code lives in one place
3. **Flexible features** - Optional features plug in cleanly
4. **Deployment optimization** - Different requirements.txt per configuration

## Alternative: Stay with Current Approach

If restructuring is too much effort right now, the current separate apps approach works. The trade-off is continued duplication when adding features. Consider restructuring when:
- A major feature addition is planned
- The drift between apps causes bugs
- Memory constraints require true minimal deployment
