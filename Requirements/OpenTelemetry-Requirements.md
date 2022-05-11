# OpenTelemetry Requirements

The following requirements were decided upon to define what OpenTelemetry (OTel)
signals the application will produce & when support for future SDKs should be
added:

1. The demo must produce OTel logs, traces, & metrics out of the box for
   languages that have a GA SDK.

2. Languages that have a Beta SDK available may be included but are not required
   like GA SDKs.

3. Native OTel metrics should be produced where possible.

4. Both manual instrumentation and instrumentation libraries
   (auto-instrumentation) should be demonstrated in each language.

5. All data should be exported to the Collector first.

6. The Collector must be configurable to allow for a variety of consumption
   experiences but default tools must be selected for each signal.

7. The demo application architecture using the Collector should be designed to
   be a best practices reference architecture.
