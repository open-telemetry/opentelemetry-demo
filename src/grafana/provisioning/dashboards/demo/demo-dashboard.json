{
  "annotations": {
    "list": [
      {
        "builtIn": 1,
        "datasource": {
          "type": "grafana",
          "uid": "-- Grafana --"
        },
        "enable": true,
        "hide": true,
        "iconColor": "rgba(0, 211, 255, 1)",
        "name": "Annotations & Alerts",
        "target": {
          "limit": 100,
          "matchAny": false,
          "tags": [],
          "type": "dashboard"
        },
        "type": "dashboard"
      }
    ]
  },
  "editable": true,
  "fiscalYearStartMonth": 0,
  "graphTooltip": 0,
  "id": 2,
  "links": [],
  "panels": [
    {
      "collapsed": false,
      "gridPos": {
        "h": 1,
        "w": 24,
        "x": 0,
        "y": 0
      },
      "id": 14,
      "panels": [],
      "title": "Spanmetrics",
      "type": "row"
    },
    {
      "datasource": {
        "type": "prometheus",
        "uid": "webstore-metrics"
      },
      "description": "",
      "fieldConfig": {
        "defaults": {
          "color": {
            "mode": "palette-classic"
          },
          "custom": {
            "axisBorderShow": false,
            "axisCenteredZero": false,
            "axisColorMode": "text",
            "axisLabel": "",
            "axisPlacement": "auto",
            "barAlignment": 0,
            "barWidthFactor": 0.6,
            "drawStyle": "line",
            "fillOpacity": 0,
            "gradientMode": "none",
            "hideFrom": {
              "legend": false,
              "tooltip": false,
              "viz": false
            },
            "insertNulls": false,
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "pointSize": 5,
            "scaleDistribution": {
              "type": "linear"
            },
            "showPoints": "auto",
            "spanNulls": false,
            "stacking": {
              "group": "A",
              "mode": "none"
            },
            "thresholdsStyle": {
              "mode": "off"
            }
          },
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "green",
                "value": null
              },
              {
                "color": "red",
                "value": 80
              }
            ]
          },
          "unit": "dtdurationms"
        },
        "overrides": []
      },
      "gridPos": {
        "h": 8,
        "w": 12,
        "x": 0,
        "y": 1
      },
      "id": 2,
      "interval": "2m",
      "options": {
        "legend": {
          "calcs": [],
          "displayMode": "list",
          "placement": "bottom",
          "showLegend": true
        },
        "tooltip": {
          "mode": "single",
          "sort": "none"
        }
      },
      "pluginVersion": "11.3.0",
      "targets": [
        {
          "datasource": {
            "type": "prometheus",
            "uid": "webstore-metrics"
          },
          "editorMode": "code",
          "exemplar": true,
          "expr": "histogram_quantile(0.50, sum(rate(traces_span_metrics_duration_milliseconds_bucket{service_name=\"${service}\"}[$__rate_interval])) by (le))",
          "legendFormat": "quantile50",
          "range": true,
          "refId": "A"
        },
        {
          "datasource": {
            "type": "prometheus",
            "uid": "webstore-metrics"
          },
          "editorMode": "code",
          "exemplar": false,
          "expr": "histogram_quantile(0.95, sum(rate(traces_span_metrics_duration_milliseconds_bucket{service_name=\"${service}\"}[$__rate_interval])) by (le))",
          "hide": false,
          "legendFormat": "quantile95",
          "range": true,
          "refId": "B"
        },
        {
          "datasource": {
            "type": "prometheus",
            "uid": "webstore-metrics"
          },
          "editorMode": "code",
          "exemplar": false,
          "expr": "histogram_quantile(0.99, sum(rate(traces_span_metrics_duration_milliseconds_bucket{service_name=\"${service}\"}[$__rate_interval])) by (le))",
          "hide": false,
          "legendFormat": "quantile99",
          "range": true,
          "refId": "C"
        },
        {
          "datasource": {
            "type": "prometheus",
            "uid": "webstore-metrics"
          },
          "editorMode": "code",
          "exemplar": false,
          "expr": "histogram_quantile(0.999, sum(rate(traces_span_metrics_duration_milliseconds_bucket{service_name=\"${service}\"}[$__rate_interval])) by (le))",
          "hide": false,
          "legendFormat": "quantile999",
          "range": true,
          "refId": "D"
        }
      ],
      "title": "Latency for ${service}",
      "type": "timeseries"
    },
    {
      "datasource": {
        "type": "prometheus",
        "uid": "webstore-metrics"
      },
      "description": "",
      "fieldConfig": {
        "defaults": {
          "color": {
            "mode": "palette-classic"
          },
          "custom": {
            "axisBorderShow": false,
            "axisCenteredZero": false,
            "axisColorMode": "text",
            "axisLabel": "",
            "axisPlacement": "auto",
            "barAlignment": 0,
            "barWidthFactor": 0.6,
            "drawStyle": "line",
            "fillOpacity": 0,
            "gradientMode": "none",
            "hideFrom": {
              "legend": false,
              "tooltip": false,
              "viz": false
            },
            "insertNulls": false,
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "pointSize": 5,
            "scaleDistribution": {
              "type": "linear"
            },
            "showPoints": "auto",
            "spanNulls": false,
            "stacking": {
              "group": "A",
              "mode": "none"
            },
            "thresholdsStyle": {
              "mode": "off"
            }
          },
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "green",
                "value": null
              },
              {
                "color": "red",
                "value": 80
              }
            ]
          }
        },
        "overrides": []
      },
      "gridPos": {
        "h": 8,
        "w": 12,
        "x": 12,
        "y": 1
      },
      "id": 10,
      "interval": "2m",
      "options": {
        "legend": {
          "calcs": [],
          "displayMode": "list",
          "placement": "bottom",
          "showLegend": true
        },
        "tooltip": {
          "mode": "single",
          "sort": "none"
        }
      },
      "pluginVersion": "11.3.0",
      "targets": [
        {
          "datasource": {
            "type": "prometheus",
            "uid": "webstore-metrics"
          },
          "editorMode": "code",
          "expr": " sum by (span_name) (rate(traces_span_metrics_calls_total{status_code=\"STATUS_CODE_ERROR\", service_name=\"${service}\"}[$__rate_interval]))",
          "interval": "",
          "legendFormat": "{{ span_name }}",
          "range": true,
          "refId": "A"
        }
      ],
      "title": "Error Rate for ${service} by span name",
      "type": "timeseries"
    },
    {
      "datasource": {
        "type": "prometheus",
        "uid": "webstore-metrics"
      },
      "fieldConfig": {
        "defaults": {
          "color": {
            "mode": "palette-classic"
          },
          "custom": {
            "axisBorderShow": false,
            "axisCenteredZero": false,
            "axisColorMode": "text",
            "axisLabel": "",
            "axisPlacement": "auto",
            "barAlignment": 0,
            "barWidthFactor": 0.6,
            "drawStyle": "line",
            "fillOpacity": 0,
            "gradientMode": "none",
            "hideFrom": {
              "legend": false,
              "tooltip": false,
              "viz": false
            },
            "insertNulls": false,
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "pointSize": 5,
            "scaleDistribution": {
              "type": "linear"
            },
            "showPoints": "auto",
            "spanNulls": false,
            "stacking": {
              "group": "A",
              "mode": "none"
            },
            "thresholdsStyle": {
              "mode": "off"
            }
          },
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "green",
                "value": null
              },
              {
                "color": "red",
                "value": 80
              }
            ]
          },
          "unit": "reqps"
        },
        "overrides": []
      },
      "gridPos": {
        "h": 8,
        "w": 12,
        "x": 0,
        "y": 9
      },
      "id": 12,
      "interval": "2m",
      "options": {
        "legend": {
          "calcs": [],
          "displayMode": "table",
          "placement": "bottom",
          "showLegend": true
        },
        "tooltip": {
          "mode": "single",
          "sort": "none"
        }
      },
      "pluginVersion": "11.3.0",
      "targets": [
        {
          "datasource": {
            "type": "prometheus",
            "uid": "webstore-metrics"
          },
          "editorMode": "code",
          "expr": "sum by (span_name) (rate(traces_span_metrics_duration_milliseconds_count{service_name=\"${service}\"}[$__rate_interval]))",
          "legendFormat": "{{ span_name }}",
          "range": true,
          "refId": "A"
        }
      ],
      "title": "Requests Rate for ${service} by span name",
      "type": "timeseries"
    },
    {
      "collapsed": false,
      "gridPos": {
        "h": 1,
        "w": 24,
        "x": 0,
        "y": 17
      },
      "id": 19,
      "panels": [],
      "title": "Application Logs",
      "type": "row"
    },
    {
      "datasource": {
        "type": "grafana-opensearch-datasource",
        "uid": "P9744FCCEAAFBD98F"
      },
      "description": "",
      "fieldConfig": {
        "defaults": {
          "color": {
            "mode": "thresholds"
          },
          "custom": {
            "align": "left",
            "cellOptions": {
              "type": "auto"
            },
            "inspect": false
          },
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "green",
                "value": null
              },
              {
                "color": "red",
                "value": 80
              }
            ]
          }
        },
        "overrides": [
          {
            "matcher": {
              "id": "byName",
              "options": "count()"
            },
            "properties": [
              {
                "id": "custom.width",
                "value": 90
              }
            ]
          }
        ]
      },
      "gridPos": {
        "h": 8,
        "w": 4,
        "x": 0,
        "y": 18
      },
      "id": 20,
      "options": {
        "cellHeight": "sm",
        "footer": {
          "countRows": false,
          "fields": "",
          "reducer": [
            "sum"
          ],
          "show": false
        },
        "showHeader": true
      },
      "pluginVersion": "11.3.0",
      "targets": [
        {
          "alias": "",
          "bucketAggs": [
            {
              "field": "time",
              "id": "2",
              "settings": {
                "interval": "auto"
              },
              "type": "date_histogram"
            }
          ],
          "datasource": {
            "type": "grafana-opensearch-datasource",
            "uid": "P9744FCCEAAFBD98F"
          },
          "format": "table",
          "metrics": [
            {
              "id": "1",
              "type": "count"
            }
          ],
          "query": "search source=otel\n| where resource.service.name=\"${service}\"\n| stats count() by severity.text",
          "queryType": "PPL",
          "refId": "A",
          "timeField": "time"
        }
      ],
      "title": "${service} Log entries by Severity",
      "type": "table"
    },
    {
      "datasource": {
        "type": "grafana-opensearch-datasource",
        "uid": "P9744FCCEAAFBD98F"
      },
      "fieldConfig": {
        "defaults": {
          "color": {
            "mode": "thresholds"
          },
          "custom": {
            "align": "auto",
            "cellOptions": {
              "type": "auto"
            },
            "inspect": false
          },
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "green",
                "value": null
              },
              {
                "color": "red",
                "value": 80
              }
            ]
          }
        },
        "overrides": [
          {
            "matcher": {
              "id": "byName",
              "options": "observedTimestamp"
            },
            "properties": [
              {
                "id": "custom.width",
                "value": 222
              }
            ]
          }
        ]
      },
      "gridPos": {
        "h": 8,
        "w": 20,
        "x": 4,
        "y": 18
      },
      "id": 17,
      "options": {
        "cellHeight": "sm",
        "footer": {
          "countRows": false,
          "fields": "",
          "reducer": [
            "sum"
          ],
          "show": false
        },
        "showHeader": true,
        "sortBy": [
          {
            "desc": true,
            "displayName": "observedTimestamp"
          }
        ]
      },
      "pluginVersion": "11.3.0",
      "targets": [
        {
          "alias": "",
          "bucketAggs": [
            {
              "field": "time",
              "id": "2",
              "settings": {
                "interval": "auto"
              },
              "type": "date_histogram"
            }
          ],
          "datasource": {
            "type": "grafana-opensearch-datasource",
            "uid": "P9744FCCEAAFBD98F"
          },
          "format": "logs",
          "hide": false,
          "metrics": [
            {
              "id": "1",
              "type": "count"
            }
          ],
          "query": "search source=otel\n| where resource.service.name=\"${service}\"| sort - observedTimestamp | head 100",
          "queryType": "PPL",
          "refId": "A",
          "timeField": "observedTimestamp"
        }
      ],
      "title": "${service} Logs (100 recent entries)",
      "type": "table"
    },
    {
      "collapsed": false,
      "gridPos": {
        "h": 1,
        "w": 24,
        "x": 0,
        "y": 26
      },
      "id": 18,
      "panels": [],
      "title": "Application Metrics",
      "type": "row"
    },
    {
      "datasource": {
        "type": "prometheus",
        "uid": "webstore-metrics"
      },
      "fieldConfig": {
        "defaults": {
          "color": {
            "mode": "palette-classic"
          },
          "custom": {
            "axisBorderShow": false,
            "axisCenteredZero": false,
            "axisColorMode": "text",
            "axisLabel": "",
            "axisPlacement": "auto",
            "barAlignment": 0,
            "barWidthFactor": 0.6,
            "drawStyle": "line",
            "fillOpacity": 0,
            "gradientMode": "none",
            "hideFrom": {
              "legend": false,
              "tooltip": false,
              "viz": false
            },
            "insertNulls": false,
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "pointSize": 5,
            "scaleDistribution": {
              "type": "linear"
            },
            "showPoints": "auto",
            "spanNulls": false,
            "stacking": {
              "group": "A",
              "mode": "none"
            },
            "thresholdsStyle": {
              "mode": "off"
            }
          },
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "green",
                "value": null
              },
              {
                "color": "red",
                "value": 80
              }
            ]
          },
          "unit": "percent"
        },
        "overrides": []
      },
      "gridPos": {
        "h": 8,
        "w": 12,
        "x": 0,
        "y": 27
      },
      "id": 6,
      "options": {
        "legend": {
          "calcs": [],
          "displayMode": "list",
          "placement": "bottom",
          "showLegend": true
        },
        "tooltip": {
          "mode": "single",
          "sort": "none"
        }
      },
      "pluginVersion": "11.3.0",
      "targets": [
        {
          "datasource": {
            "type": "prometheus",
            "uid": "webstore-metrics"
          },
          "editorMode": "code",
          "expr": "rate(process_runtime_cpython_cpu_time_seconds_total{type=~\"system\"}[$__rate_interval])*100",
          "hide": false,
          "interval": "2m",
          "legendFormat": "{{job}} ({{type}})",
          "range": true,
          "refId": "A"
        },
        {
          "datasource": {
            "type": "prometheus",
            "uid": "webstore-metrics"
          },
          "editorMode": "code",
          "expr": "rate(process_runtime_cpython_cpu_time_seconds_total{type=~\"user\"}[$__rate_interval])*100",
          "hide": false,
          "interval": "2m",
          "legendFormat": "{{job}} ({{type}})",
          "range": true,
          "refId": "B"
        }
      ],
      "title": "Python services (CPU%)",
      "transformations": [
        {
          "id": "renameByRegex",
          "options": {
            "regex": "opentelemetry-demo/(.*)",
            "renamePattern": "$1"
          }
        }
      ],
      "type": "timeseries"
    },
    {
      "datasource": {
        "type": "prometheus",
        "uid": "webstore-metrics"
      },
      "fieldConfig": {
        "defaults": {
          "color": {
            "mode": "palette-classic"
          },
          "custom": {
            "axisBorderShow": false,
            "axisCenteredZero": false,
            "axisColorMode": "text",
            "axisLabel": "",
            "axisPlacement": "auto",
            "barAlignment": 0,
            "barWidthFactor": 0.6,
            "drawStyle": "line",
            "fillOpacity": 0,
            "gradientMode": "none",
            "hideFrom": {
              "legend": false,
              "tooltip": false,
              "viz": false
            },
            "insertNulls": false,
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "pointSize": 5,
            "scaleDistribution": {
              "type": "linear"
            },
            "showPoints": "auto",
            "spanNulls": false,
            "stacking": {
              "group": "A",
              "mode": "none"
            },
            "thresholdsStyle": {
              "mode": "off"
            }
          },
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "green",
                "value": null
              },
              {
                "color": "red",
                "value": 80
              }
            ]
          },
          "unit": "bytes"
        },
        "overrides": []
      },
      "gridPos": {
        "h": 8,
        "w": 12,
        "x": 12,
        "y": 27
      },
      "id": 8,
      "options": {
        "legend": {
          "calcs": [],
          "displayMode": "list",
          "placement": "bottom",
          "showLegend": true
        },
        "tooltip": {
          "mode": "single",
          "sort": "none"
        }
      },
      "pluginVersion": "11.3.0",
      "targets": [
        {
          "datasource": {
            "type": "prometheus",
            "uid": "webstore-metrics"
          },
          "editorMode": "code",
          "expr": "process_runtime_cpython_memory_bytes{type=\"rss\"}",
          "legendFormat": "{{job}}",
          "range": true,
          "refId": "A"
        }
      ],
      "title": "Python services (Memory)",
      "transformations": [
        {
          "id": "renameByRegex",
          "options": {
            "regex": "opentelemetry-demo/(.*)",
            "renamePattern": "$1"
          }
        }
      ],
      "type": "timeseries"
    },
    {
      "datasource": {
        "type": "prometheus",
        "uid": "webstore-metrics"
      },
      "fieldConfig": {
        "defaults": {
          "color": {
            "mode": "palette-classic"
          },
          "custom": {
            "axisBorderShow": false,
            "axisCenteredZero": false,
            "axisColorMode": "text",
            "axisLabel": "",
            "axisPlacement": "auto",
            "barAlignment": 0,
            "barWidthFactor": 0.6,
            "drawStyle": "bars",
            "fillOpacity": 0,
            "gradientMode": "none",
            "hideFrom": {
              "legend": false,
              "tooltip": false,
              "viz": false
            },
            "insertNulls": false,
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "pointSize": 5,
            "scaleDistribution": {
              "type": "linear"
            },
            "showPoints": "auto",
            "spanNulls": false,
            "stacking": {
              "group": "A",
              "mode": "none"
            },
            "thresholdsStyle": {
              "mode": "off"
            }
          },
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "green",
                "value": null
              },
              {
                "color": "red",
                "value": 80
              }
            ]
          }
        },
        "overrides": []
      },
      "gridPos": {
        "h": 8,
        "w": 12,
        "x": 0,
        "y": 35
      },
      "id": 4,
      "options": {
        "legend": {
          "calcs": [],
          "displayMode": "list",
          "placement": "bottom",
          "showLegend": false
        },
        "tooltip": {
          "mode": "single",
          "sort": "none"
        }
      },
      "pluginVersion": "11.3.0",
      "targets": [
        {
          "datasource": {
            "type": "prometheus",
            "uid": "webstore-metrics"
          },
          "editorMode": "code",
          "expr": "rate(app_recommendations_counter_total{recommendation_type=\"catalog\"}[$__rate_interval])",
          "interval": "2m",
          "legendFormat": "recommendations",
          "range": true,
          "refId": "A"
        }
      ],
      "title": "Recommendations Rate",
      "type": "timeseries"
    },
    {
      "datasource": {
        "type": "prometheus",
        "uid": "webstore-metrics"
      },
      "fieldConfig": {
        "defaults": {
          "color": {
            "mode": "palette-classic"
          },
          "custom": {
            "axisBorderShow": false,
            "axisCenteredZero": false,
            "axisColorMode": "text",
            "axisLabel": "",
            "axisPlacement": "auto",
            "barAlignment": 0,
            "barWidthFactor": 0.6,
            "drawStyle": "line",
            "fillOpacity": 0,
            "gradientMode": "none",
            "hideFrom": {
              "legend": false,
              "tooltip": false,
              "viz": false
            },
            "insertNulls": false,
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "pointSize": 5,
            "scaleDistribution": {
              "type": "linear"
            },
            "showPoints": "auto",
            "spanNulls": false,
            "stacking": {
              "group": "A",
              "mode": "none"
            },
            "thresholdsStyle": {
              "mode": "off"
            }
          },
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "green",
                "value": null
              },
              {
                "color": "red",
                "value": 80
              }
            ]
          }
        },
        "overrides": []
      },
      "gridPos": {
        "h": 8,
        "w": 12,
        "x": 12,
        "y": 35
      },
      "id": 16,
      "interval": "2m",
      "options": {
        "legend": {
          "calcs": [],
          "displayMode": "list",
          "placement": "bottom",
          "showLegend": true
        },
        "tooltip": {
          "mode": "single",
          "sort": "none"
        }
      },
      "pluginVersion": "11.3.0",
      "targets": [
        {
          "datasource": {
            "type": "prometheus",
            "uid": "webstore-metrics"
          },
          "editorMode": "code",
          "expr": "rate(otel_trace_span_processor_spans{job=\"opentelemetry-demo/quote\"}[2m])*120",
          "interval": "2m",
          "legendFormat": "{{state}}",
          "range": true,
          "refId": "A"
        }
      ],
      "title": "Quote Service batch span processor",
      "type": "timeseries"
    }
  ],
  "preload": false,
  "refresh": "",
  "schemaVersion": 40,
  "tags": [],
  "templating": {
    "list": [
      {
        "current": {
          "text": "frontend",
          "value": "frontend"
        },
        "datasource": {
          "type": "prometheus",
          "uid": "webstore-metrics"
        },
        "definition": "traces_span_metrics_duration_milliseconds_bucket",
        "includeAll": false,
        "name": "service",
        "options": [],
        "query": {
          "query": "traces_span_metrics_duration_milliseconds_bucket",
          "refId": "PrometheusVariableQueryEditor-VariableQuery"
        },
        "refresh": 1,
        "regex": "/.*service_name=\\\"([^\\\"]+)\\\".*/",
        "sort": 1,
        "type": "query"
      }
    ]
  },
  "time": {
    "from": "now-1h",
    "to": "now"
  },
  "timepicker": {},
  "timezone": "",
  "title": "Demo Dashboard",
  "uid": "W2gX2zHVk",
  "version": 1,
  "weekStart": ""
}
