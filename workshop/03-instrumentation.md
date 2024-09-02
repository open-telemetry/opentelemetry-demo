# Exercise 3: Instrumentation with JAVA

In this section, we will instrument a simple Java application with OpenTelemetry. We will use the OpenTelemetry Java SDK to add tracing to the application.


## Getting started 

In this assignment we are going to instrument ad service with the OpenTelemetry Java agent. You can read about the documentation [here](https://github.com/open-telemetry/opentelemetry-java-instrumentation/)

### Assignment 1 - Enable OpenTelemetry Java agent in the Adservice
First assignment is to enable Opentelemetry java agent for the adservice. You can read about how it's done here  : 

https://opentelemetry.io/docs/zero-code/java/agent/getting-started/

```bash
ADD --chmod=644 https://github.com/open-telemetry/opentelemetry-java-instrumentation/releases/download/v$version/opentelemetry-javaagent.jar /usr/src/app/opentelemetry-javaagent.jar
ENV JAVA_TOOL_OPTIONS=-javaagent:/usr/src/app/opentelemetry-javaagent.jar
```
Now you should be able to get standard metrics and traces from the adservice.  

### Assignment 2 -  Add attributes and events to auto instrumented spans
We can use the span context to hook into so we can enrich traces with more information. 

Assignment : 

In get getAds method hook into the span context and add the following attributes to the span  "app.ads.contextKeys", "app.ads.contextKeys.count", "app.ads.count", "app.ads.ad_request_type", "app.ads.ad_response_type" . This will give us insight into what advertisement that has been shown.

You can verify that the attributes are set by looking at the traces in Grafana with Tempo as the datasource.

Next we want to refine the traces from the span with events and status codes if getAds method fails. So inside the catch block add and error event with attributeKey thats should be called : "exception.message" that adds the exception to the span. We should also as part of this mark the span as failed.

### Assignment.3 - Create new spans

Sometimes it's wise to creaste a new span and add it to the tracing context. Add a new span for getRandomAds() method in the context of the parent span.

### Assignment.4 - Add Metrics
Similar to creating spans, the first step in creating metrics is to initialize a Meter instance. 

Assignment : 
Create metrics that counts requests by request and response type

Also make an adRequestsCounter with the span metrics called : "app.ads.count", "app.ads.ad_request_type", "app.ads.ad_response_type"


### Assignment.5 - Add session_id as Baggage

Baggage in OpenTelemetry is a mechanism for propagating context across process boundaries in distributed systems. It allows you to attach arbitrary key-value pairs to a request 
and have them travel along with that request as it moves through different services or components. Unlike spans, which are primarily used for tracing and measuring the execution of operations, 
baggage is intended to carry additional contextual information that might be relevant for various parts of your system.

Assignment :
You will be modifying a service to extract a session.id from the current context's baggage. If the session.id is present, 
it should be used to enrich the current span and to update a custom context object (evaluationContext).
If no baggage is found, you will handle this case by logging an appropriate message.


## OpenTelemetry with Spring boot and micrometer

Spring boot 3 has excellent support for OpenTelemetry via the micrometer. Spring Boot 3 comes with full support for OpenTelemetry.

## Instrument Currency-service 

Currency-service has been reimplemented in Spring Boot 3 from C++. To enable that we have to comment out the image from currency-service in the docker-compose file.

´´´












