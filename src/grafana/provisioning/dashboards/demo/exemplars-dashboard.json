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
        "type": "dashboard"
      }
    ]
  },
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
      "id": 4,
      "panels": [],
      "title": "GetCart Exemplars",
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
          }
        },
        "overrides": []
      },
      "gridPos": {
        "h": 10,
        "w": 24,
        "x": 0,
        "y": 10
      },
      "id": 5,
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
          "disableTextWrap": false,
          "editorMode": "builder",
          "exemplar": true,
          "expr": "histogram_quantile(0.95, sum by(le) (rate(app_cart_get_cart_latency_bucket[$__rate_interval])))",
          "fullMetaSearch": false,
          "includeNullMetadata": false,
          "legendFormat": "p95 GetCart",
          "range": true,
          "refId": "A",
          "useBackend": false
        }
      ],
      "title": "95th Pct Cart GetCart Latency with Exemplars",
      "type": "timeseries"
    },
    {
      "datasource": {
        "type": "prometheus",
        "uid": "webstore-metrics"
      },
      "fieldConfig": {
        "defaults": {
          "custom": {
            "hideFrom": {
              "legend": false,
              "tooltip": false,
              "viz": false
            },
            "scaleDistribution": {
              "type": "linear"
            }
          }
        },
        "overrides": []
      },
      "gridPos": {
        "h": 9,
        "w": 24,
        "x": 0,
        "y": 1
      },
      "id": 2,
      "interval": "2m",
      "options": {
        "calculate": false,
        "cellGap": 1,
        "color": {
          "exponent": 0.5,
          "fill": "dark-orange",
          "mode": "scheme",
          "reverse": false,
          "scale": "exponential",
          "scheme": "Spectral",
          "steps": 64
        },
        "exemplars": {
          "color": "rgba(255,0,255,0.7)"
        },
        "filterValues": {
          "le": 1e-9
        },
        "legend": {
          "show": true
        },
        "rowsFrame": {
          "layout": "auto"
        },
        "tooltip": {
          "mode": "single",
          "showColorScale": false,
          "yHistogram": false
        },
        "yAxis": {
          "axisPlacement": "left",
          "reverse": false
        }
      },
      "pluginVersion": "11.3.0",
      "targets": [
        {
          "disableTextWrap": false,
          "editorMode": "builder",
          "exemplar": true,
          "expr": "sum by(le) (rate(app_cart_get_cart_latency_bucket[$__rate_interval]))",
          "format": "heatmap",
          "fullMetaSearch": false,
          "includeNullMetadata": false,
          "instant": true,
          "legendFormat": "{{le}}",
          "range": true,
          "refId": "A",
          "useBackend": false
        }
      ],
      "title": "GetCart Latency Heatmap with Exemplars",
      "type": "heatmap"
    },
    {
      "collapsed": false,
      "gridPos": {
        "h": 1,
        "w": 24,
        "x": 0,
        "y": 20
      },
      "id": 3,
      "panels": [],
      "title": "AddItem Exemplars",
      "type": "row"
    },
    {
      "datasource": {
        "type": "prometheus",
        "uid": "webstore-metrics"
      },
      "fieldConfig": {
        "defaults": {
          "custom": {
            "hideFrom": {
              "legend": false,
              "tooltip": false,
              "viz": false
            },
            "scaleDistribution": {
              "type": "linear"
            }
          }
        },
        "overrides": []
      },
      "gridPos": {
        "h": 9,
        "w": 24,
        "x": 0,
        "y": 21
      },
      "id": 6,
      "interval": "2m",
      "options": {
        "calculate": false,
        "cellGap": 1,
        "color": {
          "exponent": 0.5,
          "fill": "dark-orange",
          "mode": "scheme",
          "reverse": false,
          "scale": "exponential",
          "scheme": "Spectral",
          "steps": 64
        },
        "exemplars": {
          "color": "rgba(255,0,255,0.7)"
        },
        "filterValues": {
          "le": 1e-9
        },
        "legend": {
          "show": true
        },
        "rowsFrame": {
          "layout": "auto"
        },
        "tooltip": {
          "mode": "single",
          "showColorScale": false,
          "yHistogram": false
        },
        "yAxis": {
          "axisPlacement": "left",
          "reverse": false
        }
      },
      "pluginVersion": "11.3.0",
      "targets": [
        {
          "disableTextWrap": false,
          "editorMode": "builder",
          "exemplar": true,
          "expr": "sum by(le) (rate(app_cart_add_item_latency_bucket[$__rate_interval]))",
          "format": "heatmap",
          "fullMetaSearch": false,
          "includeNullMetadata": false,
          "instant": true,
          "legendFormat": "{{le}}",
          "range": true,
          "refId": "A",
          "useBackend": false
        }
      ],
      "title": "AddItem Latency Heatmap with Exemplars",
      "type": "heatmap"
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
        "h": 10,
        "w": 24,
        "x": 0,
        "y": 30
      },
      "id": 1,
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
          "disableTextWrap": false,
          "editorMode": "builder",
          "exemplar": true,
          "expr": "histogram_quantile(0.95, sum by(le) (rate(app_cart_add_item_latency_bucket[$__rate_interval])))",
          "fullMetaSearch": false,
          "includeNullMetadata": false,
          "legendFormat": "p95 AddItem",
          "range": true,
          "refId": "A",
          "useBackend": false
        }
      ],
      "title": "95th Pct Cart AddItem Latency with Exemplars",
      "type": "timeseries"
    }
  ],
  "preload": false,
  "schemaVersion": 40,
  "tags": [],
  "templating": {
    "list": []
  },
  "time": {
    "from": "now-1h",
    "to": "now"
  },
  "timepicker": {},
  "timezone": "browser",
  "title": "Cart Service Exemplars",
  "uid": "ce6sd46kfkglca",
  "version": 1,
  "weekStart": ""
}
