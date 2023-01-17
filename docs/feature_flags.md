# Feature Flags

This demo comes with several feature flags which can control failure conditions
in specific services. By default the flags are disabled. Using the Feature Flags
UI <http://localhost:8080/feature> you will be able to control the status of these
feature flags.

| Feature Flag            | Service(s)      | Description |
|-------------------------|-----------------|---------------------------------------------------------------------------------------------------------|
| `productCatalogFailure` | Product Catalog | Generate an error for `GetProduct` requests with product id: `OLJCESPC7Z`                               |
| `recommendationCache`   | Recommendation  | Create a memory leak due to an exponentially growing cache. 1.4x growth, 50% of requests trigger growth. |
