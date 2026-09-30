# Values for the current setup (personal subscription). Edit these when moving
# to another Azure account. Nothing here is secret.

subscription_id = "88e59ba1-f869-410e-a9cd-a7ff269952a6"
acr_name        = "oteldemo5352cb"

# The cluster was first created with `az aks create`, which picked this prefix.
# A new setup can drop this line and use the default.
aks_dns_prefix = "otel-demo--otel-demo-rg-88e59b"
