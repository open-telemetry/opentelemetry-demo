package org.daocloud.springcloud.adservice.config;

import com.alibaba.csp.sentinel.adapter.spring.webflux.callback.WebFluxCallbackManager;
import org.springframework.context.ApplicationListener;
import org.springframework.context.event.ContextRefreshedEvent;
import org.springframework.stereotype.Component;
import org.springframework.util.MultiValueMap;

import java.util.List;


@Component
public class SentinelWebFluxConfig implements ApplicationListener<ContextRefreshedEvent> {
    @Override
    public void onApplicationEvent(ContextRefreshedEvent event) {
        WebFluxCallbackManager.setRequestOriginParser(exchange -> {
            MultiValueMap<String, String> queryParams = exchange.getRequest().getQueryParams();

            if (queryParams.isEmpty()){
                return "";
            }
            List<String> a = queryParams.get("a");
            if (a.isEmpty()){
                return "";
            }
            String origin = a.get(0);
            return origin != null ? origin : "";
        });
    }
}
