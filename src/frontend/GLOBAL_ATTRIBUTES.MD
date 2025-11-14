# Splunk RUM Global Attributes

This document describes the dynamic user attribute system for Splunk Real User Monitoring (RUM) in the frontend application.

## Overview

The application generates deterministic user attributes based on session IDs, providing consistent user profiles across page loads while allowing easy reset for demo purposes. These attributes are sent with all RUM telemetry data.

## Global Attributes

The following attributes are automatically set for each user session:

- **`enduser.id`**: User ID (Admin: 34/37/41, Member: 1000-6000, Guest: 99999)
- **`enduser.role`**: User role (Admin, Member, or Guest)
- **`deployment.type`**: Deployment environment identifier (default: "green")

## User Generation

Users are generated deterministically from a UUID session ID using a seeded random number generator. This ensures the same session ID always produces the same user attributes.

### User Distribution

- **8%** Admin users (IDs: 34, 37, or 41)
- **42%** Member users (IDs: random between 1000-6000)
- **50%** Guest users (ID: 99999)

### Example Console Output

```
Session ID for RUM: 2dfb9f2e-1b01-4dea-bb4d-a34a34f74f99
Generated user from session ID: 2dfb9f2e-1b01-4dea-bb4d-a34a34f74f99 -> User ID: 3912 Role: Member
Generated Splunk RUM User Attributes: { "enduser.id": "3912", "enduser.role": "Member", "deployment.type": "green" }
```

## Session Management

### Session Timeout

Sessions automatically expire after **30 minutes** of inactivity. When a session expires:
1. The old session is removed from localStorage
2. A new UUID is generated
3. New user attributes are calculated from the new UUID
4. Console logs show the new session creation

### Session Persistence

Sessions are stored in browser localStorage with the following structure:

```json
{
  "userId": "2dfb9f2e-1b01-4dea-bb4d-a34a34f74f99",
  "currencyCode": "USD",
  "timestamp": 1699876543210
}
```

## Resetting Global Attributes

### Manual Reset (Demo Mode)

For demonstration purposes, you can manually reset the user session and generate new attributes:

1. **Navigate to the home page** (`/`)
2. **Click the logo** at the top of the page
3. You will see a visual indicator: **"🔄 Resetting User..."**
4. The page will reload with new user attributes

**Important Notes:**
- Logo reset **only works on the home page** (`/`)
- On other pages, clicking the logo performs normal navigation without resetting
- This ensures consistent user identity during multi-page interactions

### Console Output on Reset

When you reset the session via logo click, you'll see:

```
🔄 Session reset - generating new user...
Session ID for RUM: 8a3c2d1e-4f5a-6b7c-8d9e-0f1a2b3c4d5e
Generated user from session ID: 8a3c2d1e-4f5a-6b7c-8d9e-0f1a2b3c4d5e -> User ID: 41 Role: Admin
✅ New user generated: { "enduser.id": "41", "enduser.role": "Admin", "deployment.type": "green" }
✅ RUM global attributes updated for current session
```

### Automatic Reset

Sessions are automatically reset in the following scenarios:
- After 30 minutes of inactivity
- When localStorage is cleared manually
- When opening the site in a new browser or incognito window

## Configuring Deployment Type

### Using Environment Variables

Set the `DEPLOYMENT_TYPE` environment variable to configure the deployment identifier:

```bash
export DEPLOYMENT_TYPE=blue
```

Or in your `.env` file:

```
DEPLOYMENT_TYPE=blue
```

### Default Value

If no `DEPLOYMENT_TYPE` environment variable is provided, the system defaults to **"green"**.

### Available in Browser

The deployment type is made available to the browser via `window.ENV.DEPLOYMENT_TYPE` and is set during Next.js server-side rendering in `_document.tsx`.

## Technical Implementation

### File Locations

- **`/public/global-attributes.js`**: Client-side script that generates user attributes
- **`/pages/_document.tsx`**: Loads scripts and initializes Splunk RUM
- **`/components/Header/Header.tsx`**: Implements logo click reset functionality

### Initialization Order

1. `window.ENV` is injected with environment variables
2. Splunk RUM SDK scripts are loaded from CDN
3. `global-attributes.js` is loaded, defining `getSplunkGlobalAttributes()`
4. Splunk RUM is initialized with global attributes from the function

### Key Functions

**`getSplunkGlobalAttributes()`**
- Main function called during RUM initialization
- Returns object with all global attributes

**`getSessionId()`**
- Retrieves or creates session UUID
- Checks for 30-minute expiration
- Stores session in localStorage

**`randomUser(sessionID)`**
- Generates deterministic user ID and role
- Uses seeded random number generator for consistency

**`simpleHash(str)`**
- Creates numeric hash from session UUID
- Used as seed for random number generator

## Debugging

### Check Current Session

Open browser console and run:

```javascript
localStorage.getItem('session')
```

### Check Current Attributes

```javascript
getSplunkGlobalAttributes()
```

### View RUM Configuration

```javascript
window.SplunkRum
```

### Clear Session Manually

```javascript
localStorage.removeItem('session')
window.location.reload()
```

## Common Scenarios

### Testing Different User Roles

1. Click the logo on the home page to reset
2. Repeat until you get the desired role
3. Note: Distribution is 8% Admin, 42% Member, 50% Guest

### Testing with Specific Deployment Type

1. Set `DEPLOYMENT_TYPE` environment variable
2. Rebuild and restart the application
3. Hard refresh browser (Ctrl+Shift+R / Cmd+Shift+R) to clear cache

### Demo Workflow

1. Start on home page with generated user
2. Navigate through application (user remains consistent)
3. Return to home page when ready to demo a new user
4. Click logo to reset and get new user
5. Continue demo with new user profile
