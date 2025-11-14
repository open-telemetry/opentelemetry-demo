# Source Maps for Splunk RUM

This document explains how source maps are generated, included in the container, and uploaded to Splunk RUM for better error tracking and debugging.

## Overview

Source maps allow Splunk RUM to de-obfuscate minified JavaScript code in production, making error stack traces readable and debuggable. This implementation:

1. Generates source maps during the Next.js build process
2. Includes source maps in the Docker container
3. Uploads source maps to Splunk RUM on container startup
4. Starts the application normally with OpenTelemetry instrumentation

## How It Works

### 1. Source Map Generation

**File:** `next.config.js`
**Configuration:**
```javascript
productionBrowserSourceMaps: true
```

This tells Next.js to generate `.map` files alongside the minified JavaScript bundles during production builds.

**Output Location:** `.next/static/chunks/*.js.map`

### 2. Docker Build Process

**File:** `Dockerfile`

The Dockerfile performs two key steps after building the Next.js application:

**Step 1: Inject sourceMapId**
```dockerfile
RUN npx @splunk/rum-cli sourcemaps inject \
    --path ".next/static"
```

This injects a unique `sourceMapId` into each JavaScript bundle during the build, before the files are copied to the final image. The inject command modifies the files directly in place.

**Step 2: Copy built files**
```dockerfile
COPY --from=builder /app/.next/static/ .next/static/
```

This includes all JavaScript bundles (with injected sourceMapIds) AND their corresponding `.map` files.

### 3. Container Startup

**File:** `start.sh`

On container startup, the script:

1. **Checks for RUM credentials** (environment variables)
2. **Uploads source maps** to Splunk RUM using `@splunk/rum-cli` (sourceMapId already injected during build)
3. **Starts the Next.js server** with OpenTelemetry instrumentation

## Configuration

### Required Environment Variables

To enable sourcemap upload, set these environment variables in your Kubernetes deployment:

```yaml
env:
  - name: API_TOKEN
    valueFrom:
      secretKeyRef:
        name: workshop-secret
        key: api_token
  - name: SPLUNK_RUM_REALM
    valueFrom:
      secretKeyRef:
        name: workshop-secret
        key: realm
  - name: SPLUNK_APP_NAME
    valueFrom:
      secretKeyRef:
        name: workshop-secret
        key: app
  - name: SPLUNK_APP_VERSION
    value: "2.1.3-RUM"  # Optional: defaults to "latest"
```

**Important:** `API_TOKEN` must be an **API access token with RUM ingest permissions**, not the browser RUM token (`SPLUNK_RUM_TOKEN`). This token is used to upload sourcemaps to the Splunk Observability Cloud API.

## Environment Variables Explained

| Variable | Description | Example | Required |
|----------|-------------|---------|----------|
| `API_TOKEN` | API access token with RUM ingest permissions | `ABC123...` | Yes |
| `SPLUNK_RUM_REALM` | Splunk realm (data center) | `us1`, `us0`, `eu0` | Yes |
| `SPLUNK_APP_NAME` | Application name in Splunk RUM | `dev-astronomy-store` | Yes |
| `SPLUNK_APP_VERSION` | Application version | `2.1.3-RUM`, `1.0.0` | No (defaults to `latest`) |

## Startup Process Flow

```
Docker Build
    ↓
npm run build (generate .js and .map files)
    ↓
Inject sourceMapId into .js files
    ↓
Copy files to final image
    ↓
    ↓
Container Start
    ↓
Check RUM Environment Variables
    ↓
    ├─ If configured: Upload Sourcemaps
    │   ├─ Run: npx @splunk/rum-cli sourcemaps upload
    │   ├─ Upload all .map files from .next/static/
    │   └─ Log: "✅ Sourcemap processing completed"
    │
    └─ If not configured: Skip upload
        └─ Log: "ℹ️  Skipping sourcemap upload"
    ↓
Start Next.js Server
    └─ exec node server.js (with NODE_OPTIONS)
```

## Startup Script Details

**File:** `start.sh`

### Sourcemap Upload Command

The startup script uploads sourcemaps that were prepared during the Docker build:

```bash
npx @splunk/rum-cli sourcemaps upload \
  --path ".next/static" \
  --realm "$SPLUNK_RUM_REALM" \
  --token "$API_TOKEN" \
  --app-name "$SPLUNK_APP_NAME" \
  --app-version "${SPLUNK_APP_VERSION:-latest}"
```

**Note:** The `sourceMapId` injection happens during Docker build (in the Dockerfile), not at runtime. This ensures the JavaScript files already contain the sourceMapId before being served.

### Parameters

- `--path`: Local path to sourcemap files (scans recursively for `.js.map` files)
- `--realm`: Splunk realm (e.g., `us1`)
- `--token`: API access token with RUM ingest permissions
- `--app-name`: Application name in RUM
- `--app-version`: Application version (defaults to `latest` if not specified)

### Error Handling

If sourcemap upload fails, the script logs a warning but **continues with startup**:
```bash
⚠️  Warning: Sourcemap upload failed, but continuing with startup
```

This ensures the application starts even if sourcemap upload has issues.

## Testing

### Verify Sourcemaps Are Generated

After building:
```bash
docker run --rm frontend:2.1.3-RUM ls -la .next/static/chunks/*.map
```

You should see `.map` files for each JavaScript chunk.

### Test Sourcemap Upload

Check container logs after startup:
```bash
kubectl logs deployment/frontend | grep -A5 "Uploading sourcemaps"
```

