-- Copyright The OpenTelemetry Authors
-- SPDX-License-Identifier: Apache-2.0

-- Feature Flags created and initialized on startup
--     'enabled' is a decimal value between 0 and 1 (inclusive)
--     0.0 is always disabled
--     1.0 is always enabled
--     All values between set a percentage chance on each request
--     example: 0.55 is enabled 55% of the time
INSERT INTO public.featureflags (name, description, enabled)
VALUES
    ('productCatalogFailure', 'Fail product catalog service on a specific product', 0),
    ('recommendationCache', 'Cache recommendations', 0),
    ('adServiceFailure', 'Fail ad service requests', 0),
    ('cartServiceFailure', 'Fail cart service requests', 0);
