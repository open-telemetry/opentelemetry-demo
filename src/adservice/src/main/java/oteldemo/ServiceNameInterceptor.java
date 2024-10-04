package oteldemo;

import io.grpc.*;
import io.opentelemetry.api.trace.Span;
import io.opentelemetry.api.trace.StatusCode;
import io.opentelemetry.context.Scope;

public class ServiceNameInterceptor implements ServerInterceptor {

    private static final String ATTRIBUTE_NET_PEER_NAME = "net.peer.name";

    private static final Metadata.Key<String> X_SERVICE_NAME_KEY = Metadata.Key.of("X-Service-Name",
            Metadata.ASCII_STRING_MARSHALLER);

    @Override
    public <R, S> ServerCall.Listener<R> interceptCall(ServerCall<R, S> call,
            Metadata headers,
            ServerCallHandler<R, S> next) {
        String clientServiceName = headers.get(X_SERVICE_NAME_KEY);
        Span span = Span.current();
        if (clientServiceName != null && !clientServiceName.isEmpty()) {
            span.setAttribute(ATTRIBUTE_NET_PEER_NAME, clientServiceName);
        }

        try (Scope scope = span.makeCurrent()) {
            return next.startCall(call, headers);
        } catch (Exception e) {
            span.setStatus(StatusCode.ERROR, "Exception while processing call");
            throw e;
        } finally {
            span.end();
        }
    }
}
