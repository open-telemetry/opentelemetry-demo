# Feature Flags

This demo comes with several feature flags which can control failure conditions
in specific services. By default the flags are disabled. Using the Feature Flags
UI <http://localhost:8081> you will be able to control the status of these
feature flags.

| Feature Flag            | Service(s)      | Description                                                               |
|-------------------------|-----------------|---------------------------------------------------------------------------|
| `productCatalogFailure` | Product Catalog | Generate an error for `GetProduct` requests with product id: `OLJCESPC7Z` |
| `shippingFailure`       | Shipping        | Induce very long latency when shipping outside of USA                     |
