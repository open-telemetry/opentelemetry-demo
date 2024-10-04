using Grpc.Core;
using Grpc.Core.Interceptors;
using OpenTelemetry.Trace;

public class ServiceNameInterceptor : Interceptor
{
    private static readonly string attributeNetPeerName = "net.peer.name";
    public override async Task<TResponse> UnaryServerHandler<TRequest, TResponse>(
        TRequest request,
        ServerCallContext context,
        UnaryServerMethod<TRequest, TResponse> continuation)
    {
        var clientServiceName = context.RequestHeaders?.GetValue("X-Service-Name");
        var span = Tracer.CurrentSpan;

        if (!string.IsNullOrEmpty(clientServiceName))
        {
            span.SetAttribute(attributeNetPeerName, clientServiceName);
        }

        return await continuation(request, context);
    }
}
