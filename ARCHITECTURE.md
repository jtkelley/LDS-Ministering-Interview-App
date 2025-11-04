# User Management System - Visual Architecture

## User Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    MINISTERING INTERVIEW APP                     │
│                      USER MANAGEMENT SYSTEM                      │
└─────────────────────────────────────────────────────────────────┘

ADMIN WORKFLOWS
═══════════════════════════════════════════════════════════════════

    ┌──────────────────┐
    │  Admin Login     │
    └────────┬─────────┘
             │
             ▼
    ┌──────────────────────────┐
    │   Manage Users Page      │  ← /admin/users
    │  (/admin/users)          │
    └─┬──────┬──────┬─────┬────┘
      │      │      │     └─────────────────┐
      │      │      │                       │
      ▼      ▼      ▼                       ▼
    ┌──────┐ ┌──────┐ ┌───────┐      ┌──────────────┐
    │Create│ │Invite│ │ Edit  │      │ Delete User  │
    │User  │ │User  │ │ User  │      │              │
    │Direct│ │Email │ │Role   │      │ (Protected)  │
    └──┬───┘ └──┬───┘ └───┬───┘      └──────────────┘
       │        │        │
       │        │        ▼
       │        │    ┌─────────────┐
       │        │    │User updated │
       │        │    │immediately  │
       │        │    └─────────────┘
       │        │
       │        ▼
       │    ┌──────────────────┐
       │    │ Email Sent:      │
       │    │ Invitation Link  │
       │    └────────┬─────────┘
       │             │
       │             ▼
       │         ┌────────────────────┐
       │         │ User Accepts Link  │  ← /user/accept-invite/<token>
       │         │ Email in address   │
       │         │ Sets password      │
       │         └────────┬───────────┘
       │                  │
       ▼                  ▼
    ┌──────────────────────────┐
    │  User Account Created    │
    │  Ready to Login          │
    └──────────────────────────┘


USER WORKFLOWS
═══════════════════════════════════════════════════════════════════

    ┌──────────────────┐
    │  User Login      │
    └────────┬─────────┘
             │
             ▼
    ┌──────────────────────────┐
    │  Dashboard               │
    │                          │
    │ Navbar Menu: [▼]         │
    │              │           │
    └──────────────┼───────────┘
                   │
        ┌──────────┼──────────┐
        │                     │
        ▼                     ▼
    ┌────────────┐   ┌─────────────────┐
    │ Change     │   │ Forgot Password │
    │ Password   │   │ (from login)     │
    │            │   │                 │
    │ Current PW │   │ Email → Link    │
    │ New PW     │   │ Reset PW        │
    │ Confirm    │   │ Login           │
    └────────────┘   └─────────────────┘


DATABASE SCHEMA
═══════════════════════════════════════════════════════════════════

User Table
──────────────────────────────────────────
├─ id (PK)
├─ email (UNIQUE)
├─ password (hashed)
├─ role ('admin' | 'interviewer')
├─ active (T/F)
└─ email_confirmed_at

UserInvitation Table (NEW)
──────────────────────────────────────────
├─ id (PK)
├─ email (UNIQUE)
├─ token (UNIQUE) [Secure Random]
├─ role ('admin' | 'interviewer')
├─ created_at [DateTime]
├─ expires_at [DateTime + 7 days]
├─ accepted_at [DateTime]
├─ accepted_by_user_id (FK)
├─ created_by_user_id (FK)
└─ is_used (T/F)


ROUTES TREE
═══════════════════════════════════════════════════════════════════

/admin/
├─ /users                          [GET]  → Manage Users Dashboard
├─ /users/create                   [GET/POST] → Create User Form
├─ /users/<id>/edit                [GET/POST] → Edit User Form
├─ /users/<id>/delete              [POST]     → Delete User
├─ /users/invite                   [GET/POST] → Invite User Form
└─ /invitations/<id>/cancel        [POST]     → Cancel Invitation

/user/
├─ /change-password                [GET/POST] → Change Password (Flask-User)
├─ /forgot-password                [GET/POST] → Forgot Password (Flask-User)
├─ /reset-password/<token>         [GET/POST] → Reset Password (Flask-User)
├─ /login                          [GET/POST] → Login (Flask-User)
└─ /logout                         [GET]      → Logout (Flask-User)