Expected output:
```
📤 Uploading sourcemaps to Splunk RUM...
   Realm: us1
   App: dev-astronomy-store
   Version: 2.1.3-RUM
   Note: sourceMapId was injected during Docker build
📤 Uploading sourcemaps...
✅ Sourcemap processing completed
```

### Verify in Splunk RUM

1. Generate an error in the application (e.g., click a broken feature)
2. Go to Splunk RUM → Errors
3. Click on the error
4. Check the stack trace - it should show:
   - **Original source file names** (not minified)
   - **Original line numbers**
   - **Original variable names**

## Troubleshooting

### No Sourcemap Upload Logs

**Symptom:** No "Uploading sourcemaps" message in logs

**Causes:**
- Missing RUM environment variables
- Variables set to empty strings

**Fix:**
```bash
# Check if environment variables are set in the pod
kubectl exec -it deployment/frontend -- env | grep SPLUNK
```

### Upload Fails with Authentication Error

**Symptom:** `Error: Authentication failed` with 401 status code

**Causes:**
- Invalid `API_TOKEN`
- Token doesn't have RUM ingest permissions
- Using browser RUM token instead of API access token

**Fix:**
- Verify you're using an **API access token**, not the browser RUM token
- Check token has **RUM ingest permissions** in Splunk Observability Cloud
- Verify token in Organization Settings → Access Tokens

### Warnings About Missing sourceMapId

**Symptom:** `WARN No sourceMapId was found in the related JavaScript file` during upload

**Solution:**
As of version 2.1.3-RUM, sourceMapId injection is performed **during Docker build**, not at runtime. If you're seeing these warnings:

1. **Rebuild the Docker image** - The inject step was added to the Dockerfile
2. **Check build logs** - You should see "Inject sourceMapId into built JavaScript files" during build
3. **Verify injection worked** - The warnings should disappear after rebuilding

**If warnings persist:**
- Sourcemaps will still work for error de-obfuscation
- The sourceMapId is an optimization, not a requirement
- Splunk RUM matches sourcemaps by filename as a fallback

### Upload Fails with "No sourcemaps found"

**Symptom:** `Error: No sourcemap files found in .next/static`

**Causes:**
- `productionBrowserSourceMaps: true` not set in `next.config.js`
- Build didn't generate sourcemaps

**Fix:**
```bash
# Verify next.config.js has the setting
grep productionBrowserSourceMaps next.config.js

# Rebuild the image
./build-frontend.sh 2.1.3-RUM
```

### Wrong URL Prefix

**Symptom:** Sourcemaps uploaded but not applied to errors

**Causes:**
- `SPLUNK_RUM_URL_PREFIX` doesn't match actual URL where JS is served
- CDN or proxy changes the URL

**Fix:**
1. Check browser DevTools Network tab
2. Look at the URL for a `.js` file (e.g., `main-abc123.js`)
3. Extract the prefix (e.g., `https://example.com/_next/static/`)
4. Set `SPLUNK_RUM_URL_PREFIX` to match

### Container Startup Delay

**Symptom:** Container takes longer to start

**Causes:**
- Sourcemap upload happens on every container start
- Large number of sourcemap files

**Mitigation:**
- This is expected behavior
- Upload typically takes 5-10 seconds
- Consider uploading sourcemaps as a separate deployment step if startup time is critical

## Build Without Sourcemap Upload

If you want to build the image but skip sourcemap upload at runtime, simply don't set the required environment variables:

```yaml
# Don't include these:
# - API_TOKEN
# - SPLUNK_RUM_REALM
# - SPLUNK_APP_NAME
```

The container will start normally and log:
```
ℹ️  Skipping sourcemap upload (API_TOKEN not provided)
   Note: Use API_TOKEN (API token with RUM ingest permissions), not SPLUNK_RUM_TOKEN
```

## Security Considerations

### Source Maps Contain Source Code

Source maps contain your **original source code** which may include:
- Business logic
- API endpoints
- Comments
- Internal variable names

**Recommendation:** Only upload sourcemaps to trusted Splunk RUM instances, not public repositories.

### Token Security

The `API_TOKEN` should be:
- Stored in Kubernetes Secrets
- Never committed to source control
- Rotated periodically
- Limited to RUM ingest permissions only
- **Must be an API access token**, not the browser RUM token

## React Minified Errors

You may see errors like:

```
Minified React error #418; visit https://react.dev/errors/418 for the full message
```

**Why this happens:**
- React itself is pre-minified from npm
- React doesn't include source maps in the npm package
- Our webpack source maps don't cover React's internal code

**What's covered by our source maps:**
- ✅ Your application code (pages, components, utils)
- ✅ Code bundled by webpack
- ✅ Your custom error handlers
- ❌ React's internal errors (pre-minified)

**How to handle it:**
1. Visit the error URL (e.g., `https://react.dev/errors/418`)
2. The URL provides the full error message and explanation
3. Your application's stack trace will still be de-obfuscated

**Alternative approaches:**
- Use React development build (not recommended for production - much larger)
- Create an error boundary to catch and decode React errors client-side
- The minified error numbers are stable and documented

## Related Files

- `next.config.js` - Enables sourcemap generation
- `Dockerfile` - Copies sourcemaps into container and injects sourceMapId
- `start.sh` - Uploads sourcemaps on container start
- `package.json` - Includes `@splunk/rum-cli` dependency

## Version History

- **v2.1.3-RUM** - Initial sourcemap support
  - Sourcemap generation enabled
  - Startup script with upload
  - Graceful failure handling
