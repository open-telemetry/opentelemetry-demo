graph TD
    subgraph Data_Plane[Telemetry Flow]
        Services[Microservices] -->|OTLP Traces / Metrics / Logs| Collector[otel-collector]
        Collector -->|Metrics| Prom[Prometheus]
        Collector -->|Logs| OS[OpenSearch]
        Collector -->|Traces| Jaeger[Jaeger]
    end

    subgraph RealTime_Triggers[Push / Watchdog Layer]
        Prom -->|Alert Webhook| AgentWebhook[FastAPI /alerts endpoint]
        OS -->|Monitor Webhook| AgentWebhook
        Collector -.->|Connector / Filtered Error Stream| AgentWebhook
    end

    subgraph Agentic_Layer[src/agent & src/mcp]
        AgentWebhook -->|Wakes up agent with incident context| Agent[src/agent: LangGraph ReAct]
        Agent <-->|Pulls targeted telemetry via MCP| MCP[src/mcp: FastMCP Observability Server]
    end

    subgraph MCP_Tools[Observability Tools]
        MCP -->|PromQL| Prom
        MCP -->|PPL / Query| OS
        MCP -->|v3 Traces API| Jaeger
        MCP -->|/feature/api/read| Flagd[flagd: Feature Flags]
    end
