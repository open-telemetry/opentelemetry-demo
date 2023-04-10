package org.daocloud.springcloud.adservice.consts;

import com.alibaba.csp.sentinel.util.AppNameUtil;

public final class SentinelConst {
    public static final String APPNAME = AppNameUtil.getAppName();
    
    public static final String FLOW_POSTFIX = "-flow-rules";
    public static final String PARAM_FLOW_POSTFIX = "-param-rules";
    public static final String CLUSTER_CLIENT_POSTFIX = "-cluster-client-config";
    public static final String CLUSTER_MAP_POSTFIX = "-cluster-map";
    
    
    public static final String DEFAULT_NACOS_USERNAME = "skoala";
    public static final String DEFAULT_NACOS_PASSWORD = "98985ba0-da90-41f6-b6dc-96f2ec49d973";
    public static final String DEFAULT_NACOS_NAMESPACE = "";
    public static final String DEFAULT_NACOS_GROUP = "SENTINEL_GROUP";
}
