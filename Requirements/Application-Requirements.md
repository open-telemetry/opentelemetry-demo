# Application Requirements

The following requirements were decided upon to define what OpenTelemetry (OTel)
signals the application will produce & when support for future SDKs should be
added:

1. Every supported language that has a GA Traces or Metrics SDK must have at
   least 1 service example.

    * Mobile support (Swift) is not an initial priority and not included in the
      above requirement.

2. Application processes must be language independent.

    * gRPC is preferred where available and HTTP is to be used where it is not.

3. Services should be architected to be modular components that can be switched out.

    * Individual services can and should be encouraged to have multiple language
      options available.

4. The architecture must allow for the possible integration of platform generic
   components like a database, queue, or blob storage.

    * There is no requirement for a particular component type - at least 1 generic
      component should be present in general.

5. A load generator must be provided to simulate user load against the demo.
