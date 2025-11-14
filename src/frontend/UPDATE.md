# Frontend Updates - Version 2.1.3-RUM

This document provides an overview of the new Splunk RUM (Real User Monitoring) and OpenTelemetry features added to the frontend service.

## Overview

The frontend service has been enhanced with comprehensive observability features including Splunk RUM integration, OpenTelemetry backend tracing, custom business event tracking, source map support for error debugging, and demo capabilities for testing and presentations.

## New Features

### 1. Dynamic RUM Global Attributes

**What it does:**
- Generates consistent user identities across sessions using deterministic attributes
- Creates realistic user personas (city, state, device, browser) based on session ID
- Automatically rotates sessions after 30 minutes of inactivity
- Supports deployment type switching (blue/green deployments) via logo click

**Usage:**
- User attributes are automatically generated on first visit
- Sessions persist across page reloads for 30 minutes
- Click the logo on the home page to reset attributes and change deployment type
- All attributes are sent to Splunk RUM for analytics and filtering

**Key attributes:**
- `enduser.id`**: User ID (Admin: 34/37/41, Member: 1000-6000, Guest: 99999)
- `enduser.role`**: User role (Admin, Member, or Guest)
- `deployment.type`**: Deployment environment identifier (default: "green")

**Reference:** See `GLOBAL_ATTRIBUTES.md` for complete details.

---

### 2. Order Confirmation Page & Custom Spans

**What it does:**
- Provides a dedicated order confirmation route for better pageview tracking
- Creates custom OpenTelemetry spans for order events 
- Tracks order details (order ID, item counts, currency) in both backend and frontend spans
- Enables conversion tracking and funnel analysis

**Usage:**
- Order confirmation appears at `/order/confirmation/[orderId]` (separate from checkout flow)
- Backend span `order.confirmed` created when order is placed via `/api/checkout`
- Frontend RUM span `order.confirmed` created when confirmation page loads
- Both spans include order metadata for analytics

**Key benefits:**
- Separate pageview for conversion tracking
- Custom spans for business analytics
- Order ID tracking across backend and frontend
- Funnel tracking: Home → Product → Cart → Checkout → Confirmation

**Reference:** See `ORDER_CONFIRMATION.MD` for implementation details.

---

### 3. Source Maps for Error De-obfuscation

**What it does:**
- Generates source maps for production JavaScript bundles
- Automatically injects sourceMapId during Docker build
- Uploads source maps to Splunk RUM on container startup
- Enables readable stack traces for production errors

**Usage:**
- Source maps are generated automatically during build
- Upload happens on container startup (requires `API_TOKEN` environment variable)
- Errors in Splunk RUM show original source file names and line numbers
- No manual intervention required once configured

**Key environment variables:**
- `API_TOKEN` - API access token with RUM ingest permissions


**What you see in RUM:**
- **Before:** `main-abc123.js:2341` (minified)
- **After:** `pages/index.tsx:18` (readable source)

**Reference:** See `SOURCEMAPS.md` for complete setup and troubleshooting.

---

### 4. Demo Error Feature

**What it does:**
- Provides a safe, non-disruptive way to trigger demo errors for testing
- Creates realistic multi-level stack traces
- Demonstrates source map functionality
- Perfect for demos and testing RUM error tracking

**Usage:**
- **Method 1:** Click the semi-transparent "🐛 Demo Error" button in bottom-right corner
- **Method 2:** Press **Ctrl+Shift+E** (Windows/Linux) or **Cmd+Shift+E** (Mac)

**Error details:**
- Error message: "Demo Error: Failed to fetch user preferences from cache"
- Multi-level stack trace (3 functions deep)
- Automatically caught by RUM
- Application continues running normally

**What you see in RUM:**
```
Error: Demo Error: Failed to fetch user preferences from cache
    at simulateDatabaseError (pages/index.tsx:18)
    at processUserData (pages/index.tsx:24)
    at triggerDemoError (pages/index.tsx:33)
```

**Reference:** See `DEMO_ERROR.md` for detailed usage and queries.

---

### 5. Logging Improvements

**What it does:**
- Standardized logging utility with multiple log levels
- Consistent log format across frontend service
- Environment variable logging for troubleshooting
- Integration with OpenTelemetry instrumentation

**Usage:**
- Logs appear in container output (stdout/stderr)
- Use `kubectl logs` to view logs in Kubernetes
- Structured logging for easier parsing and analysis

**Reference:** See `utils/LOGGING.md` for logging standards.
