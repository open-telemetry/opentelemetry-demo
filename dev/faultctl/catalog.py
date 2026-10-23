"""The allowlist of practice incidents faultctl can inject. Anything not listed here is rejected.

To add an incident, add one Incident(...) line to CATALOGUE.
  mechanism "flag":      target is the flag key; variants are checked against the live flag UI.
  mechanism "container": target is a container name; it must carry the compose project label.
inject_variant is what `inject` applies when --variant is not given; rest_variant is what
`reset` puts the flag back to. Containers have neither.
"""
from dataclasses import dataclass

COMPOSE_PROJECT = "opentelemetry-demo"
DEFAULT_BASE_URL = "http://localhost:8080"

FLAG = "flag"
CONTAINER = "container"


@dataclass(frozen=True)
class Incident:
    id: str
    mechanism: str
    target: str
    inject_variant: str | None = None
    rest_variant: str | None = None


CATALOGUE: dict[str, Incident] = {i.id: i for i in [
    Incident("cache-unavailable", CONTAINER, "valkey-cart"),
    Incident("database-unavailable", CONTAINER, "astronomy-db"),
    Incident("currency-down", CONTAINER, "currency"),
    Incident("payment-failure", FLAG, "paymentFailure", "50%", "off"),
    Incident("cart-failure", FLAG, "cartFailure", "50%", "off"),
    Incident("ad-failure", FLAG, "adFailure", "on", "off"),
    Incident("product-catalog-failure", FLAG, "productCatalogFailure", "on", "off"),
    Incident("product-catalog-lock-contention", FLAG, "productCatalogLockContention", "on", "off"),
    Incident("ad-high-cpu", FLAG, "adHighCpu", "on", "off"),
]}

# The only containers faultctl may ever stop or start, derived from the catalogue.
ALLOWED_CONTAINERS = frozenset(i.target for i in CATALOGUE.values() if i.mechanism == CONTAINER)
