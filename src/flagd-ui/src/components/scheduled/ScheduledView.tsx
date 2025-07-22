// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
"use client";
import React, { useEffect, useState, useCallback } from "react";
import { useLoading } from "../Layout";

interface FlagConfig {
  description: string;
  state: string;
  variants: Record<string, any>;
  defaultVariant: string;
}

interface ConfigFile {
  $schema: string;
  flags: Record<string, FlagConfig>;
}

interface SchedulerConfig {
  interval: number; // in minutes
  seed?: string;
  enabledFlags: string[];
  isRunning: boolean;
}

interface SchedulerState {
  config: SchedulerConfig;
  currentCycle: number;
  lastUpdate: Date | null;
  schedulerInterval: number | null;
}

export default function ScheduledView() {
  const [flagData, setFlagData] = useState<ConfigFile | null>(null);
  const [schedulerState, setSchedulerState] = useState<SchedulerState>({
    config: {
      interval: 30, // default 30 minutes
      seed: "",
      enabledFlags: [],
      isRunning: false,
    },
    currentCycle: 0,
    lastUpdate: null,
    schedulerInterval: null,
  });

  const { setIsLoading } = useLoading();

  // Load flag data on component mount
  useEffect(() => {
    const readFile = async () => {
      try {
        const response = await fetch("/feature/api/read-file", {
          method: "GET",
          headers: { "Content-Type": "application/json" },
        });
        const data = await response.json();
        setFlagData(data);
      } catch (err) {
        console.error("Error loading flag data:", err);
      }
    };
    readFile();
  }, []);

  // Cleanup interval on unmount
  useEffect(() => {
    return () => {
      if (schedulerState.schedulerInterval) {
        clearInterval(schedulerState.schedulerInterval);
      }
    };
  }, [schedulerState.schedulerInterval]);

  const updateFlagData = useCallback(async (updatedFlags: ConfigFile) => {
    try {
      setIsLoading(true);
      await fetch("/feature/api/write-to-file", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ data: updatedFlags }),
      });
      setFlagData(updatedFlags);
      setIsLoading(false);
    } catch (err) {
      setIsLoading(false);
      console.error("Error updating flags:", err);
    }
  }, [setIsLoading]);

  const createSeededRandom = (seed: string) => {
    let hash = 0;
    if (seed.length === 0) return Math.random;
    for (let i = 0; i < seed.length; i++) {
      const char = seed.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash; // Convert to 32bit integer
    }
    
    return () => {
      hash = (hash * 9301 + 49297) % 233280;
      return hash / 233280;
    };
  };

  const performChaosIteration = useCallback(() => {
    if (!flagData || schedulerState.config.enabledFlags.length === 0) {
      return;
    }

    const random = schedulerState.config.seed 
      ? createSeededRandom(schedulerState.config.seed + schedulerState.currentCycle.toString())
      : Math.random;

    const updatedFlagData = { ...flagData };
    
    // For each enabled flag, randomly decide whether to toggle it
    schedulerState.config.enabledFlags.forEach((flagId) => {
      if (updatedFlagData.flags[flagId]) {
        const variants = Object.keys(updatedFlagData.flags[flagId].variants);
        if (variants.length > 0) {
          // 50% chance to toggle, then randomly select from variants
          if (random() < 0.5) {
            const randomVariantIndex = Math.floor(random() * variants.length);
            const selectedVariant = variants[randomVariantIndex];
            updatedFlagData.flags[flagId].defaultVariant = selectedVariant;
          }
        }
      }
    });

    updateFlagData(updatedFlagData);
    
    setSchedulerState(prev => ({
      ...prev,
      currentCycle: prev.currentCycle + 1,
      lastUpdate: new Date(),
    }));

    console.log(`Chaos iteration ${schedulerState.currentCycle + 1} completed at ${new Date().toISOString()}`);
  }, [flagData, schedulerState.config.enabledFlags, schedulerState.config.seed, schedulerState.currentCycle, updateFlagData]);

  const startScheduler = () => {
    if (schedulerState.config.enabledFlags.length === 0) {
      alert("Please select at least one flag to include in the chaos schedule.");
      return;
    }

    const intervalMs = schedulerState.config.interval * 60 * 1000; // convert minutes to milliseconds
    const interval = setInterval(performChaosIteration, intervalMs);

    setSchedulerState(prev => ({
      ...prev,
      config: { ...prev.config, isRunning: true },
      schedulerInterval: interval as unknown as number,
      currentCycle: 0,
      lastUpdate: null,
    }));

    console.log(`Chaos scheduler started with ${schedulerState.config.interval} minute intervals`);
  };

  const stopScheduler = () => {
    if (schedulerState.schedulerInterval) {
      clearInterval(schedulerState.schedulerInterval);
    }

    setSchedulerState(prev => ({
      ...prev,
      config: { ...prev.config, isRunning: false },
      schedulerInterval: null,
    }));

    console.log("Chaos scheduler stopped");
  };

  const handleIntervalChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const interval = parseInt(e.target.value, 10);
    if (interval > 0) {
      setSchedulerState(prev => ({
        ...prev,
        config: { ...prev.config, interval },
      }));
    }
  };

  const handleSeedChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSchedulerState(prev => ({
      ...prev,
      config: { ...prev.config, seed: e.target.value },
    }));
  };

  const handleFlagToggle = (flagId: string) => {
    setSchedulerState(prev => {
      const enabledFlags = prev.config.enabledFlags.includes(flagId)
        ? prev.config.enabledFlags.filter(id => id !== flagId)
        : [...prev.config.enabledFlags, flagId];
      
      return {
        ...prev,
        config: { ...prev.config, enabledFlags },
      };
    });
  };

  const runSingleIteration = () => {
    performChaosIteration();
  };

  if (!flagData) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="text-gray-300">Loading flag data...</div>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-gray-100 mb-4">Chaos Scheduler</h2>
        <p className="text-gray-300 mb-6">
          Configure automated chaos engineering by randomly toggling feature flags at specified intervals.
        </p>
      </div>

      {/* Configuration Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
        {/* Scheduler Configuration */}
        <div className="bg-gray-800 rounded-lg p-6">
          <h3 className="text-lg font-semibold text-gray-100 mb-4">Configuration</h3>
          
          {/* Interval */}
          <div className="mb-4">
            <label htmlFor="interval" className="block text-sm font-medium text-gray-300 mb-2">
              Interval (minutes) *
            </label>
            <input
              type="number"
              id="interval"
              min="1"
              value={schedulerState.config.interval}
              onChange={handleIntervalChange}
              disabled={schedulerState.config.isRunning}
              className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-md text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
            />
            <p className="text-xs text-gray-400 mt-1">How often to randomly toggle flags</p>
          </div>

          {/* Seed */}
          <div className="mb-4">
            <label htmlFor="seed" className="block text-sm font-medium text-gray-300 mb-2">
              Seed (optional)
            </label>
            <input
              type="text"
              id="seed"
              value={schedulerState.config.seed}
              onChange={handleSeedChange}
              disabled={schedulerState.config.isRunning}
              placeholder="Enter a seed for reproducible randomness"
              className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-md text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
            />
            <p className="text-xs text-gray-400 mt-1">
              Use the same seed to get reproducible chaos patterns. Leave empty for true randomness.
            </p>
          </div>

          {/* Controls */}
          <div className="flex gap-3">
            <button
              onClick={schedulerState.config.isRunning ? stopScheduler : startScheduler}
              className={`px-4 py-2 rounded-md font-medium transition-colors duration-200 ${
                schedulerState.config.isRunning
                  ? "bg-red-600 hover:bg-red-700 text-white"
                  : "bg-green-600 hover:bg-green-700 text-white"
              }`}
            >
              {schedulerState.config.isRunning ? "Stop Scheduler" : "Start Scheduler"}
            </button>
            
            <button
              onClick={runSingleIteration}
              disabled={schedulerState.config.isRunning || schedulerState.config.enabledFlags.length === 0}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 disabled:opacity-50 text-white rounded-md font-medium transition-colors duration-200"
            >
              Run Once
            </button>
          </div>
        </div>

        {/* Status */}
        <div className="bg-gray-800 rounded-lg p-6">
          <h3 className="text-lg font-semibold text-gray-100 mb-4">Status</h3>
          
          <div className="space-y-3">
            <div>
              <span className="text-sm text-gray-400">Status: </span>
              <span className={`text-sm font-medium ${
                schedulerState.config.isRunning ? "text-green-400" : "text-gray-300"
              }`}>
                {schedulerState.config.isRunning ? "Running" : "Stopped"}
              </span>
            </div>
            
            <div>
              <span className="text-sm text-gray-400">Enabled Flags: </span>
              <span className="text-sm text-gray-300">{schedulerState.config.enabledFlags.length}</span>
            </div>
            
            <div>
              <span className="text-sm text-gray-400">Cycles Completed: </span>
              <span className="text-sm text-gray-300">{schedulerState.currentCycle}</span>
            </div>
            
            {schedulerState.lastUpdate && (
              <div>
                <span className="text-sm text-gray-400">Last Update: </span>
                <span className="text-sm text-gray-300">
                  {schedulerState.lastUpdate.toLocaleTimeString()}
                </span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Flag Selection */}
      <div className="bg-gray-800 rounded-lg p-6">
        <h3 className="text-lg font-semibold text-gray-100 mb-4">Feature Flags</h3>
        <p className="text-sm text-gray-400 mb-4">
          Select which flags should be included in the chaos schedule:
        </p>
        
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Object.entries(flagData.flags).map(([flagId, flagConfig]) => (
            <div
              key={flagId}
              className="flex items-start space-x-3 p-4 bg-gray-700 rounded-lg"
            >
              <input
                type="checkbox"
                id={`flag-${flagId}`}
                checked={schedulerState.config.enabledFlags.includes(flagId)}
                onChange={() => handleFlagToggle(flagId)}
                disabled={schedulerState.config.isRunning}
                className="mt-1 h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-600 rounded disabled:opacity-50"
              />
              <div className="flex-1">
                <label
                  htmlFor={`flag-${flagId}`}
                  className={`block text-sm font-medium cursor-pointer ${
                    schedulerState.config.isRunning ? "text-gray-400" : "text-gray-200"
                  }`}
                >
                  {flagId}
                </label>
                <p className="text-xs text-gray-400 mt-1">{flagConfig.description}</p>
                <p className="text-xs text-gray-500 mt-1">
                  Current: {flagConfig.defaultVariant}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
