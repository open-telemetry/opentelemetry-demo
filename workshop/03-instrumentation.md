# Exercise 3: Instrumentation with JAVA

In this section, we will instrument a simple Java application with OpenTelemetry. We will use the OpenTelemetry Java SDK to add tracing to the application.


## Getting started 

In this assignment we are going to instrument ad service with the OpenTelemetry Java agent. You can read about the documentation [here](https://github.com/open-telemetry/opentelemetry-java-instrumentation/)

### Assignment 1 - Enable OpenTelemetry Java agent in the Adservice
First assignment is to enable Opentelemetry java agent for the adservice. You can read about how it's done here  : https://opentelemetry.io/docs/zero-code/java/agent/getting-started/

We should configure the agent as well with the current environment variables. 

```bash
OTEL_EXPORTER_OTLP_ENDPOINT // endpoint for the OTEL collector
OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE // Configure the exporter’s aggregation temporality option (see above) on the basis of instrument kind. 
OTEL_RESOURCE_ATTRIBUTES // default attribute config is needed
OTEL_LOGS_EXPORTER // format we are sending logs in 
OTEL_SERVICE_NAME // name of the service
JAVA_TOOL_OPTIONS  // url to the java agent that we are injecting
```
Now you should be able to get standard metrics and traces from the adservice.  Open grafana and navigate to  Explore and select Tempo as a datasource and click on the service graph. Adservice should now be available there.

TIPS :  If you get stuck you can look at the dockerfile and docker-compose file for other services

### Assignment 2 - Add attributes and events to auto instrumented spans
We can use the span context to hook into so we can enrich traces with more information.  Read about how it's done : https://opentelemetry.io/docs/languages/java/instrumentation/

__Assignment  :__

In get `getAds` method hook into the span context and add the following attributes to the span `app.ads.contextKeys`, `app.ads.contextKeys.count`, `app.ads.count`, `app.ads.ad_request_type`, `app.ads.ad_response_type` .  
Data that you are adding to the attributes are defined in the demo.proto file. This will give us insight into what advertisement that has been shown.

You can rebuild the adservice with the following command : 

```bash
docker-compose down adservice
docker-compose up adservice --build -d
```
You can verify that the attributes are set by looking at the traces in Grafana with Tempo as the datasource.

#### Span Events
A Span Event can be thought of as a structured log message (or annotation) on a Span, typically used to denote a meaningful, singular point in time during the Span’s duration.

For example, consider two scenarios in a web browser:
* Tracking a page load
* Denoting when a page becomes interactive
A Span is best used to the first scenario because it’s an operation with a start and an end.

A Span Event is best used to track the second scenario because it represents a meaningful, singular point in time.

#### When to use span events versus span attributes
Since span events also contain attributes, the question of when to use events instead of attributes might not always have an obvious answer. To inform your decision, consider whether a specific timestamp is meaningful.

For example, when you’re tracking an operation with a span and the operation completes, you might want to add data from the operation to your telemetry.
* If the timestamp in which the operation completes is meaningful or relevant, attach the data to a span event.
* If the timestamp isn’t meaningful, attach the data as span attributes.


__Assignment  :__
Next we want to refine the traces from the span with events and status codes if getAds method fails. Inside the `try/catch` block add and error event with attributeKey thats should be called : `exception.message` that adds the exception to the span. We should also as part of this mark the span as failed.

### Assignment.3 - Create new spans

#### Spans
A span represents a unit of work or operation. Spans are the building blocks of Traces. In OpenTelemetry, they include the following information:

* Name
* Parent span ID (empty for root spans)
* Start and End Timestamps
* Span Context
* Attributes
* Span Events
* Span Links
* Span Status

Read more here : https://opentelemetry.io/docs/concepts/signals/traces/#spans

__Assignment  :__
In the Adservice we would like to add a span for just `getRandomAds()` method and add it to the tracing context.

### Assignment.4 - Add Metrics

A metric is a measurement of a service captured at runtime. The moment of capturing a measurements is known as a metric event, 
which consists not only of the measurement itself, but also the time at which it was captured and associated metadata.
Application and request metrics are important indicators of availability and performance. 
Custom metrics can provide insights into how availability indicators impact user experience or the business. 
Collected data can be used to alert of an outage or trigger scheduling decisions to scale up a deployment automatically upon high demand.

Read more about  metrics here :  https://opentelemetry.io/docs/concepts/signals/metrics/

Assignment : 
Create metrics that counts requests by request and response type

Also make an adRequestsCounter with the span metrics called : `app.ads.count`, `app.ads.ad_request_type`, `app.ads.ad_response_type`


### Assignment.5 - Add session_id as Baggage

Baggage in OpenTelemetry is a mechanism for propagating context across process boundaries in distributed systems. It allows you to attach arbitrary key-value pairs to a request 
and have them travel along with that request as it moves through different services or components. Unlike spans, which are primarily used for tracing and measuring the execution of operations, 
baggage is intended to carry additional contextual information that might be relevant for various parts of your system.

__Assignment  :__
You will be modifying a service to extract a session.id from the current context's baggage. If the session.id is present, 
it should be used to enrich the current span and to update a custom context object (evaluationContext).
If no baggage is found, you will handle this case by logging an appropriate message.

### Assignment.6 - Add logs
OpenTelemetry does not define a bespoke API or SDK to create logs. Instead, OpenTelemetry logs are the existing logs you already have from a logging framework or infrastructure component. OpenTelemetry SDKs and autoinstrumentation utilize several components to automatically correlate logs with traces.

OpenTelemetry’s support for logs is designed to be fully compatible with what you already have, providing capabilities to wrap those logs with additional context and a common toolkit to parse and manipulate logs into a common format across many different sources.

In our instance we are using Log4j that automaticly sends logs to the OpenTelemetry collector.

Read more here :  https://opentelemetry.io/docs/concepts/signals/logs/














