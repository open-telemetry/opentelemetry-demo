package org.daocloud.springcloud.adservice.init;

import com.alibaba.csp.sentinel.cluster.ClusterStateManager;
import com.alibaba.csp.sentinel.cluster.client.config.ClusterClientAssignConfig;
import com.alibaba.csp.sentinel.cluster.client.config.ClusterClientConfig;
import com.alibaba.csp.sentinel.cluster.client.config.ClusterClientConfigManager;
import com.alibaba.csp.sentinel.datasource.ReadableDataSource;
import com.alibaba.csp.sentinel.datasource.nacos.NacosDataSource;
import com.alibaba.csp.sentinel.init.InitFunc;
import com.alibaba.csp.sentinel.slots.block.flow.FlowRule;
import com.alibaba.csp.sentinel.slots.block.flow.FlowRuleManager;
import com.alibaba.csp.sentinel.slots.block.flow.param.ParamFlowRule;
import com.alibaba.csp.sentinel.slots.block.flow.param.ParamFlowRuleManager;
import com.alibaba.csp.sentinel.transport.config.TransportConfig;
import com.alibaba.csp.sentinel.util.HostNameUtil;
import com.alibaba.csp.sentinel.util.StringUtil;
import com.alibaba.fastjson.JSON;
import com.alibaba.fastjson.TypeReference;
import com.alibaba.nacos.api.PropertyKeyConst;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;
import org.daocloud.springcloud.adservice.dto.ClusterGroupDto;
import org.daocloud.springcloud.adservice.service.AdServiceGrpcService;

import java.util.List;
import java.util.Objects;
import java.util.Optional;
import java.util.Properties;

import static org.daocloud.springcloud.adservice.consts.SentinelConst.*;

public class SentinelClusterClientInitFunc implements InitFunc {
    private static final Logger logger = LogManager.getLogger(AdServiceGrpcService.class);

    private String nacosAddress;
    private Properties properties = new Properties();
    private String groupId;
    private String dataId;

    @Override
    public void init() throws Exception {
        getNacosAddr();

        parseAppName();

        initDynamicRuleProperty();

        initClientConfigProperty();

        initClientServerAssignProperty();

        initStateProperty();
    }

    private void getNacosAddr() {
        nacosAddress = System.getProperty("spring.cloud.nacos.config.server-addr");
        if (StringUtil.isBlank(nacosAddress)){
            throw new RuntimeException("nacos address start param must be set");
        }
        logger.info("nacos address: %s\n", nacosAddress);
    }

    private void parseAppName() {
        String[] apps = APPNAME.split("@@");
        logger.info("app name: %s\n", APPNAME);
        if (apps.length != 3) {
            throw new RuntimeException("app name format must be set like this: {{namespaceId}}@@{{groupName}}@@{{appName}}");
        } else if (StringUtil.isBlank(apps[1])){
            throw new RuntimeException("group name cannot be empty");
        }
        properties.put(PropertyKeyConst.NAMESPACE, apps[0]);
        properties.put(PropertyKeyConst.SERVER_ADDR, nacosAddress);
        properties.put(PropertyKeyConst.USERNAME, DEFAULT_NACOS_USERNAME);
        properties.put(PropertyKeyConst.PASSWORD, DEFAULT_NACOS_PASSWORD);
        groupId = apps[1];
        dataId = apps[2];
    }

    private void initDynamicRuleProperty() {
        ReadableDataSource<String, List<FlowRule>> ruleSource = new NacosDataSource<>(properties, groupId,
            dataId + FLOW_POSTFIX, source -> JSON.parseObject(source, new TypeReference<List<FlowRule>>() {}));
        FlowRuleManager.register2Property(ruleSource.getProperty());

        ReadableDataSource<String, List<ParamFlowRule>> paramRuleSource = new NacosDataSource<>(nacosAddress, groupId,
                dataId +  PARAM_FLOW_POSTFIX, source -> JSON.parseObject(source, new TypeReference<List<ParamFlowRule>>() {}));
        ParamFlowRuleManager.register2Property(paramRuleSource.getProperty());
    }

    private void initClientConfigProperty() {
        ReadableDataSource<String, ClusterClientConfig> clientConfigDs = new NacosDataSource<>(nacosAddress, groupId,
                dataId + CLUSTER_CLIENT_POSTFIX, source -> JSON.parseObject(source, new TypeReference<ClusterClientConfig>() {}));
        ClusterClientConfigManager.registerClientConfigProperty(clientConfigDs.getProperty());
    }

    private void initClientServerAssignProperty() {
//        Cluster map format:
//        [
//            {
//                "machineId": "10.64.0.81@8720",
//                 "ip": "10.64.0.81",
//                 "port": 18730,
//                 "clientSet": ["10.64.0.81@8721", "10.64.0.81@8722"]
//            }
//        ]
        ReadableDataSource<String, ClusterClientAssignConfig> clientAssignDs = new NacosDataSource<>(nacosAddress, groupId,
                dataId +  CLUSTER_MAP_POSTFIX, source -> {
            List<ClusterGroupDto> groupList = JSON.parseObject(source, new TypeReference<List<ClusterGroupDto>>() {});
            return Optional.ofNullable(groupList)
                .flatMap(this::extractClientAssignment)
                .orElse(null);
        });
        ClusterClientConfigManager.registerServerAssignProperty(clientAssignDs.getProperty());
    }

    private void initStateProperty() {
        ReadableDataSource<String, Integer> clusterModeDs = new NacosDataSource<>(nacosAddress, groupId,
                dataId + CLUSTER_MAP_POSTFIX, source -> {
            List<ClusterGroupDto> groupList = JSON.parseObject(source, new TypeReference<List<ClusterGroupDto>>() {});
            return Optional.ofNullable(groupList)
                .map(this::extractMode)
                .orElse(ClusterStateManager.CLUSTER_NOT_STARTED);
        });
        ClusterStateManager.registerProperty(clusterModeDs.getProperty());
    }

    private int extractMode(List<ClusterGroupDto> groupList) {
        if (groupList.stream().anyMatch(this::machineEqual)) {
            return ClusterStateManager.CLUSTER_SERVER;
        }

        boolean canBeClient = groupList.stream()
            .flatMap(e -> e.getClientSet().stream())
            .filter(Objects::nonNull)
            .anyMatch(e -> e.equals(getCurrentMachineId()));
        return canBeClient ? ClusterStateManager.CLUSTER_CLIENT : ClusterStateManager.CLUSTER_NOT_STARTED;
    }

    private Optional<ClusterClientAssignConfig> extractClientAssignment(List<ClusterGroupDto> groupList) {
        if (groupList.stream().anyMatch(this::machineEqual)) {
            return Optional.empty();
        }
        for (ClusterGroupDto group : groupList) {
            if (group.getClientSet().contains(getCurrentMachineId())) {
                String ip = group.getIp();
                Integer port = group.getPort();
                return Optional.of(new ClusterClientAssignConfig(ip, port));
            }
        }
        return Optional.empty();
    }

    private boolean machineEqual(ClusterGroupDto group) {
        return getCurrentMachineId().equals(group.getMachineId());
    }

    private String getCurrentMachineId() {
        return HostNameUtil.getIp() + SEPARATOR + TransportConfig.getRuntimePort();
    }

    private static final String SEPARATOR = "@";
}