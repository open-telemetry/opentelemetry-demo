# Load Generator

The load generator creates simulated traffic to the demo.

## Accessing the Load Generator

You can access the web interface to Locust at `http://localhost:8080/loadgen/`.

## Modifying the Load Generator

Please see the [Locust
documentation](https://docs.locust.io/en/2.16.0/writing-a-locustfile.html) to
learn more about modifying the locustfile.

## Configuration

* `LOCUST_BROWSER_TRAFFIC_ENABLED`: when `true`, spawns `WebsiteBrowserUser`
  virtual users that drive a real headless Chromium session against the
  frontend. Each one keeps its browser process alive for its whole lifetime,
  so raising the ratio of these users increases memory usage.
* `LOCUST_HTTP_USER_WEIGHT` / `LOCUST_BROWSER_USER_WEIGHT`: relative [Locust
  weights](https://docs.locust.io/en/stable/writing-a-locustfile.html#weight-of-tasks)
  for `WebsiteUser` (plain HTTP) vs `WebsiteBrowserUser` (real browser),
  defaulting to `9` and `1`. Raise `LOCUST_BROWSER_USER_WEIGHT` for more
  browser/frontend traffic, at the cost of more concurrent Chromium
  processes.
