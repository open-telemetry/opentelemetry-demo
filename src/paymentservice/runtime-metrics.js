// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
const { metrics } = require('@opentelemetry/api');
const process = require('process');
const v8 = require('v8');
const perf_hooks = require('perf_hooks');
const { monitorEventLoopDelay } = require('perf_hooks');

class RuntimeMetricsCollector {
  constructor(meterName = 'runtime-metrics', collectionIntervalMs = 10000) {
    this.meter = metrics.getMeter(meterName);
    this.collectionIntervalMs = collectionIntervalMs;
    this.minorGcCount = 0;
    this.majorGcCount = 0;
    this.lastGcPause = 0;
    this.heapSizeAfterGc = 0;
    this.collectionInterval = null;
    this.histogram = monitorEventLoopDelay({ resolution: 20 });
    
    this.globalLastState = {
      timestamp: process.hrtime.bigint(),
      count: this.histogram.count,
      sum: this.histogram.mean * this.histogram.count,
      lastCollection: Date.now()
    };

    this.initializeMetrics();
    this.setupGcObserver();
  }

  initializeMetrics() {
    // Initialize all gauge metrics
    this.gcPauseGauge = this.meter.createObservableGauge('nodejs.gc.gcPause', {
      description: 'GC Pause in milliseconds',
      unit: 'ms',
    });

    this.activeHandlesGauge = this.meter.createObservableGauge('nodejs.activeHandles', {
      description: 'Number of active handles',
      unit: '{handles}',
    });

    this.activeRequestsGauge = this.meter.createObservableGauge('nodejs.activeRequests', {
      description: 'Number of active requests',
      unit: '{requests}',
    });

    this.minorGcsGauge = this.meter.createObservableGauge('nodejs.gc.minorGcs', {
      description: 'Number of minor GCs',
      unit: '{gcs}',
    });

    this.majorGcsGauge = this.meter.createObservableGauge('nodejs.gc.majorGcs', {
      description: 'Number of major GCs',
      unit: '{gcs}',
    });

    this.rssGauge = this.meter.createObservableGauge('nodejs.memory.rss', {
      description: 'Resident Set Size',
      unit: 'bytes',
    });

    this.heapUsedGauge = this.meter.createObservableGauge('nodejs.memory.heapUsed', {
      description: 'Heap Size Used',
      unit: 'bytes',
    });

    this.heapSizeAfterGcGauge = this.meter.createObservableGauge('nodejs.gc.usedHeapSizeAfterGc', {
      description: 'Heap Size After GC',
      unit: 'bytes',
    });

    this.eventLoopMetrics = {
      max: this.meter.createObservableGauge('nodejs.libuv.max', {
        description: 'Longest time spent in a single loop',
        unit: 'ms',
      }),
      sum: this.meter.createObservableGauge('nodejs.libuv.sum', {
        description: 'Total time spent in loop',
        unit: 'ms',
      }),
      lag: this.meter.createObservableGauge('nodejs.libuv.lag', {
        description: 'Event loop lag',
        unit: 'ms',
      }),
      count: this.meter.createObservableGauge('nodejs.libuv.num', {
        description: 'Loops per second',
        unit: '{loops}',
      })
    };

    this.heapSpacesMetrics = {
      used: this.meter.createObservableGauge('nodejs.heapSpaces.used', {
        description: 'Heap Spaces Used',
        unit: 'bytes',
      }),
      available: this.meter.createObservableGauge('nodejs.heapSpaces.available', {
        description: 'Heap Spaces Available',
        unit: 'bytes',
      }),
      current: this.meter.createObservableGauge('nodejs.heapSpaces.current', {
        description: 'Heap Spaces Current',
        unit: 'bytes',
      }),
      physical: this.meter.createObservableGauge('nodejs.heapSpaces.physical', {
        description: 'Heap Spaces Physical',
        unit: 'bytes',
      })
    };
  }

  setupGcObserver() {
    const obs = new perf_hooks.PerformanceObserver((list) => {
      const entries = list.getEntries();
      entries.forEach((entry) => {
        if (entry.kind === perf_hooks.constants.NODE_PERFORMANCE_GC_MAJOR) {
          this.majorGcCount++;
        } else {
          this.minorGcCount++;
        }
        this.lastGcPause = entry.duration;
        this.heapSizeAfterGc = process.memoryUsage().heapUsed;
      });
    });

    obs.observe({ entryTypes: ['gc'], buffered: true });
  }

