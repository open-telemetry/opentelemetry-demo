{{- define "opentelemetry-collector.otelsdkotlp.traces" -}}
traces:
  processors:
    - batch:
        exporter:
          otlp:
            protocol: http/protobuf
            endpoint: {{ default .Values.internalTelemetryViaOTLP.endpoint .Values.internalTelemetryViaOTLP.traces.endpoint }}
            {{- if or .Values.internalTelemetryViaOTLP.headers .Values.internalTelemetryViaOTLP.traces.headers }}
            headers:
              {{- toYaml (default .Values.internalTelemetryViaOTLP.headers .Values.internalTelemetryViaOTLP.traces.headers) | nindent 14 }}
            {{- end }}
{{- end }}

{{- define "opentelemetry-collector.otelsdkotlp.metrics" -}}
metrics:
  readers:
    - periodic:
        exporter:
          otlp:
            protocol: http/protobuf
            endpoint: {{ default .Values.internalTelemetryViaOTLP.endpoint .Values.internalTelemetryViaOTLP.metrics.endpoint }}
            {{- if or .Values.internalTelemetryViaOTLP.headers .Values.internalTelemetryViaOTLP.metrics.headers }}
            headers:
              {{- toYaml (default .Values.internalTelemetryViaOTLP.headers .Values.internalTelemetryViaOTLP.metrics.headers) | nindent 14 }}
            {{- end }}
{{- end }}

{{- define "opentelemetry-collector.metrics.prometheus" -}}
metrics:
  readers:
    - pull:
        exporter:
          prometheus:
            host: {{ .address._0 | replace "{env!" "{env:" }}
            port: {{ .address._1 }}
            {{- if .Values.config.service.telemetry.resource }}
            with_resource_constant_labels:
              included:
              {{- range (keys .Values.config.service.telemetry.resource | sortAlpha) }}
              - {{ println . }}
              {{- end }}
            {{- end }}
{{- end }}

{{- define "opentelemetry-collector.otelsdkotlp.logs" -}}
logs:
  processors:
    - batch:
        exporter:
          otlp:
            protocol: http/protobuf
            endpoint: {{ default .Values.internalTelemetryViaOTLP.endpoint .Values.internalTelemetryViaOTLP.logs.endpoint }}
            {{- if or .Values.internalTelemetryViaOTLP.headers .Values.internalTelemetryViaOTLP.logs.headers }}
            headers:
              {{- toYaml (default .Values.internalTelemetryViaOTLP.headers .Values.internalTelemetryViaOTLP.logs.headers) | nindent 14 }}
            {{- end }}
{{- end }}

{{- define "opentelemetry-collector.baseConfig" -}}
{{- if .Values.alternateConfig }}
{{- .Values.alternateConfig | toYaml }}
{{- else}}
{{- $config := deepCopy .Values.config }}
{{- if .Values.internalTelemetryViaOTLP.traces.enabled }}
{{- $_ := set $config.service "telemetry" (mustMerge $config.service.telemetry (include "opentelemetry-collector.otelsdkotlp.traces" . | fromYaml)) }}
{{- end }}
{{- if .Values.internalTelemetryViaOTLP.metrics.enabled }}
{{- $_ := unset $config.receivers "prometheus" }}
{{- if $config.service.pipelines.metrics }}
{{- $_ := set $config.service.pipelines.metrics "receivers" (mustWithout $config.service.pipelines.metrics.receivers "prometheus") }}
{{- end }}
{{- $_ := unset $config.service.telemetry.metrics "readers" }}
{{- $_ := set $config.service "telemetry" (mustMerge $config.service.telemetry (include "opentelemetry-collector.otelsdkotlp.metrics" . | fromYaml)) }}
{{- else if .Values.config.service.telemetry.metrics.address }}
{{/* First replace env: with env! so we can split the host with the port and replace it back later */}}
{{- $address:= .Values.config.service.telemetry.metrics.address | replace "{env:" "{env!" | split ":" }}
{{- $_ := unset $config.service.telemetry.metrics "address" }}
{{- $_ := set $config.service "telemetry" (mustMerge (include "opentelemetry-collector.metrics.prometheus" (mustMerge (dict "address" $address) .) | fromYaml) $config.service.telemetry ) }}
{{- end }}
{{- if .Values.internalTelemetryViaOTLP.logs.enabled }}
{{- $_ := set $config.service "telemetry" (mustMerge $config.service.telemetry (include "opentelemetry-collector.otelsdkotlp.logs" . | fromYaml)) }}
{{- end }}
{{- $config | toYaml }}
{{- end }}
{{- end }}

