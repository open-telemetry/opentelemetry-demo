# Demo Error Feature for RUM Source Map Testing

This document describes the demo error feature built into the application for testing Splunk RUM source map functionality.

## Overview

A safe, non-disruptive demo error button has been added to the home page to allow easy testing of:
- Splunk RUM error tracking
- Source map de-obfuscation
- Error stack trace visualization
- RUM error analytics

## How to Trigger the Demo Error

There are two ways to trigger the demo error:

### Method 1: Hidden Button
1. Navigate to the home page
2. Look in the bottom-right corner
3. Hover over the semi-transparent "🐛 Demo Error" button
4. Click the button

### Method 2: Keyboard Shortcut
1. Navigate to the home page
2. Press **Ctrl+Shift+E** (Windows/Linux) or **Cmd+Shift+E** (Mac)

## What Happens

When triggered, the demo error:

1. **Simulates a realistic error scenario**:
   - Attempts to process user data
   - Encounters a null value (missing cache data)
   - Throws a descriptive error

2. **Creates a multi-level stack trace**:
   ```
   triggerDemoError()
     → processUserData()
       → simulateDatabaseError()
         → throw Error()
   ```

3. **Logs to console**:
   ```
   Demo error triggered for RUM testing: Error: Demo Error: Failed to fetch user preferences from cache
   ```

4. **Sends to Splunk RUM**:
   - Error name: "Error"
   - Error message: "Demo Error: Failed to fetch user preferences from cache"
   - Stack trace with source file names and line numbers

## Error Details

**Error Message:**
```
Demo Error: Failed to fetch user preferences from cache
```

**Stack Trace (before source maps):**
```
Error: Demo Error: Failed to fetch user preferences from cache
    at simulateDatabaseError (main-abc123.js:2341)
    at processUserData (main-abc123.js:2346)
    at triggerDemoError (main-abc123.js:2353)
    at onClick (main-abc123.js:2389)
```

**Stack Trace (after source maps applied):**
```
Error: Demo Error: Failed to fetch user preferences from cache
    at simulateDatabaseError (pages/index.tsx:18)
    at processUserData (pages/index.tsx:24)
    at triggerDemoError (pages/index.tsx:33)
    at onClick (pages/index.tsx:78)
```

## Verifying Source Maps in Splunk RUM

After triggering the demo error:

1. **Open Splunk RUM**
2. **Navigate to Errors**
3. **Find the error**:
   - Filter by error message: "Failed to fetch user preferences from cache"
   - Look for errors from the current session

4. **Examine the stack trace**:
   - ✅ **With working source maps**: You'll see `pages/index.tsx` with correct line numbers
   - ❌ **Without source maps**: You'll see minified file names like `main-abc123.js`

5. **Check error attributes**:
   - `error.type`: "Error"
   - `error.message`: "Demo Error: Failed to fetch user preferences from cache"
   - `page.url`: Home page URL
   - User session details

## Safety Features

The demo error is designed to be safe:

1. **Does not affect application state**
   - Error is caught and logged
   - Application continues running normally
   - No data is modified

2. **Does not disrupt user experience**
   - Button is semi-transparent and non-intrusive
   - Located in bottom-right corner
   - Only visible to users who look for it

3. **Clear labeling**
   - Error message prefixed with "Demo Error:"
   - Console log indicates it's for RUM testing
   - Button clearly labeled as demo

4. **No network calls**
   - Error is generated entirely client-side
   - No backend services are called
   - No real cache lookup is attempted

## Use Cases

### During Development
- Test that RUM is capturing errors correctly
- Verify error attributes are being set
- Test error tracking without breaking real features

### During Demos
- Show how RUM captures and displays errors
- Demonstrate source map de-obfuscation
- Compare minified vs. de-obfuscated stack traces
- Showcase error analytics and dashboards

### During Testing
- Verify source maps uploaded correctly
- Test error alerting workflows
- Validate error dashboards and queries

## Removing the Demo Error

If you want to remove the demo error feature:

1. **Remove the button**:
   - Delete lines 76-99 in `pages/index.tsx`

2. **Remove the keyboard handler**:
   - Delete lines 48-54 in `pages/index.tsx`
   - Remove `onKeyDown={handleKeyPress} tabIndex={0}` from line 61

3. **Remove the error functions**:
   - Delete lines 16-39 in `pages/index.tsx`

4. **Rebuild the image**

## Splunk RUM Queries

### Find all demo errors
```
error.message="*Demo Error*"
```

### Count demo errors by session
```
error.message="*Demo Error*" | stats count by rum.session_id
```

### Demo errors in last hour
```
error.message="*Demo Error*" AND _time > now()-1h
```

## Related Files

- `pages/index.tsx` - Contains demo error implementation
- `SOURCEMAPS.md` - Documentation on source map setup
- `ORDER_CONFIRMATION.md` - Other custom instrumentation examples

## Version History

- **v2.1.3-RUM** - Initial demo error feature
  - Button in bottom-right corner
  - Keyboard shortcut support
  - Multi-level stack trace
  - Safe, non-disruptive implementation
