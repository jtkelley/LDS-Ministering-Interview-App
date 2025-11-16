# Database Migration Instructions

This project uses Flask-Migrate (Alembic) for database schema migrations. Follow these steps to manage your database schema:

## 1. Initialize Migrations (First Time Only)

This creates a `migrations/` folder in your project.

```powershell
flask db init
```

## 2. Create a Migration (Whenever You Change Models)

```powershell
flask db migrate -m "Describe your change"
```

## 3. Apply Migrations to the Database

```powershell
flask db upgrade
```

## 4. Roll Back a Migration (if needed)

```powershell
flask db downgrade
```

## 5. Notes
- The `migrations/` folder stores migration scripts and should be committed to version control.
- Make sure your `FLASK_APP` environment variable is set to your main app file (e.g., `app.py`).
- For production, set the `DATABASE_URL` environment variable to your Postgres connection string.

## Example Workflow
```powershell
# First time setup
flask db init

# After changing models
flask db migrate -m "Add new field to User"
flask db upgrade
```

---

## Current Migration: Adding interview_type to Booking

We've added an `interview_type` field to the Booking model. To migrate your database:

```powershell
# Create the migration
flask db migrate -m "Add interview_type to Booking"

# Apply the migration
flask db upgrade
```

**OR** if you don't have existing data you need to keep:

```powershell
# Delete the database file
del instance\interviews.db

# Run the app (it will recreate the database)
python app.py
```

---

For more details, see the Flask-Migrate documentation: https://flask-migrate.readthedocs.io/en/latest/
