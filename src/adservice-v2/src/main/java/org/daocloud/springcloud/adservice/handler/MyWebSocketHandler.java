package org.daocloud.springcloud.adservice.handler;

import org.springframework.web.reactive.socket.WebSocketHandler;
import org.springframework.web.reactive.socket.WebSocketSession;
import reactor.core.publisher.Mono;

/**
 * @author yangyang
 * @date 2022/10/26 下午3:16
 */
public class MyWebSocketHandler implements WebSocketHandler {
    @Override
    public Mono<Void> handle(WebSocketSession session) {
        return session.send(
                session.receive().map(msg -> session.textMessage("server send:"+ msg.getPayloadAsText()))
        );
    }
}
