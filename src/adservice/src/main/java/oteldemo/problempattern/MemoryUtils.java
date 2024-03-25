/*
* Copyright The OpenTelemetry Authors
* SPDX-License-Identifier: Apache-2.0
*/

package oteldemo.problempattern;

import java.lang.management.MemoryMXBean;
import java.lang.management.MemoryUsage;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;


/**
 * This class provides JVM heap related utility methods.
*/
public class MemoryUtils {

    private static final Logger logger = LogManager.getLogger(MemoryUtils.class.getName());

    private static final long NO_HEAP_LIMIT = -1;

    private final MemoryMXBean memoryBean;

    /**
     * @param memoryBean defines which {@link MemoryMXBean} is to use
    */
    public MemoryUtils(MemoryMXBean memoryBean) {
        this.memoryBean = memoryBean;
    }


    /**
     * @return The current heap usage as a decimal number between 0.0 and 1.0.
    *         That is, if the returned value is 0.85, 85% of the max heap is used.
    *
    *         If no max heap is set, the method returns -1.0.
    */
    public double getHeapUsage() {
        MemoryUsage heapProps = memoryBean.getHeapMemoryUsage();
        long heapUsed = heapProps.getUsed();
        long heapMax = heapProps.getMax();

        if (heapMax == NO_HEAP_LIMIT) {
            if (logger.isDebugEnabled()) {
            logger.debug("No maximum heap is set");
            }
            return NO_HEAP_LIMIT;
        }


        double heapUsage = (double) heapUsed / heapMax;
        if (logger.isDebugEnabled()) {
            logger.debug("Current heap usage is {0} percent" + (heapUsage * 100));
        }
        return heapUsage;
    }

    /**
     * see {@link MemoryMXBean#getObjectPendingFinalizationCount()}
    */
    public int getObjectPendingFinalizationCount() {
        return memoryBean.getObjectPendingFinalizationCount();
    }
}
