package org.daocloud.springcloud.adservice.controller;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.web.embedded.netty.NettyReactiveWebServerFactory;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpStatus;
import org.springframework.http.server.reactive.HttpHandler;
import reactor.core.publisher.Mono;

import javax.annotation.PostConstruct;
import javax.annotation.Resource;
import java.net.URI;
import java.net.URISyntaxException;

@Configuration
public class HttpToHttpsConfig {

    @Value("${http.port}")
    private int httpPort;

    @Value("${server.port}")
    private int httpsPort;

    @Value("${http.redirect}")
    private boolean httpToHttps;



    private final HttpHandler httpHandler;

    public HttpToHttpsConfig(HttpHandler httpHandler) {
        this.httpHandler = httpHandler;
    }


    @PostConstruct
    //@Bean
    public void startRedirectServer() {
        NettyReactiveWebServerFactory factory = new NettyReactiveWebServerFactory(httpPort);
         factory.getWebServer(
                (request, response) -> {
                    URI uri = request.getURI();
                    URI httpsUri;
                    try {
                        if (isNeedRedirect(uri.getPath())) {
                            httpsUri = new URI("https",
                                    uri.getUserInfo(),
                                    uri.getHost(),
                                    httpsPort,
                                    uri.getPath(),
                                    uri.getQuery(),
                                    uri.getFragment());
                            response.setStatusCode(HttpStatus.MOVED_PERMANENTLY);
                            response.getHeaders().setLocation(httpsUri);
                            return response.setComplete();
                        } else {
                            return httpHandler.handle(request, response);
                        }

                    } catch (URISyntaxException e) {
                        return Mono.error(e);
                    }
                }
        ).start();
    }

    private boolean isNeedRedirect(String path) {
        return !path.startsWith("/actuator") && httpToHttps;
    }
}