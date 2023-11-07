![](nginx.png)

# Nginx Integrations 

## What it Nginx ?
Nginx is a popular open-source web server software used by millions of websites worldwide. It was developed to address the limitations of Apache, which is another popular web server software. Nginx is known for its high performance, scalability, and reliability, and is widely used as a reverse proxy server, load balancer, and HTTP cache.

One of the primary advantages of Nginx is its ability to handle large numbers of concurrent connections and requests. It uses an event-driven architecture that allows it to handle multiple connections with minimal resources, making it an ideal choice for high-traffic websites. In addition, Nginx can also serve static content very efficiently, which further improves its performance.

Another important feature of Nginx is its ability to act as a reverse proxy server. This means that it can sit in front of web servers and route incoming requests to the appropriate server based on various criteria, such as the URL or the type of request. Reverse proxying can help improve website performance and security by caching static content, load balancing incoming traffic, and providing an additional layer of protection against attacks.

Nginx is also widely used as a load balancer. In this role, it distributes incoming traffic across multiple web servers to improve performance and ensure high availability. Nginx can balance traffic using a variety of algorithms, such as round-robin or least connections, and can also perform health checks to ensure that requests are only sent to healthy servers.

Finally, Nginx is also an effective HTTP cache. By caching frequently accessed content, Nginx can reduce the load on backend servers and improve website performance. Nginx can cache content based on a variety of criteria, such as the URL, response headers, or response body.

## What is An Nginx Integration ?
As described in the [documentation](../../README.md) Nginx integrations is a bundle of resources, assets and documentations. 

An Integration may have multiple ways of ingesting Observability signals, for example nginx logs may arrive via fluent-bit agent or OTEL-logs collector...

## Which are the Nginx Observability providers ?
Observability Providers are agents which can collect nginx logs, metrics and traces information, convert them to `sso` observability schema and send them to opensearch observability data-streams.

### Fluent-Bit
Fluent-bit has a dedicated input plugin for Nginx called `in_tail` which can be used to tail the Nginx access logs and send them to a destination of your choice.
The in_tail plugin reads log files line by line and sends them to Fluent-bit engine to be processed.

See additional details [here](fluet-bit/README.md).

### Dashboards
The following dashboard preview shows the summarized information collected from the access log index

![nginx-dashboard-preview.png](preview%2Fnginx-dashboard-preview.png)