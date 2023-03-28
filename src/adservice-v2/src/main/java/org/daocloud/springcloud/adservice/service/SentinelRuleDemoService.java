package org.daocloud.springcloud.adservice.service;

import com.alibaba.csp.sentinel.annotation.SentinelResource;
import com.alibaba.csp.sentinel.slots.block.BlockException;
import org.springframework.stereotype.Service;

@Service
public class SentinelRuleDemoService {
    @SentinelResource("common")
    public String common() {
        return "common";
    }

    @SentinelResource(value = "cluster-resource", blockHandler = "clusterFlowBlockHandler")
    public String clusterFlow() {
        return "cluster flow test";
    }

    public String clusterFlowBlockHandler(BlockException ex) {
        ex.printStackTrace();
        return String.format("Oops, <%s> blocked by Sentinel", "cluster flow test");
    }
}