/user/ (Public)
└─ /accept-invite/<token>          [GET/POST] → Accept Invitation


SECURITY LAYERS
═══════════════════════════════════════════════════════════════════

Password Security
─────────────────
plaintext password
        ↓
   validate length (6-72 bytes)
        ↓
   require confirmation
        ↓
   hash with pbkdf2_sha256
        ↓
   store hashed in database


Token Security
──────────────
generate secrets.token_urlsafe(32)
        ↓
   store in database (not URL)
        ↓
   set expiration time
        ↓
   track usage (is_used flag)
        ↓
   validate on each use
        ↓
   prevent replay attacks


Role-Based Access
──────────────────
authenticated?
      ↓
   YES: Check role
      ├─ admin: Allow all admin routes
      └─ interviewer: Block admin routes
      ↓
   NO: Redirect to login


NAVBAR STRUCTURE
═══════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────┐
│ Calendar │ Districts │ Scrape │ Import │ Users [admin]    │
│                                      user@email.com ▼       │
│                                      ├─ Change Password   │
│                                      └─ Logout            │
└─────────────────────────────────────────────────────────────┘


EMAIL FLOWS
═══════════════════════════════════════════════════════════════════

Invitation Email
────────────────
Admin sends invite
      ↓
Flask-Mail generates email
      ↓
SMTP to Gmail (smtp.gmail.com:587)
      ↓
User receives email
      ↓
Clicks secure link: /user/accept-invite/<token>
      ↓
Sets password
      ↓
Account created


Password Reset Email
────────────────────
User clicks "Forgot Password"
      ↓
Enters email
      ↓
Flask-User generates token
      ↓
Flask-Mail sends reset link
      ↓
User receives email
      ↓
Clicks link: /user/reset-password/<token>
      ↓
Sets new password
      ↓
Can login with new password


AUTHENTICATION FLOW
═══════════════════════════════════════════════════════════════════

1. User visits /user/login
   ├─ If already logged in → Redirect to /admin
   └─ If not logged in → Show login form

2. User enters email + password

3. Flask-User validates credentials
   ├─ Email exists in database?
   ├─ Password hashes match?
   ├─ Account active?
   └─ Email confirmed?

4. If valid:
   ├─ Create session
   ├─ Set current_user
   └─ Redirect to /admin

5. If invalid:
   └─ Show error, stay on login

6. Logged-in users:
   ├─ Can access role-appropriate routes
   ├─ Navbar shows their email
   ├─ Can change password
   └─ Can access their dashboard


FILE ORGANIZATION
═══════════════════════════════════════════════════════════════════

app.py (Core)
├─ Models
│  ├─ User (existing)
│  └─ UserInvitation (new)
├─ Routes
│  ├─ User Management Routes (new)
│  └─ Existing routes (unchanged)
└─ Config
   └─ USER_ENABLE_* settings

templates/
├─ base.html (updated navbar)
├─ manage_users.html (new)
├─ create_user.html (new)
├─ edit_user.html (new)
├─ invite_user.html (new)
├─ accept_invitation.html (new)
└─ user/
   ├─ change_password.html (new)
   ├─ forgot_password.html (new)
   └─ reset_password.html (new)


FEATURE COMPARISON
═══════════════════════════════════════════════════════════════════

Feature              | Flask-User | Custom | Method
─────────────────────┼────────────┼────────┼──────────────
Change Password      |     ✓      |        | Built-in
Forgot Password      |     ✓      |        | Built-in
Reset with Token     |     ✓      |        | Built-in
Create User Direct   |            |   ✓    | Admin route
Invite via Email     |            |   ✓    | Token-based
Accept Invitation    |            |   ✓    | Public route
User Management      |            |   ✓    | Admin routes
Role Management      |            |   ✓    | Admin routes
User Listing         |            |   ✓    | Admin dashboard
Active/Inactive      |            |   ✓    | Admin dashboard

═══════════════════════════════════════════════════════════════════
✅ ALL FEATURES COMPLETE - READY FOR USE
═══════════════════════════════════════════════════════════════════