{{/*
Build config file for daemonset OpenTelemetry Collector
*/}}
{{- define "opentelemetry-collector.daemonsetConfig" -}}
{{- $values := deepCopy .Values }}
{{- $data := dict "Values" $values | mustMergeOverwrite (deepCopy .) }}
{{- $config := include "opentelemetry-collector.baseConfig" $data | fromYaml }}
{{- if .Values.presets.logsCollection.enabled }}
{{- $config = (include "opentelemetry-collector.applyLogsCollectionConfig" (dict "Values" $data "config" $config) | fromYaml) }}
{{- end }}
{{- if or .Values.presets.annotationDiscovery.logs.enabled .Values.presets.annotationDiscovery.metrics.enabled }}
{{- $config = (include "opentelemetry-collector.applyAnnotationDiscoveryConfig" (dict "Values" $data "config" $config) | fromYaml) }}
{{- end }}
{{- if .Values.presets.hostMetrics.enabled }}
{{- $config = (include "opentelemetry-collector.applyHostMetricsConfig" (dict "Values" $data "config" $config) | fromYaml) }}
{{- end }}
{{- if .Values.presets.kubeletMetrics.enabled }}
{{- $config = (include "opentelemetry-collector.applyKubeletMetricsConfig" (dict "Values" $data "config" $config) | fromYaml) }}
{{- end }}
{{- if .Values.presets.kubernetesAttributes.enabled }}
{{- $config = (include "opentelemetry-collector.applyKubernetesAttributesConfig" (dict "Values" $data "config" $config) | fromYaml) }}
{{- end }}
{{- if .Values.presets.clusterMetrics.enabled }}
{{- $config = (include "opentelemetry-collector.applyClusterMetricsConfig" (dict "Values" $data "config" $config) | fromYaml) }}
{{- end }}
{{- tpl (toYaml $config) . }}
{{- end }}

{{/*
Build config file for deployment OpenTelemetry Collector
*/}}
{{- define "opentelemetry-collector.deploymentConfig" -}}
{{- $values := deepCopy .Values }}
{{- $data := dict "Values" $values | mustMergeOverwrite (deepCopy .) }}
{{- $config := include "opentelemetry-collector.baseConfig" $data | fromYaml }}
{{- if .Values.presets.logsCollection.enabled }}
{{- $config = (include "opentelemetry-collector.applyLogsCollectionConfig" (dict "Values" $data "config" $config) | fromYaml) }}
{{- end }}
{{- if or .Values.presets.annotationDiscovery.logs.enabled .Values.presets.annotationDiscovery.metrics.enabled }}
{{- $config = (include "opentelemetry-collector.applyAnnotationDiscoveryConfig" (dict "Values" $data "config" $config) | fromYaml) }}
{{- end }}
{{- if .Values.presets.hostMetrics.enabled }}
{{- $config = (include "opentelemetry-collector.applyHostMetricsConfig" (dict "Values" $data "config" $config) | fromYaml) }}
{{- end }}
{{- if .Values.presets.kubeletMetrics.enabled }}
{{- $config = (include "opentelemetry-collector.applyKubeletMetricsConfig" (dict "Values" $data "config" $config) | fromYaml) }}
{{- end }}
{{- if .Values.presets.kubernetesAttributes.enabled }}
{{- $config = (include "opentelemetry-collector.applyKubernetesAttributesConfig" (dict "Values" $data "config" $config) | fromYaml) }}
{{- end }}
{{- if .Values.presets.kubernetesEvents.enabled }}
{{- $config = (include "opentelemetry-collector.applyKubernetesEventsConfig" (dict "Values" $data "config" $config) | fromYaml) }}
{{- end }}
{{- if .Values.presets.clusterMetrics.enabled }}
{{- $config = (include "opentelemetry-collector.applyClusterMetricsConfig" (dict "Values" $data "config" $config) | fromYaml) }}
{{- end }}
{{- tpl (toYaml $config) . }}
{{- end }}

{{- define "opentelemetry-collector.applyHostMetricsConfig" -}}
{{- $config := mustMergeOverwrite (dict "service" (dict "pipelines" (dict "metrics" (dict "receivers" list)))) (include "opentelemetry-collector.hostMetricsConfig" .Values | fromYaml) .config }}
{{- $_ := set $config.service.pipelines.metrics "receivers" (append $config.service.pipelines.metrics.receivers "hostmetrics" | uniq)  }}
{{- $config | toYaml }}
{{- end }}

