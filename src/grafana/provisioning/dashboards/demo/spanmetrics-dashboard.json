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
  "description": "Spanmetrics way of demo application view.",
  "editable": true,
  "fiscalYearStartMonth": 0,
  "graphTooltip": 0,
  "id": 5,
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
      "id": 24,
      "panels": [],
      "title": "Service Level - Throughput and Latencies",
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
            "mode": "continuous-BlYlRd"
          },
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "blue",
                "value": null
              },
              {
                "color": "green",
                "value": 2
              },
              {
                "color": "#EAB839",
                "value": 64
              },
              {
                "color": "orange",
                "value": 128
              },
              {
                "color": "red",
                "value": 256
              }
            ]
          },
          "unit": "ms"
        },
        "overrides": []
      },
      "gridPos": {
        "h": 20,
        "w": 12,
        "x": 0,
        "y": 1
      },
      "id": 2,
      "interval": "5m",
      "options": {
        "minVizHeight": 75,
        "minVizWidth": 75,
        "orientation": "auto",
        "reduceOptions": {
          "calcs": [
            "lastNotNull"
          ],
          "fields": "",
          "values": false
        },
        "showThresholdLabels": false,
        "showThresholdMarkers": true,
        "sizing": "auto"
      },
      "pluginVersion": "11.3.0",
      "targets": [
        {
          "datasource": {
            "type": "prometheus",
            "uid": "webstore-metrics"
          },
          "editorMode": "code",
          "exemplar": false,
          "expr": "topk(7,histogram_quantile(0.50, sum(rate(traces_span_metrics_duration_milliseconds_bucket{service_name=~\"$service\", span_name=~\"$span_name\"}[$__rate_interval])) by (le,service_name)))",
          "format": "time_series",
          "hide": true,
          "instant": false,
          "interval": "",
          "legendFormat": "{{service_name}}-quantile_0.50",
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
          "expr": "topk(7,histogram_quantile(0.95, sum(rate(traces_span_metrics_duration_milliseconds_bucket{service_name=~\"$service\", span_name=~\"$span_name\"}[$__range])) by (le,service_name)))",
          "hide": false,
          "instant": true,
          "interval": "",
          "legendFormat": "{{service_name}}",
          "range": false,
          "refId": "B"
        },
        {
          "datasource": {
            "type": "prometheus",
            "uid": "webstore-metrics"
          },
          "editorMode": "code",
          "exemplar": false,
          "expr": "histogram_quantile(0.99, sum(rate(traces_span_metrics_duration_milliseconds_bucket{service_name=~\"$service\", span_name=~\"$span_name\"}[$__rate_interval])) by (le,service_name))",
          "hide": true,
          "interval": "",
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
          "expr": "histogram_quantile(0.999, sum(rate(traces_span_metrics_duration_milliseconds_bucket{service_name=~\"$service\", span_name=~\"$span_name\"}[$__rate_interval])) by (le,service_name))",
          "hide": true,
          "interval": "",
          "legendFormat": "quantile999",
          "range": true,
          "refId": "D"
        }
      ],
      "title": "Top 3x3 - Service Latency - quantile95",
      "type": "gauge"
    },
    {
      "datasource": {
        "type": "prometheus",
        "uid": "webstore-metrics"
      },
      "fieldConfig": {
        "defaults": {
          "color": {
            "mode": "continuous-BlYlRd"
          },
          "decimals": 2,
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "green",
                "value": null
              },
              {
                "color": "super-light-blue",
                "value": 1
              },
              {
                "color": "#EAB839",
                "value": 2
              },
              {
                "color": "red",
                "value": 10
              }
            ]
          },
          "unit": "reqps"
        },
        "overrides": []
      },
      "gridPos": {
        "h": 13,
        "w": 12,
        "x": 12,
        "y": 1
      },
      "id": 4,
      "interval": "5m",
      "options": {
        "displayMode": "lcd",
        "legend": {
          "calcs": [],
          "displayMode": "list",
          "placement": "bottom",
          "showLegend": false
        },
        "maxVizHeight": 300,
        "minVizHeight": 10,
        "minVizWidth": 0,
        "namePlacement": "auto",
        "orientation": "horizontal",
        "reduceOptions": {
          "calcs": [
            "mean"
          ],
          "fields": "",
          "values": false
        },
        "showUnfilled": true,
        "sizing": "auto",
        "text": {},
        "valueMode": "color"
      },
      "pluginVersion": "11.3.0",
      "targets": [
        {
          "datasource": {
            "type": "prometheus",
            "uid": "webstore-metrics"
          },
          "editorMode": "code",
          "exemplar": false,
          "expr": "topk(7,sum by (service_name) (rate(traces_span_metrics_calls_total{service_name=~\"$service\", span_name=~\"$span_name\"}[$__range])))",
          "format": "time_series",
          "instant": true,
          "interval": "",
          "legendFormat": "{{service_name}}",
          "range": false,
          "refId": "A"
        }
      ],
      "title": "Top 7 Services Mean Rate over Range",
      "type": "bargauge"
    },
    {
      "datasource": {
        "type": "prometheus",
        "uid": "webstore-metrics"
      },
      "fieldConfig": {
        "defaults": {
          "color": {
            "mode": "continuous-reds"
          },
          "decimals": 4,
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "green",
                "value": null
              },
              {
                "color": "#EAB839",
                "value": 1
              },
              {
                "color": "red",
                "value": 15
              }
            ]
          },
          "unit": "reqps"
        },
        "overrides": []
      },
      "gridPos": {
        "h": 7,
        "w": 12,
        "x": 12,
        "y": 14
      },
      "id": 15,
      "interval": "5m",
      "options": {
        "displayMode": "lcd",
        "legend": {
          "calcs": [],
          "displayMode": "list",
          "placement": "bottom",
          "showLegend": false
        },
        "maxVizHeight": 300,
        "minVizHeight": 10,
        "minVizWidth": 0,
        "namePlacement": "auto",
        "orientation": "vertical",
        "reduceOptions": {
          "calcs": [
            "mean"
          ],
          "fields": "",
          "values": false
        },
        "showUnfilled": true,
        "sizing": "auto",
        "text": {},
        "valueMode": "color"
      },
      "pluginVersion": "11.3.0",
      "targets": [
        {
          "datasource": {
            "type": "prometheus",
            "uid": "webstore-metrics"
          },
          "editorMode": "code",
          "exemplar": false,
          "expr": "topk(7,sum(rate(traces_span_metrics_calls_total{status_code=\"STATUS_CODE_ERROR\",service_name=~\"$service\", span_name=~\"$span_name\"}[$__range])) by (service_name))",
          "instant": true,
          "interval": "",
          "legendFormat": "{{service_name}}",
          "range": false,
          "refId": "A"
        }
      ],
      "title": "Top 7 Services Mean ERROR Rate over Range",
      "type": "bargauge"
    },
    {
      "collapsed": false,
      "gridPos": {
        "h": 1,
        "w": 24,
        "x": 0,
        "y": 21
      },
      "id": 14,
      "panels": [],
      "title": "span_names Level - Throughput",
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
            "mode": "thresholds"
          },
          "custom": {
            "align": "auto",
            "cellOptions": {
              "type": "auto"
            },
            "inspect": false
          },
          "decimals": 2,
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
        "overrides": [
          {
            "matcher": {
              "id": "byName",
              "options": "bRate"
            },
            "properties": [
              {
                "id": "custom.cellOptions",
                "value": {
                  "mode": "lcd",
                  "type": "gauge"
                }
              },
              {
                "id": "color",
                "value": {
                  "mode": "continuous-BlYlRd"
                }
              }
            ]
          },
          {
            "matcher": {
              "id": "byName",
              "options": "eRate"
            },
            "properties": [
              {
                "id": "custom.cellOptions",
                "value": {
                  "mode": "lcd",
                  "type": "gauge"
                }
              },
              {
                "id": "color",
                "value": {
                  "mode": "continuous-RdYlGr"
                }
              }
            ]
          },
          {
            "matcher": {
              "id": "byName",
              "options": "Error Rate"
            },
            "properties": [
              {
                "id": "custom.width",
                "value": 663
              }
            ]
          },
          {
            "matcher": {
              "id": "byName",
              "options": "Rate"
            },
            "properties": [
              {
                "id": "custom.width",
                "value": 667
              }
            ]
          },
          {
            "matcher": {
              "id": "byName",
              "options": "Service"
            },
            "properties": [
              {
                "id": "custom.width"
              }
            ]
          }
        ]
      },
      "gridPos": {
        "h": 11,
        "w": 24,
        "x": 0,
        "y": 22
      },
      "id": 22,
      "interval": "5m",
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
        "sortBy": []
      },
      "pluginVersion": "11.3.0",
      "targets": [
        {
          "datasource": {
            "type": "prometheus",
            "uid": "webstore-metrics"
          },
          "exemplar": false,
          "expr": "topk(7, sum(rate(traces_span_metrics_calls_total{service_name=~\"$service\", span_name=~\"$span_name\"}[$__range])) by (span_name,service_name)) ",
          "format": "table",
          "instant": true,
          "interval": "",
          "legendFormat": "",
          "refId": "Rate"
        },
        {
          "datasource": {
            "type": "prometheus",
            "uid": "webstore-metrics"
          },
          "exemplar": false,
          "expr": "topk(7, sum(rate(traces_span_metrics_calls_total{status_code=\"STATUS_CODE_ERROR\",service_name=~\"$service\", span_name=~\"$span_name\"}[$__range])) by (span_name,service_name))",
          "format": "table",
          "hide": false,
          "instant": true,
          "interval": "",
          "legendFormat": "",
          "refId": "Error Rate"
        }
      ],
      "title": "Top 7 span_names and Errors  (APM Table)",
      "transformations": [
        {
          "id": "seriesToColumns",
          "options": {
            "byField": "span_name"
          }
        },
        {
          "id": "organize",
          "options": {
            "excludeByName": {
              "Time 1": true,
              "Time 2": true
            },
            "indexByName": {},
            "renameByName": {
              "Value #Error Rate": "Error Rate",
              "Value #Rate": "Rate",
              "service_name 1": "Rate in Service",
              "service_name 2": "Error Rate in Service"
            }
          }
        },
        {
          "id": "calculateField",
          "options": {
            "alias": "bRate",
            "mode": "reduceRow",
            "reduce": {
              "include": [
                "Rate"
              ],
              "reducer": "sum"
            }
          }
        },
        {
          "id": "calculateField",
          "options": {
            "alias": "eRate",
            "mode": "reduceRow",
            "reduce": {
              "include": [
                "Error Rate"
              ],
              "reducer": "sum"
            }
          }
        },
        {
          "id": "organize",
          "options": {
            "excludeByName": {
              "Error Rate": true,
              "Rate": true,
              "bRate": false
            },
            "indexByName": {
              "Error Rate": 4,
              "Error Rate in Service": 6,
              "Rate": 1,
              "Rate in Service": 5,
              "bRate": 2,
              "eRate": 3,
              "span_name": 0
            },
            "renameByName": {
              "Rate in Service": "Service",
              "bRate": "Rate",
              "eRate": "Error Rate",
              "span_name": "span_name Name"
            }
          }
        },
        {
          "id": "sortBy",
          "options": {
            "fields": {},
            "sort": [
              {
                "desc": true,
                "field": "Rate"
              }
            ]
          }
        }
      ],
      "type": "table"
    },
    {
      "collapsed": false,
      "gridPos": {
        "h": 1,
        "w": 24,
        "x": 0,
        "y": 33
      },
      "id": 20,
      "panels": [],
      "title": "span_name Level - Latencies",
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
            "mode": "continuous-BlYlRd"
          },
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "blue",
                "value": null
              },
              {
                "color": "green",
                "value": 2
              },
              {
                "color": "#EAB839",
                "value": 64
              },
              {
                "color": "orange",
                "value": 128
              },
              {
                "color": "red",
                "value": 256
              }
            ]
          },
          "unit": "ms"
        },
        "overrides": []
      },
      "gridPos": {
        "h": 13,
        "w": 12,
        "x": 0,
        "y": 34
      },
      "id": 25,
      "interval": "5m",
      "options": {
        "minVizHeight": 75,
        "minVizWidth": 75,
        "orientation": "auto",
        "reduceOptions": {
          "calcs": [
            "lastNotNull"
          ],
          "fields": "",
          "values": false
        },
        "showThresholdLabels": false,
        "showThresholdMarkers": true,
        "sizing": "auto"
      },
      "pluginVersion": "11.3.0",
      "targets": [
        {
          "datasource": {
            "type": "prometheus",
            "uid": "webstore-metrics"
          },
          "editorMode": "code",
          "exemplar": false,
          "expr": "topk(7,histogram_quantile(0.50, sum(rate(traces_span_metrics_duration_milliseconds_bucket{service_name=~\"$service\", span_name=~\"$span_name\"}[$__rate_interval])) by (le,service_name)))",
          "format": "time_series",
          "hide": true,
          "instant": false,
          "interval": "",
          "legendFormat": "{{service_name}}-quantile_0.50",
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
          "expr": "topk(7,histogram_quantile(0.95, sum(rate(traces_span_metrics_duration_milliseconds_bucket{service_name=~\"$service\", span_name=~\"$span_name\"}[$__range])) by (le,span_name)))",
          "hide": false,
          "instant": true,
          "interval": "",
          "legendFormat": "{{span_name}}",
          "range": false,
          "refId": "B"
        },
        {
          "datasource": {
            "type": "prometheus",
            "uid": "webstore-metrics"
          },
          "editorMode": "code",
          "exemplar": false,
          "expr": "histogram_quantile(0.99, sum(rate(traces_span_metrics_duration_milliseconds_bucket{service_name=~\"$service\", span_name=~\"$span_name\"}[$__rate_interval])) by (le,service_name))",
          "hide": true,
          "interval": "",
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
          "expr": "histogram_quantile(0.999, sum(rate(traces_span_metrics_duration_milliseconds_bucket{service_name=~\"$service\", span_name=~\"$span_name\"}[$__rate_interval])) by (le,service_name))",
          "hide": true,
          "interval": "",
          "legendFormat": "quantile999",
          "range": true,
          "refId": "D"
        }
      ],
      "title": "Top 3x3 - span_name Latency - quantile95",
      "type": "gauge"
    },
    {
      "datasource": {
        "type": "prometheus",
        "uid": "webstore-metrics"
      },
      "fieldConfig": {
        "defaults": {
          "color": {
            "mode": "continuous-BlYlRd"
          },
          "decimals": 2,
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
          "unit": "ms"
        },
        "overrides": []
      },
      "gridPos": {
        "h": 13,
        "w": 12,
        "x": 12,
        "y": 34
      },
      "id": 10,
      "interval": "5m",
      "options": {
        "displayMode": "lcd",
        "legend": {
          "calcs": [],
          "displayMode": "list",
          "placement": "bottom",
          "showLegend": false
        },
        "maxVizHeight": 300,
        "minVizHeight": 10,
        "minVizWidth": 0,
        "namePlacement": "auto",
        "orientation": "horizontal",
        "reduceOptions": {
          "calcs": [
            "mean"
          ],
          "fields": "",
          "values": false
        },
        "showUnfilled": true,
        "sizing": "auto",
        "valueMode": "color"
      },
      "pluginVersion": "11.3.0",
      "targets": [
        {
          "datasource": {
            "type": "prometheus",
            "uid": "webstore-metrics"
          },
          "editorMode": "code",
          "exemplar": false,
          "expr": "topk(7, sum by (span_name,service_name)(increase(duration_milliseconds_sum{service_name=~\"${service}\", span_name=~\"$span_name\"}[5m]) / increase(traces_span_metrics_duration_milliseconds_count{service_name=~\"${service}\",span_name=~\"$span_name\"}[5m\n])))",
          "instant": true,
          "interval": "",
          "legendFormat": "{{span_name}} [{{service_name}}]",
          "range": false,
          "refId": "A"
        }
      ],
      "title": "Top 7 Highest Endpoint Latencies  Mean Over Range ",
      "type": "bargauge"
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
            "fillOpacity": 15,
            "gradientMode": "none",
            "hideFrom": {
              "legend": false,
              "tooltip": false,
              "viz": false
            },
            "insertNulls": false,
            "lineInterpolation": "smooth",
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
          "unit": "ms"
        },
        "overrides": []
      },
      "gridPos": {
        "h": 12,
        "w": 24,
        "x": 0,
        "y": 47
      },
      "id": 16,
      "interval": "5m",
      "options": {
        "legend": {
          "calcs": [
            "mean",
            "logmin",
            "max",
            "delta"
          ],
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
          "exemplar": true,
          "expr": "topk(7,sum by (span_name,service_name)(increase(traces_span_metrics_duration_milliseconds_sum{service_name=~\"$service\", span_name=~\"$span_name\"}[$__rate_interval]) / increase(traces_span_metrics_duration_milliseconds_count{service_name=~\"$service\", span_name=~\"$span_name\"}[$__rate_interval])))",
          "instant": false,
          "interval": "",
          "legendFormat": "[{{service_name}}]  {{span_name}}",
          "range": true,
          "refId": "A"
        }
      ],
      "title": "Top 7 Latencies Over Range ",
      "type": "timeseries"
    }
  ],
  "preload": false,
  "refresh": "5m",
  "schemaVersion": 40,
  "tags": [],
  "templating": {
    "list": [
      {
        "allValue": ".*",
        "current": {
          "text": "All",
          "value": "$__all"
        },
        "datasource": {
          "type": "prometheus",
          "uid": "webstore-metrics"
        },
        "definition": "query_result(count by (service_name)(count_over_time(traces_span_metrics_calls_total[$__range])))",
        "includeAll": true,
        "multi": true,
        "name": "service",
        "options": [],
        "query": {
          "query": "query_result(count by (service_name)(count_over_time(traces_span_metrics_calls_total[$__range])))",
          "refId": "StandardVariableQuery"
        },
        "refresh": 2,
        "regex": "/.*service_name=\"(.*)\".*/",
        "sort": 1,
        "type": "query"
      },
      {
        "allValue": ".*",
        "current": {
          "text": "All",
          "value": "$__all"
        },
        "datasource": {
          "type": "prometheus",
          "uid": "webstore-metrics"
        },
        "definition": "query_result(sum ({__name__=~\".*traces_span_metrics_calls_total\",service_name=~\"$service\"})  by (span_name))",
        "includeAll": true,
        "multi": true,
        "name": "span_name",
        "options": [],
        "query": {
          "query": "query_result(sum ({__name__=~\".*traces_span_metrics_calls_total\",service_name=~\"$service\"})  by (span_name))",
          "refId": "StandardVariableQuery"
        },
        "refresh": 2,
        "regex": "/.*span_name=\"(.*)\".*/",
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
  "title": "Spanmetrics Demo Dashboard",
  "uid": "W2gX2zHVk48",
  "version": 1,
  "weekStart": ""
}
