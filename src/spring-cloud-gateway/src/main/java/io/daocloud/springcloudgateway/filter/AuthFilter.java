package io.daocloud.springcloudgateway.filter;


import io.daocloud.springcloudgateway.config.AuthProperties;
import lombok.extern.slf4j.Slf4j;
import org.springframework.cloud.gateway.filter.GatewayFilterChain;
import org.springframework.cloud.gateway.filter.GlobalFilter;
import org.springframework.core.Ordered;
import org.springframework.core.io.buffer.DataBuffer;
import org.springframework.http.HttpStatus;
import org.springframework.http.server.reactive.ServerHttpResponse;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ServerWebExchange;
import reactor.core.publisher.Mono;

import java.nio.charset.StandardCharsets;

@Slf4j
@Component
public class AuthFilter implements GlobalFilter, Ordered {

    private final AuthProperties authProperties;

    public AuthFilter(AuthProperties authProperties) {
        this.authProperties = authProperties;
    }

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, GatewayFilterChain chain) {

        if (authProperties.isEnabled()) {
            String headerKey = authProperties.getKey();
            String headerValue = authProperties.getValue();

            String token = exchange.getRequest().getHeaders().getFirst(headerKey);

            if (!headerValue.equals(token)) {

                log.error("Authentication error: header auth key is {} , value is : {}", headerKey, exchange.getRequest().getHeaders().getFirst(headerKey));

                ServerHttpResponse response = exchange.getResponse();
                response.setStatusCode(HttpStatus.UNAUTHORIZED);
                String data = "{\"code\":\"403\",\"message\": \"Authentication failed\"}";
                DataBuffer buffer = response.bufferFactory().wrap(data.getBytes(StandardCharsets.UTF_8));
                return response.writeWith(Mono.just(buffer));
            }
        }
        return chain.filter(exchange);
    }

    @Override
    public int getOrder() {
        return 0;
    }

}
