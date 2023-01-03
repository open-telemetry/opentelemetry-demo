package org.daocloud.springcloud.adservice.controller;

import org.daocloud.springcloud.adservice.handler.MyWebSocketHandler;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.reactive.HandlerMapping;
import org.springframework.web.reactive.handler.SimpleUrlHandlerMapping;
import org.springframework.web.reactive.socket.WebSocketHandler;
import org.springframework.web.reactive.socket.server.support.WebSocketHandlerAdapter;

import java.util.HashMap;
import java.util.Map;

/**
 * @author yangyang
 * @date 2022/10/26 下午3:20
 */
@Configuration
public class WebsocketConfig {
    @Bean
    public MyWebSocketHandler getMyWebsocketHandler() {
        return new MyWebSocketHandler();
    }
    @Bean
    public HandlerMapping handlerMapping() {
        // 对相应的URL进行添加处理器
        Map<String, WebSocketHandler> map = new HashMap<>();
        map.put("/websocket", getMyWebsocketHandler());

        SimpleUrlHandlerMapping mapping = new SimpleUrlHandlerMapping();
        mapping.setUrlMap(map);
        mapping.setOrder(-1);
        return mapping;
    }

    @Bean
    public WebSocketHandlerAdapter handlerAdapter() {
        return new WebSocketHandlerAdapter();
    }
}
