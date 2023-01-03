package org.daocloud.springcloud.adservice.Interceptor;
import com.alibaba.csp.sentinel.adapter.grpc.SentinelGrpcServerInterceptor;
import io.grpc.ServerInterceptor;
import net.devh.boot.grpc.server.interceptor.GrpcGlobalServerInterceptor;
import org.springframework.context.annotation.Configuration;

@Configuration
public class GlobalInterceptorConfiguration {
    @GrpcGlobalServerInterceptor
    ServerInterceptor SentinelInterceptor() {
        return new SentinelGrpcServerInterceptor();
    }

    @GrpcGlobalServerInterceptor
    ServerInterceptor MeterInterceptor() {
        return new MeterInterceptor();
    }
}