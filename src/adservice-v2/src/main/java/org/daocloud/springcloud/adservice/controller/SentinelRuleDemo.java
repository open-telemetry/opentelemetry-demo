package org.daocloud.springcloud.adservice.controller;

import com.alibaba.csp.sentinel.Entry;
import com.alibaba.csp.sentinel.EntryType;
import com.alibaba.csp.sentinel.SphU;
import com.alibaba.csp.sentinel.slots.block.BlockException;
import com.alibaba.csp.sentinel.slots.block.RuleConstant;
import com.alibaba.csp.sentinel.slots.block.authority.AuthorityRule;
import com.alibaba.csp.sentinel.slots.block.authority.AuthorityRuleManager;
import com.alibaba.csp.sentinel.slots.block.flow.param.ParamFlowItem;
import com.alibaba.csp.sentinel.slots.block.flow.param.ParamFlowRule;
import com.alibaba.csp.sentinel.slots.block.flow.param.ParamFlowRuleManager;
import org.daocloud.springcloud.adservice.service.SentinelRuleDemoService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import reactor.core.publisher.Mono;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

@RestController
@RequestMapping(value = "/sentinel")
public class SentinelRuleDemo {
    @Autowired
    private SentinelRuleDemoService sentinelRuleDemoService;

    private static Boolean flag = false;

    @GetMapping("/read")
    public String testA() {
        sentinelRuleDemoService.common();
        return "read";
    }

    @GetMapping("/write")
    public Mono<String> testB() {
        sentinelRuleDemoService.common();
        return Mono.just("write");
    }

    @GetMapping("/degrade")
    public Mono<String> degrade(@RequestParam(required = false, defaultValue = "0") String on) throws InterruptedException {
        if (!flag) {
            Thread.sleep(1200);
        }
        return Mono.just("degrade test");
    }

    @GetMapping("/degrade/exp")
    public Mono<String> exp(@RequestParam(required = false, defaultValue = "0") String on) throws RuntimeException {
        if (!flag) {
            throw new RuntimeException("degrade exp exp");
        }
        return Mono.just("degrade exception test");
    }

    @GetMapping("/degrade/switch")
    public Mono<String> degrade() {
        flag = !flag;
        return Mono.just("degrade switch");
    }

    @GetMapping("/hot")
    public Mono<String> testHot(
            @RequestParam(required = false) String a,
            @RequestParam(required = false) String b
    ) {
        Entry entry = null;
        try {
            entry = SphU.entry("hot-test", EntryType.IN, 1, a, b);
            // Your logic here.
            return Mono.just("hot test passed");
        } catch (BlockException ex) {
            return Mono.just("hot test blocked");
        } finally {
            if (entry != null) {
                entry.exit(1, a, b);
            }
        }
    }

    private static void initParamFlowRules() {
        ParamFlowRule rule = new ParamFlowRule("hot-test")
                .setParamIdx(0)
                .setGrade(RuleConstant.FLOW_GRADE_QPS)
                .setCount(2);

        ParamFlowItem item = new ParamFlowItem().setObject(String.valueOf("test"))
                .setClassType(String.class.getName())
                .setCount(5);
        rule.setParamFlowItemList(Collections.singletonList(item));
        ParamFlowRuleManager.loadRules(Collections.singletonList(rule));
    }

    @GetMapping("/auth")
    public Mono<String> testSentinelAPI(
            @RequestParam(required = false) String a) {
        initAuthorityRule();
        return Mono.just("auth test");
    }

    private void initAuthorityRule() {
        List<AuthorityRule> rules = new ArrayList<>();
        AuthorityRule rule = new AuthorityRule();
        rule.setResource("/sentinel/auth");
        rule.setLimitApp("daocloud");
        rule.setStrategy(RuleConstant.AUTHORITY_WHITE);
        rules.add(rule);
        AuthorityRuleManager.loadRules(rules);
    }

    @GetMapping("/cluster-flow")
    public String clusterFlow() {
        return sentinelRuleDemoService.clusterFlow();
    }
}
