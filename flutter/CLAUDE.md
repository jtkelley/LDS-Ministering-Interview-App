# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Flutter mobile app for the Ministering Interviews scheduling system. It serves as a companion to the Flask backend (in the parent directory), allowing administrators to send bulk SMS/email notifications to members who need to schedule interviews.

The app connects to the Flask backend API to fetch member data and log notifications sent via the device.

## Development Commands

```bash
# Get dependencies
flutter pub get

# Run on connected device/emulator
flutter run

# Build debug APK
flutter build apk --debug

# Build release APK
flutter build apk --release

# Run static analysis
flutter analyze

# Run tests
flutter test
```

## API Configuration

The backend URL is configured in `lib/config/api_config.dart`:
- Default: `http://10.0.2.2:8181` (Android emulator → localhost)
- For physical device testing: change to your computer's local IP address
- For production: update to the deployed server URL

## Architecture

### State Management

Uses Provider pattern with three main providers:
- **ApiService** (`lib/services/api_service.dart`) - Singleton for all HTTP communication with Flask backend, handles JWT token storage via SharedPreferences
- **AuthProvider** (`lib/providers/auth_provider.dart`) - Authentication state, login/logout
- **MembersProvider** (`lib/providers/members_provider.dart`) - Member list, district filters, selection state, bulk operations

### Models

- **Member** - Church member with contact info, booking status, and notification history. Has two factory constructors: `fromListJson` (partial data from list endpoint) and `fromDetailJson` (full data from detail endpoint)
- **District** - Organizational unit containing companionships
- **NotificationRecord** - Tracks sent email/SMS notifications

### Services

- **InviteService** (`lib/services/invite_service.dart`) - Handles notification sending:
  - **Android bulk SMS**: Uses `telephony` package to send SMS directly (uses device plan, free)
  - **iOS SMS**: Opens native Messages app for each recipient via `url_launcher`
  - **Email**: Server-side bulk email or native email app via `url_launcher`

### Screens

- **LoginScreen** - JWT authentication with Flask backend
- **MemberListScreen** - Main screen with district filter, member selection, bulk SMS/email actions
- **MemberDetailScreen** - Individual member view with contact info, companionship members, notification history

## Platform-Specific Notes

### Android
- Requires `SEND_SMS` and `READ_PHONE_STATE` permissions (declared in AndroidManifest.xml)
- Uses AGP 8.7.0 with Kotlin DSL (`build.gradle.kts`)
- minSdk is 23 (Android 6.0) due to `another_telephony` package requirement
- The `another_telephony` package enables bulk SMS without per-message confirmation

### iOS
- Cannot send SMS programmatically; opens Messages app for each recipient
- Bulk SMS workflow requires manual user interaction for each message

## Backend API Endpoints

All endpoints require JWT Bearer token (except login):
- `POST /api/auth/login` - Get JWT token
- `GET /api/auth/me` - Verify token, get user info
- `GET /api/districts` - List districts
- `GET /api/members` - List members (supports `district_id`, `needs_invite` filters)
- `GET /api/members/:id` - Member detail with companionship and notification history
- `POST /api/members/:id/log-notification` - Log notification sent via device
- `POST /api/notifications/send-bulk-email` - Send emails via server
- `POST /api/notifications/log-bulk` - Log multiple notifications
