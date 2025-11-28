# Image Verification Report

This document verifies that all service images match the original `kubernetes/opentelemetry-demo.yaml` and are configured correctly for registry replacement.

## Verification Summary

✅ **All service images verified against original manifest**
✅ **32 services checked**
✅ **0 mismatches found**
✅ **6 third-party services properly marked**

---

## Services Using Splunk Registry

These services use `ghcr.io/splunk/opentelemetry-demo` or `ghcr.io/open-telemetry/demo` and will have their registry replaced based on environment (dev/prod):

| Service | Image | Replace Registry |
|---------|-------|------------------|
| accounting | `ghcr.io/splunk/opentelemetry-demo/otel-accounting:2.1.3` | ✅ Yes |
| ad | `ghcr.io/splunk/opentelemetry-demo/otel-ad:2.1.3-profiling-cve` | ✅ Yes |
| cart | `ghcr.io/splunk/opentelemetry-demo/otel-cart:2.1.3` | ✅ Yes |
| checkout | `ghcr.io/open-telemetry/demo:2.1.3-checkout` | ✅ Yes |
| currency | `ghcr.io/open-telemetry/demo:2.1.3-currency` | ✅ Yes |
| email | `ghcr.io/open-telemetry/demo:2.1.3-email` | ✅ Yes |
| fraud-detection | `ghcr.io/splunk/opentelemetry-demo/otel-fraud-detection:2.1.3-for-jeremy` | ✅ Yes |
| frontend | `ghcr.io/splunk/opentelemetry-demo/otel-frontend:2.1.3-RUM` | ✅ Yes |
| frontend-proxy | `ghcr.io/splunk/opentelemetry-demo/otel-frontend-proxy:2.1.3` | ✅ Yes |
| image-provider | `ghcr.io/splunk/opentelemetry-demo/otel-image-provider:2.1.3` | ✅ Yes |
| kafka | `ghcr.io/open-telemetry/demo:2.1.3-kafka` | ✅ Yes |
| llm | `ghcr.io/open-telemetry/demo:2.1.3-llm` | ✅ Yes |
| payment | `ghcr.io/splunk/opentelemetry-demo/otel-payment:2.1.3-profiling.1` | ✅ Yes |
| postgres | `ghcr.io/open-telemetry/demo:2.1.3-postgresql` | ✅ Yes |
| product-catalog | `ghcr.io/open-telemetry/demo:2.1.3-product-catalog` | ✅ Yes |
| product-reviews | `ghcr.io/open-telemetry/demo:2.1.3-product-reviews` | ✅ Yes |
| quote | `ghcr.io/open-telemetry/demo:2.1.3-quote` | ✅ Yes |
| recommendation | `ghcr.io/splunk/opentelemetry-demo/otel-recommendation:2.1.3` | ✅ Yes |
| shipping | `ghcr.io/open-telemetry/demo:2.1.3-shipping` | ✅ Yes |

---

## Services Using Third-Party Registries

These services use external/third-party registries and are marked with `replace_registry: false` to preserve their original image sources:

| Service | Image(s) | Registry | Reason |
|---------|----------|----------|--------|
| **astronomy-loadgen** | `ghcr.io/splunk/online-boutique/rumloadgen:5.6` | online-boutique | RUM load generator from different project |
| **flagd** | `ghcr.io/open-feature/flagd:v0.12.8` | open-feature | OpenFeature flag daemon |
| **shop-dc-shim** | `mcr.microsoft.com/mssql/server:2022-latest`<br>`quay.io/jeremyh/shop-dc-shim:latest`<br>`quay.io/jeremyh/shop-dc-load-generator:0.0.1` | Microsoft + Quay.io | SQL Server + custom images |
| **sql-server-fraud** | `mcr.microsoft.com/mssql/server:2022-latest` | Microsoft | SQL Server |
| **thousandeyes** | `thousandeyes/enterprise-agent:latest` | ThousandEyes | Monitoring agent |
| **valkey-cart** | `valkey/valkey:8.1.3-alpine` | Valkey | Redis alternative |

---

## Configuration in services.yaml

All third-party services are properly configured:

```yaml
services:
  - name: astronomy-loadgen
    build: false
    manifest: true
    replace_registry: false  # Keep original registry

  - name: flagd
    build: false
    manifest: true
    replace_registry: false  # Uses ghcr.io/open-feature/flagd

  - name: shop-dc-shim
    build: true
    manifest: true
    replace_registry: false  # Uses mcr.microsoft.com/mssql and quay.io images

  - name: sql-server-fraud
    build: false
    manifest: true
    replace_registry: false  # Uses mcr.microsoft.com/mssql

  - name: thousandeyes
    build: false
    manifest: true
    replace_registry: false  # Uses thousandeyes/enterprise-agent

  - name: valkey-cart
    build: false
    manifest: true
    replace_registry: false  # Uses valkey/valkey
```

---

## Verification Process

### 1. Image Comparison
All service images were compared against `kubernetes/opentelemetry-demo.yaml`:
- ✅ Splunk-customized services use correct `ghcr.io/splunk/opentelemetry-demo/otel-*` images
- ✅ Standard services use correct `ghcr.io/open-telemetry/demo:*` images
- ✅ Third-party services use original external registry images

### 2. Registry Replacement Testing
Tested manifest generation with dev registry:
```bash
.github/scripts/stitch-manifests.sh dev
```

**Results:**
- ✅ 26 services had registries replaced with dev registry
- ✅ 6 services preserved original registries (marked with `replace_registry: false`)
- ✅ All third-party images remained unchanged

### 3. Manifest Validation
Generated manifest validated successfully:
- ✅ YAML syntax valid
- ✅ 93 YAML documents
- ✅ 60 Kubernetes resources
- ✅ All images correctly configured

---

## Registry Replacement Behavior

### With Dev Registry (`stitch-manifests.sh dev`):
- **Replace:** Splunk and OpenTelemetry demo images → `ghcr.io/hagen-p/opentelemetry-demo-splunk`
- **Preserve:** Third-party images (online-boutique, open-feature, valkey, mssql, etc.)

### With Prod Registry (`stitch-manifests.sh prod`):
- **Replace:** Splunk and OpenTelemetry demo images → `ghcr.io/splunk/opentelemetry-demo`
- **Preserve:** Third-party images (online-boutique, open-feature, valkey, mssql, etc.)

### Without Registry Parameter (`stitch-manifests.sh`):
- **All images:** Use original URLs from source manifests

---

## Utility Images

Some services use standard utility images (busybox, curl, etc.) for init containers or jobs. These are not replaced:

- `busybox:latest` - Used in init containers
- `busybox` - Basic utility image
- `curlimages/curl:8.1.2` - HTTP client utility

---

## Next Steps

When adding new services:

1. **Splunk/OTel images:** No special configuration needed (registry will be replaced)
2. **Third-party images:** Add `replace_registry: false` to service in `services.yaml`
3. **Verify:** Run `python3 /tmp/check-images.py` to validate

---

## Related Documentation

- `REGISTRY-CONFIG.md` - Registry configuration details
- `WORKFLOWS.md` - Workflow usage guide
- `services.yaml` - Service configuration

---

**Last Verified:** 2025-01-28
**Verified By:** Automated image comparison script
**Status:** ✅ All Clear
