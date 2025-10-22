/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */

package frauddetection

import org.apache.logging.log4j.LogManager
import org.apache.logging.log4j.Logger
import oteldemo.Demo.OrderResult
import oteldemo.Demo.Money
import oteldemo.Demo.Address
import kotlin.random.Random

/**
 * Mutates orders to trigger fraud detection alerts for demo purposes.
 * This helps demonstrate fraud detection capabilities by randomly modifying
 * order attributes to match fraud patterns.
 */
class OrderMutator {
    private val logger: Logger = LogManager.getLogger(OrderMutator::class.java)

    companion object {
        // High-risk shipping addresses for demos
        private val PO_BOX_ADDRESSES = listOf(
            "P.O. Box 12345",
            "PO Box 98765",
            "P.O. Box 54321",
            "PO BOX 11111"
        )

        private val SUSPICIOUS_CITIES = listOf(
            "Unknown City",
            "Test City",
            "Fraud Town"
        )
    }

    /**
     * Randomly mutates an order to trigger fraud alerts.
     * Returns the mutated order if mutation occurred, otherwise returns original.
     * @param order The original order
     * @param mutationPercentage The percentage (0-100) chance to mutate
     */
    fun mutateOrder(order: OrderResult, mutationPercentage: Int): OrderResult {
        // Random chance to mutate based on percentage
        if (mutationPercentage <= 0 || Random.nextInt(100) >= mutationPercentage) {
            return order
        }

        val mutationType = Random.nextInt(4)
        val builder = order.toBuilder()

        when (mutationType) {
            0 -> mutateToHighValue(builder)
            1 -> mutateToVeryHighValue(builder)
            2 -> mutateToLargeQuantity(builder)
            3 -> mutateToPOBoxAddress(builder)
        }

        val mutatedOrder = builder.build()
        logger.info("Order ${order.orderId} mutated (type=$mutationType) to trigger fraud detection")

        return mutatedOrder
    }

    /**
     * Mutate shipping cost to high value ($50-$99)
     */
    private fun mutateToHighValue(builder: OrderResult.Builder) {
        val highValue = Random.nextLong(50, 100)
        val money = Money.newBuilder()
            .setCurrencyCode("USD")
            .setUnits(highValue)
            .setNanos(Random.nextInt(0, 1000000))
            .build()

        builder.shippingCost = money
        logger.debug("Mutated to high value: \$${highValue}")
    }

    /**
     * Mutate shipping cost to very high value ($100-$500)
     */
    private fun mutateToVeryHighValue(builder: OrderResult.Builder) {
        val veryHighValue = Random.nextLong(100, 501)
        val money = Money.newBuilder()
            .setCurrencyCode("USD")
            .setUnits(veryHighValue)
            .setNanos(Random.nextInt(0, 1000000))
            .build()

        builder.shippingCost = money
        logger.debug("Mutated to very high value: \$${veryHighValue}")
    }

    /**
     * Mutate items count to large quantity (11-30 items)
     * We duplicate existing items to increase the count
     */
    private fun mutateToLargeQuantity(builder: OrderResult.Builder) {
        val currentItems = builder.itemsList.toMutableList()
        if (currentItems.isEmpty()) {
            // Can't mutate if there are no items
            return
        }

        val targetQuantity = Random.nextInt(11, 31)

        // Duplicate items until we reach target quantity
        while (builder.itemsCount < targetQuantity) {
            val itemToDuplicate = currentItems.random()
            builder.addItems(itemToDuplicate)
        }

        logger.debug("Mutated to large quantity: ${builder.itemsCount} items")
    }

    /**
     * Mutate shipping address to PO Box
     */
    private fun mutateToPOBoxAddress(builder: OrderResult.Builder) {
        if (builder.hasShippingAddress()) {
            val originalAddress = builder.shippingAddress
            val poBoxAddress = Address.newBuilder()
                .setStreetAddress(PO_BOX_ADDRESSES.random())
                .setCity(SUSPICIOUS_CITIES.random())
                .setState(originalAddress.state)
                .setCountry(originalAddress.country)
                .setZipCode(originalAddress.zipCode)
                .build()

            builder.shippingAddress = poBoxAddress
            logger.debug("Mutated to PO Box address: ${poBoxAddress.streetAddress}")
        }
    }

}