  collectEventLoopMetrics() {
    const attributes = { type: 'loops' };
    const now = Date.now();

    this.eventLoopMetrics.max.addCallback((result) => {
      const maxValue = Math.round(this.histogram.max / 1e6 * 1000) / 1000;
      result.observe(maxValue, attributes);
    });

    this.eventLoopMetrics.lag.addCallback((result) => {
      const lagValue = Math.round(this.histogram.mean / 1e6 * 1000) / 1000;
      result.observe(lagValue, attributes);
    });

    this.eventLoopMetrics.sum.addCallback((result) => {
      const currentState = {
        timestamp: process.hrtime.bigint(),
        count: this.histogram.count,
        sum: this.histogram.mean * this.histogram.count
      };

      const deltaTime = Number(currentState.timestamp - this.globalLastState.timestamp) / 1e9;
      const deltaSum = (currentState.sum - this.globalLastState.sum) / 1e6;

      if (deltaTime >= 0.9) {
        const timePerSecond = deltaSum / deltaTime;
        result.observe(timePerSecond, attributes);
        this.globalLastState.sum = currentState.sum;
        this.globalLastState.timestamp = currentState.timestamp;
      }
    });

    this.eventLoopMetrics.count.addCallback((result) => {
      const currentCount = this.histogram.count;
      const deltaTime = Number(process.hrtime.bigint() - this.globalLastState.timestamp) / 1e9;
      const deltaCount = currentCount - this.globalLastState.count;

      if (deltaTime >= 0.9) {
        const loopsPerSecond = Math.round(deltaCount / deltaTime);
        result.observe(loopsPerSecond, attributes);
        this.globalLastState.count = currentCount;
      }
    });

    this.globalLastState.lastCollection = now;
  }

  collectMetrics() {
    // Memory metrics
    this.rssGauge.addCallback((result) => {
      const memoryUsage = process.memoryUsage();
      result.observe(memoryUsage.rss, { type: 'rss' });
    });

    this.heapUsedGauge.addCallback((result) => {
      const memoryUsage = process.memoryUsage();
      result.observe(memoryUsage.heapUsed, { type: 'heapUsed' });
    });

    // Active handles and requests
    this.activeHandlesGauge.addCallback((result) => {
      result.observe(process._getActiveHandles().length, { type: 'handles' });
    });

    this.activeRequestsGauge.addCallback((result) => {
      result.observe(process._getActiveRequests().length, { type: 'requests' });
    });

    // GC metrics
    this.minorGcsGauge.addCallback((result) => {
      result.observe(this.minorGcCount, { type: 'minor' });
    });

    this.majorGcsGauge.addCallback((result) => {
      result.observe(this.majorGcCount, { type: 'major' });
    });

    this.gcPauseGauge.addCallback((result) => {
      result.observe(this.lastGcPause, { type: 'pause' });
    });

    this.heapSizeAfterGcGauge.addCallback((result) => {
      result.observe(this.heapSizeAfterGc, { type: 'heapAfterGc' });
    });

    // Heap spaces metrics
    Object.keys(this.heapSpacesMetrics).forEach(metricType => {
      this.heapSpacesMetrics[metricType].addCallback((result) => {
        const heapSpaces = v8.getHeapSpaceStatistics();
        heapSpaces.forEach(space => {
          const attributes = { 
            space: space.space_name,
            metric: metricType 
          };
          
          switch(metricType) {
            case 'used':
              result.observe(space.space_used_size, attributes);
              break;
            case 'available':
              result.observe(space.space_available_size, attributes);
              break;
            case 'current':
              result.observe(space.space_size, attributes);
              break;
            case 'physical':
              result.observe(space.physical_space_size, attributes);
              break;
          }
        });
      });
    });

    this.collectEventLoopMetrics();
  }

  start() {
    this.histogram.enable();
    this.collectionInterval = setInterval(() => {
      this.collectMetrics();
    }, this.collectionIntervalMs);
  }

  stop() {
    if (this.collectionInterval) {
      clearInterval(this.collectionInterval);
      this.collectionInterval = null;
    }
    this.histogram.disable();
  }
}

const runtimeMetrics = new RuntimeMetricsCollector('paymentservice', 10000);
runtimeMetrics.start();

// Handle shutdown gracefully
let sdkInstance = null;

function setSdkInstance(sdk) {
  sdkInstance = sdk;
}

process.on('SIGTERM', () => {
  runtimeMetrics.stop();
  if (sdkInstance) {
    sdkInstance.shutdown()
      .then(() => console.log('SDK shut down successfully'))
      .catch((error) => console.log('Error shutting down SDK', error))
      .finally(() => process.exit(0));
  } else {
    process.exit(0);
  }
});

process.on('SIGINT', () => {
  runtimeMetrics.stop();
  if (sdkInstance) {
    sdkInstance.shutdown()
      .then(() => console.log('SDK shut down successfully'))
      .catch((error) => console.log('Error shutting down SDK', error))
      .finally(() => process.exit(0));
  } else {
    process.exit(0);
  }
});

module.exports = {
  RuntimeMetricsCollector,
  setSdkInstance
};
