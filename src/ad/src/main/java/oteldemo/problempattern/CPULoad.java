/*
* Copyright The OpenTelemetry Authors
* SPDX-License-Identifier: Apache-2.0
*/
package oteldemo.problempattern;

import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

import io.grpc.ManagedChannelBuilder;

import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

/**
 * This class is designed to simulate a high CPU load scenario.
 * It contains methods to start and stop a specified number of worker threads designed to
 * perform CPU-intensive calculations.
 */
public class CPULoad {
    private static final Logger logger = LogManager.getLogger(CPULoad.class.getName());
    private static final int THREAD_COUNT = 4;
    private boolean running = false;
    private final List<Logarithmizer> runningWorkers = new ArrayList<>();
    
    private static CPULoad instance;

    /**
     * Singleton pattern to get the instance of CPULoad.
     * @return The singleton instance of CPULoad.
     */
    public static CPULoad getInstance() {
        if (instance == null) {
            instance = new CPULoad();
        }
        return instance;
    }

    /**
     * Starts or stops the CPU load generation based on the input parameter.
     * If enabled, it launches worker threads. If disabled, it stops any running threads.
     * 
     * @param enabled Flag to start (true) or stop (false) the CPU load simulation.
     */
    public void execute(Boolean enabled) {
        if (enabled) {
            logger.info("High CPU-Load problempattern enabled");
            if (!running) {
                spawnLoadWorkers(THREAD_COUNT);
                running = true;
            }
        } else {
            running = false;
            stopWorkers();
        }
    }

    /**
     * Creates and starts a specified number of Logarithmizer threads to simulate CPU load.
     * 
     * @param threadCount The number of threads to be started.
     */
    private void spawnLoadWorkers(int threadCount) {
        synchronized(runningWorkers) {
            for (int i = 0; i < threadCount; i++) {
                Logarithmizer logarithmizer = new Logarithmizer();
                Thread thread = new Thread(logarithmizer);
                thread.setDaemon(true);
                thread.start();
                runningWorkers.add(logarithmizer);
            }
        }
    }

    /**
     * Signals all running Logarithmizer threads to stop and clears the list of running workers.
     */
    private void stopWorkers() {
        synchronized(runningWorkers) {
            for (Logarithmizer logarithmizer : runningWorkers) {
                logarithmizer.setShouldRun(false);
            }
            runningWorkers.clear();
        }
    }

    /**
     * Inner class representing a worker focused on calculating logarithms to consume CPU resources.
     */
    private static class Logarithmizer implements Runnable {

        private volatile boolean shouldRun = true;

        /**
         * Continuously calculates the logarithm of the current system time until
         * requested to stop.
         */
        @Override
        public void run() {
            while (shouldRun) {
                Math.log(System.currentTimeMillis());
            }
        }

        /**
         * Sets the shouldRun flag to control whether this Logarithmizer should continue
         * to run.
         *
         * @param shouldRun A boolean flag to continue (true) or stop (false) the logarithm computation.
         */
        public void setShouldRun(boolean shouldRun) {
            this.shouldRun = shouldRun;
       }
    }
}