{{- define "opentelemetry-collector.hostMetricsConfig" -}}
receivers:
  hostmetrics:
    root_path: /hostfs
    collection_interval: 10s
    scrapers:
        cpu:
        load:
        memory:
        disk:
        filesystem:
          exclude_mount_points:
            mount_points:
              - /dev/*
              - /proc/*
              - /sys/*
              - /run/k3s/containerd/*
              - /var/lib/docker/*
              - /var/lib/kubelet/*
              - /snap/*
            match_type: regexp
          exclude_fs_types:
            fs_types:
              - autofs
              - binfmt_misc
              - bpf
              - cgroup2
              - configfs
              - debugfs
              - devpts
              - devtmpfs
              - fusectl
              - hugetlbfs
              - iso9660
              - mqueue
              - nsfs
              - overlay
              - proc
              - procfs
              - pstore
              - rpc_pipefs
              - securityfs
              - selinuxfs
              - squashfs
              - sysfs
              - tracefs
            match_type: strict
        network:
{{- end }}

{{- define "opentelemetry-collector.applyClusterMetricsConfig" -}}
{{- $vals := .Values.Values -}}
{{- $disableLeaderElection := false -}}
{{- if and (hasKey $vals "presets") (hasKey $vals.presets "clusterMetrics") -}}
  {{- $disableLeaderElection = $vals.presets.clusterMetrics.disableLeaderElection -}}
{{- end -}}
{{- $useLeaderElection := and (eq $vals.mode "daemonset") (not $disableLeaderElection) -}}
{{- $electorName := "k8s_cluster" }}
{{- $ctx := mustMerge (dict "namespace" (include "opentelemetry-collector.namespace" .Values) "useLeaderElection" $useLeaderElection "electorName" $electorName) .Values }}
{{- $config := mustMergeOverwrite (dict "service" (dict "pipelines" (dict "metrics" (dict "receivers" list)))) (include "opentelemetry-collector.clusterMetricsConfig" $ctx | fromYaml) .config }}
{{- if $useLeaderElection}}
{{- $configExtensions := mustMergeOverwrite (dict "service" (dict "extensions" list)) $config }}
{{- $_ := set $config.service "extensions" (append $configExtensions.service.extensions (printf "k8s_leader_elector/%s" $electorName) | uniq)  }}
{{- end }}
{{- $_ := set $config.service.pipelines.metrics "receivers" (append $config.service.pipelines.metrics.receivers "k8s_cluster" | uniq)  }}
{{- $config | toYaml }}
{{- end }}

{{- define "opentelemetry-collector.clusterMetricsConfig" -}}
{{- if .useLeaderElection}}
{{- include "opentelemetry-collector.leaderElectionConfig" (dict "name" .electorName "leaseName" "k8s.cluster.receiver.opentelemetry.io" "leaseNamespace" .namespace)}}
{{- end}}
receivers:
  k8s_cluster:
    {{- if .useLeaderElection}}
    k8s_leader_elector: k8s_leader_elector/{{ .electorName }}
    {{- end}}
    collection_interval: 10s
{{- end }}

{{- define "opentelemetry-collector.applyKubeletMetricsConfig" -}}
{{- $config := mustMergeOverwrite (dict "service" (dict "pipelines" (dict "metrics" (dict "receivers" list)))) (include "opentelemetry-collector.kubeletMetricsConfig" .Values | fromYaml) .config }}
{{- $_ := set $config.service.pipelines.metrics "receivers" (append $config.service.pipelines.metrics.receivers "kubeletstats" | uniq)  }}
{{- $config | toYaml }}
{{- end }}

{{- define "opentelemetry-collector.kubeletMetricsConfig" -}}
receivers:
  kubeletstats:
    collection_interval: 20s
    auth_type: "serviceAccount"
    endpoint: "${env:K8S_NODE_IP}:10250"
{{- end }}

{{- define "opentelemetry-collector.applyLogsCollectionConfig" -}}
{{- $config := mustMergeOverwrite (dict "service" (dict "pipelines" (dict "logs" (dict "receivers" list)))) (include "opentelemetry-collector.logsCollectionConfig" .Values | fromYaml) .config }}
{{- $_ := set $config.service.pipelines.logs "receivers" (append $config.service.pipelines.logs.receivers "filelog" | uniq)  }}
{{- if .Values.Values.presets.logsCollection.storeCheckpoints}}
{{- $configExtensions := mustMergeOverwrite (dict "service" (dict "extensions" list)) $config }}
{{- $_ := set $config.service "extensions" (append $configExtensions.service.extensions "file_storage" | uniq)  }}
{{- end }}
{{- $config | toYaml }}
{{- end }}

{{- define "opentelemetry-collector.logsCollectionConfig" -}}
{{- if .Values.presets.logsCollection.storeCheckpoints }}
extensions:
  file_storage:
    directory: /var/lib/otelcol
{{- end }}
receivers:
  filelog:
    include: [ /var/log/pods/*/*/*.log ]
    {{- if .Values.presets.logsCollection.includeCollectorLogs }}
    exclude: []
    {{- else }}
    # Exclude collector container's logs. The file format is /var/log/pods/<namespace_name>_<pod_name>_<pod_uid>/<container_name>/<run_id>.log
    exclude: [ /var/log/pods/{{ include "opentelemetry-collector.namespace" . }}_{{ include "opentelemetry-collector.fullname" . }}*_*/{{ include "opentelemetry-collector.lowercase_chartname" . }}/*.log ]
    {{- end }}
    start_at: end
    retry_on_failure:
        enabled: true
    {{- if .Values.presets.logsCollection.storeCheckpoints}}
    storage: file_storage
    {{- end }}
    include_file_path: true
    include_file_name: false
    operators:
      # parse container logs
      - type: container
        id: container-parser
        max_log_size: {{ $.Values.presets.logsCollection.maxRecombineLogSize }}
{{- end }}

{{- define "opentelemetry-collector.applyAnnotationDiscoveryConfig" -}}
{{- $config := mustMergeOverwrite (include "opentelemetry-collector.annotationDiscoveryConfig" .Values | fromYaml) .config }}
{{- $_ := set $config.service "extensions" (append $config.service.extensions "k8s_observer" | uniq) }}
{{- if .Values.Values.presets.annotationDiscovery.logs.enabled }}
{{- $_ := set $config.service.pipelines.logs "receivers" (append $config.service.pipelines.logs.receivers "receiver_creator/logs" | uniq)  }}
{{- end }}
{{- if .Values.Values.presets.annotationDiscovery.metrics.enabled }}
{{- $_ := set $config.service.pipelines.metrics "receivers" (append $config.service.pipelines.metrics.receivers "receiver_creator/metrics" | uniq) }}
{{- end }}
{{- $config | toYaml }}
{{- end }}

{{- define "opentelemetry-collector.annotationDiscoveryConfig" -}}
extensions:
  k8s_observer:
    auth_type: serviceAccount
    node: ${env:K8S_NODE_NAME}

receivers:
  {{- if .Values.presets.annotationDiscovery.logs.enabled }}
  receiver_creator/logs:
    watch_observers:
      - k8s_observer
    discovery:
      enabled: true
      default_annotations:
        io.opentelemetry.discovery.logs/enabled: "true"
 {{- end }}
  {{- if .Values.presets.annotationDiscovery.metrics.enabled }}
  receiver_creator/metrics:
    watch_observers:
      - k8s_observer
    discovery:
      enabled: true
  {{- end }}
{{- end }}

{{- define "opentelemetry-collector.applyKubernetesAttributesConfig" -}}
{{- $config := mustMergeOverwrite (include "opentelemetry-collector.kubernetesAttributesConfig" .Values | fromYaml) .config }}
{{- if $config.service.pipelines.logs }}
  {{- $config = mustMergeOverwrite (dict "service" (dict "pipelines" (dict "logs" (dict "processors" list)))) $config }}
  {{- if not (has "k8sattributes" $config.service.pipelines.logs.processors) }}
    {{- $_ := set $config.service.pipelines.logs "processors" (prepend $config.service.pipelines.logs.processors "k8sattributes" | uniq)  }}
  {{- end }}
{{- end }}
{{- if and $config.service.pipelines.metrics }}
  {{- $config = mustMergeOverwrite (dict "service" (dict "pipelines" (dict "metrics" (dict "processors" list)))) $config }}
  {{- if not (has "k8sattributes" $config.service.pipelines.metrics.processors) }}
    {{- $_ := set $config.service.pipelines.metrics "processors" (prepend $config.service.pipelines.metrics.processors "k8sattributes" | uniq)  }}
  {{- end }}
{{- end }}
{{- if and $config.service.pipelines.traces }}
  {{- $config = mustMergeOverwrite (dict "service" (dict "pipelines" (dict "traces" (dict "processors" list)))) $config }}
  {{- if not (has "k8sattributes" $config.service.pipelines.traces.processors) }}
    {{- $_ := set $config.service.pipelines.traces "processors" (prepend $config.service.pipelines.traces.processors "k8sattributes" | uniq)  }}
  {{- end }}
{{- end }}
{{- $config | toYaml }}
{{- end }}

{{- define "opentelemetry-collector.kubernetesAttributesConfig" -}}
processors:
  k8sattributes:
  {{- if eq .Values.mode "daemonset" }}
    filter:
      node_from_env_var: K8S_NODE_NAME
  {{- end }}
    passthrough: false
    pod_association:
    - sources:
      - from: resource_attribute
        name: k8s.pod.ip
    - sources:
      - from: resource_attribute
        name: k8s.pod.uid
    - sources:
      - from: connection
    extract:
      otel_annotations: true
      metadata:
        - k8s.namespace.name
        - k8s.pod.name
        - k8s.pod.uid
        - k8s.node.name
        - k8s.pod.start_time
        - k8s.deployment.name
        - k8s.replicaset.name
        - k8s.replicaset.uid
        - k8s.daemonset.name
        - k8s.daemonset.uid
        - k8s.job.name
        - k8s.job.uid
        - k8s.container.name
        - k8s.cronjob.name
        - k8s.statefulset.name
        - k8s.statefulset.uid
        - container.image.tag
        - container.image.name
        - k8s.cluster.uid
        - service.namespace
        - service.name
        - service.version
        - service.instance.id
      {{- if .Values.presets.kubernetesAttributes.extractAllPodLabels }}
      labels:
        - tag_name: $$1
          key_regex: (.*)
          from: pod
      {{- end }}
      {{- if .Values.presets.kubernetesAttributes.extractAllPodAnnotations }}
      annotations:
        - tag_name: $$1
          key_regex: (.*)
          from: pod
      {{- end }}
{{- end }}

{{/* Build the list of port for service */}}
{{- define "opentelemetry-collector.servicePortsConfig" -}}
{{- $ports := deepCopy .Values.ports }}
{{- range $key, $port := $ports }}
{{- if $port.enabled }}
- name: {{ $key }}
  port: {{ $port.servicePort }}
  targetPort: {{ $port.containerPort }}
  protocol: {{ $port.protocol }}
  {{- if $port.appProtocol }}
  appProtocol: {{ $port.appProtocol }}
  {{- end }}
{{- if $port.nodePort }}
  nodePort: {{ $port.nodePort }}
{{- end }}
{{- end }}
{{- end }}
{{- end }}

