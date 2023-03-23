package org.daocloud.springcloud.adservice.service;

import com.alibaba.csp.sentinel.annotation.SentinelResource;
import org.springframework.stereotype.Service;

@Service
public class SentinelRuleDemoService {
    @SentinelResource("common")
    public String common() {
        return "common";
    }
}
