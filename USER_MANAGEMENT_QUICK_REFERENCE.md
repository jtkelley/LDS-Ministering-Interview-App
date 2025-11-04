# Quick Reference: User Management Features

## 🎯 Admin Routes (All Require Admin Role)

| Route | Method | Purpose |
|-------|--------|---------|
| `/admin/users` | GET | View user management dashboard |
| `/admin/users/create` | GET/POST | Create new user directly |
| `/admin/users/<id>/edit` | GET/POST | Edit user role/status |
| `/admin/users/<id>/delete` | POST | Delete user |
| `/admin/users/invite` | GET/POST | Send user invitation |
| `/admin/invitations/<id>/cancel` | POST | Cancel pending invitation |

## 👤 User Routes (All Authenticated Users)

| Route | Method | Purpose |
|-------|--------|---------|
| `/user/change-password` | GET/POST | Change password (Flask-User) |
| `/user/forgot-password` | GET/POST | Request password reset (Flask-User) |
| `/user/reset-password/<token>` | GET/POST | Reset password with token (Flask-User) |

## 🔓 Public Routes

| Route | Method | Purpose |
|-------|--------|---------|
| `/user/accept-invite/<token>` | GET/POST | Accept invitation and create account |

---

## 🔑 Key Features

### Change Password
- **Who:** Any logged-in user
- **Where:** User dropdown menu → "Change Password"
- **Requirements:** Current password + new password

### Forgot Password
- **Who:** Anyone (public)
- **Where:** Login page (link if available)
- **Flow:** Email address → Check email → Click link → Set new password

### Create User
- **Who:** Admin only
- **Where:** Manage Users → Create User Directly
- **Instant:** User can login immediately with given password

### Invite User
- **Who:** Admin only
- **Where:** Manage Users → Send User Invitation
- **Flow:** Admin sends → User gets email → User clicks link → Sets password → Account created
- **Expiry:** 7 days

### Manage Users
- **Who:** Admin only
- **Where:** Navbar → "Manage Users"
- **Actions:** List, Edit (role/status), Delete, View invitations, Cancel invites

---

## 🛡️ Protection & Rules

### Password Rules
- Minimum: 6 characters
- Maximum: 72 bytes (important for hashing)
- Must be confirmed on change

### User Management Rules
- Cannot delete yourself
- Cannot delete last admin
- Cannot edit your own account from admin panel
  - Use "Change Password" from dropdown instead

### Invitation Rules
- One invitation per email at a time
- Expires after 7 days
- One-time use only
- Cannot accept if user already exists

---

## 📧 Email Templates

### Invitation Email
```
Subject: You are invited to Ministering Interview App

Body includes:
- Role (admin/interviewer)
- Secure acceptance link
- 7-day expiration notice
```

### Password Reset Email
```
Subject: Password reset request

Body includes:
- Secure password reset link
- 24-hour expiration notice
```

---

## 🧬 Database Schema

### UserInvitation Table
```
id              - Auto-increment ID
email           - Invited email (unique)
token           - Secure token (unique)
role            - 'admin' or 'interviewer'
created_at      - When invitation was sent
expires_at      - When invitation expires
accepted_at     - When/if accepted
accepted_by_user_id - ID of created user
created_by_user_id  - ID of admin who invited
is_used         - Boolean flag
```

---

## ⚙️ Configuration

All config in `app.py`:
```python
app.config['USER_ENABLE_FORGOT_PASSWORD'] = True
app.config['USER_ENABLE_CHANGE_PASSWORD'] = True
app.config['USER_EMAIL_SENDER_EMAIL'] = os.environ.get('MAIL_USERNAME')
app.config['USER_EMAIL_SENDER_NAME'] = 'Ministering Interview App'
```

---

## 🚨 Common Issues & Fixes

**Emails not sending?**
- Check `MAIL_USERNAME` and `MAIL_PASSWORD` env vars
- Check Gmail app password if using Gmail
- Check SMTP settings in `app.py`

**Invitation link doesn't work?**
- Ensure token wasn't manually edited
- Check expiration date hasn't passed
- Ensure email isn't already registered

**Can't change password?**
- Ensure you're logged in
- Current password must be correct
- New password must be different

---

## 🔄 Common Workflows

### Add New Interviewer
1. Admin → Manage Users
2. Click "Send User Invitation"
3. Enter email, select "Interviewer"
4. Send
5. User receives email, accepts, creates account

### Add New Admin
1. Admin → Manage Users
2. Click "Send User Invitation"
3. Enter email, select "Admin"
4. Send
5. User receives email, accepts, creates account

### Change Admin Role to Interviewer
1. Admin → Manage Users
2. Click "Edit" next to user
3. Change role to "Interviewer"
4. Save
5. User is now interviewer

### Disable User Account
1. Admin → Manage Users
2. Click "Edit" next to user
3. Uncheck "Account Active"
4. Save
5. User cannot login until re-enabled

### User Forgot Password
1. User → Login page → "Forgot Password"
2. Enter email
3. Check email for reset link
4. Click link, set new password
5. Login with new password

---

## 📊 Navbar Menu Structure

```
┌─ Calendar
├─ Manage Districts
├─ Scrape from LCR
├─ Import from CSV
├─ Manage Users (Admin only)
└─ User Menu (dropdown)
   ├─ Email Address ▼
   ├─ Change Password
   └─ Logout
```

---

*For detailed implementation info, see: `USER_MANAGEMENT_IMPLEMENTATION.md`*