{{/* Build the list of port for pod */}}
{{- define "opentelemetry-collector.podPortsConfig" -}}
{{- $ports := deepCopy .Values.ports }}
{{- range $key, $port := $ports }}
{{- if $port.enabled }}
- name: {{ $key }}
  containerPort: {{ $port.containerPort }}
  protocol: {{ $port.protocol }}
  {{- if and $.isAgent $port.hostPort }}
  hostPort: {{ $port.hostPort }}
  {{- end }}
{{- end }}
{{- end }}
{{- end }}

{{- define "opentelemetry-collector.applyKubernetesEventsConfig" -}}
{{- $config := mustMergeOverwrite (dict "service" (dict "pipelines" (dict "logs" (dict "receivers" list)))) (include "opentelemetry-collector.kubernetesEventsConfig" .Values | fromYaml) .config }}
{{- $_ := set $config.service.pipelines.logs "receivers" (append $config.service.pipelines.logs.receivers "k8sobjects" | uniq)  }}
{{- $config | toYaml }}
{{- end }}

{{- define "opentelemetry-collector.kubernetesEventsConfig" -}}
receivers:
  k8sobjects:
    objects:
      - name: events
        mode: "watch"
        group: "events.k8s.io"
        exclude_watch_type:
          - "DELETED"
{{- end }}

{{- define "opentelemetry-collector.leaderElectionConfig" -}}
extensions:
  k8s_leader_elector/{{ .name }}:
    auth_type: serviceAccount
    lease_name: {{ .leaseName }}
    lease_namespace: {{ .leaseNamespace }}
{{- end }}
