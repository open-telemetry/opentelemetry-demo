/*
* Copyright The OpenTelemetry Authors
* SPDX-License-Identifier: Apache-2.0
*/

package oteldemo.problempattern;

import java.lang.management.ManagementFactory;
import java.util.concurrent.TimeUnit;

import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

/**
 * The GarbageCollectionTrigger class is responsible for triggering manual garbage collection
* at specified intervals to simulate memory pressure and measure the impact on performance.
*/
public class GarbageCollectionTrigger {
    private static final Logger logger = LogManager.getLogger(GarbageCollectionTrigger.class.getName());

    private final long gc_delay;
    private final int finalize_delay;
    private final int maxObjects;

    private long lastGC = 0;

    private final MemoryUtils memUtils;

    /**
     * Constructs a new GarbageCollectionTrigger with default values.
    */
    public GarbageCollectionTrigger() {
        memUtils = new MemoryUtils(ManagementFactory.getMemoryMXBean());
        gc_delay = TimeUnit.SECONDS.toMillis(10);
        finalize_delay = 500;
        maxObjects = 500000;
    }

    /**
     * Triggers manual garbage collection at specified intervals and measures the impact on performance.
    * It creates Entry objects to fill up memory and initiates garbage collection.
    */
    public void doExecute() {
        if (System.currentTimeMillis() - lastGC > gc_delay) {
            logger.info("Triggering a manual garbage collection, next one in " + (gc_delay/1000) + " seconds.");
            // clear old data, we want to clear old Entry objects, because their finalization is expensive
            System.gc();

            long total = 0;
            for (int i = 0; i < 10; i++) {
                while (memUtils.getHeapUsage() < 0.9 && memUtils.getObjectPendingFinalizationCount() < maxObjects) {
                    new Entry();
                }
                long start = System.currentTimeMillis();
                System.gc();
                total += System.currentTimeMillis() - start;
            }
            logger.info("The artificially triggered GCs took: " + total + " ms");
            lastGC = System.currentTimeMillis();
        }

    }

    /**
     * The Entry class represents objects created for the purpose of triggering garbage collection.
    */
    private class Entry {
        /**
         * Overrides the finalize method to introduce a delay, simulating finalization during garbage collection.
        *
        * @throws Throwable If an exception occurs during finalization.
        */
        @SuppressWarnings("removal")
        @Override
        protected void finalize() throws Throwable {
            TimeUnit.MILLISECONDS.sleep(finalize_delay);
            super.finalize();
        }
    }
}
