/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */

package frauddetection

import io.opentelemetry.api.GlobalOpenTelemetry
import io.opentelemetry.api.common.AttributeKey
import io.opentelemetry.api.common.Attributes
import io.opentelemetry.api.metrics.LongCounter
import io.opentelemetry.api.trace.SpanKind
import io.opentelemetry.api.trace.StatusCode
import io.opentelemetry.api.trace.Tracer
import io.opentelemetry.context.Context
import io.opentelemetry.context.propagation.TextMapGetter
import org.apache.kafka.clients.consumer.ConsumerConfig.*
import org.apache.kafka.clients.consumer.ConsumerRecord
import org.apache.kafka.clients.consumer.KafkaConsumer
import org.apache.kafka.common.serialization.ByteArrayDeserializer
import org.apache.kafka.common.serialization.StringDeserializer
import org.apache.logging.log4j.LogManager
import org.apache.logging.log4j.Logger
import oteldemo.Demo.*
import java.time.Duration.ofMillis
import java.util.*
import kotlin.system.exitProcess
import dev.openfeature.contrib.providers.flagd.FlagdOptions
import dev.openfeature.contrib.providers.flagd.FlagdProvider
import dev.openfeature.sdk.ImmutableContext
import dev.openfeature.sdk.Value
import dev.openfeature.sdk.OpenFeatureAPI

const val topic = "orders"
const val groupID = "fraud-detection"

private val logger: Logger = LogManager.getLogger(groupID)

// CUP-1 post-checkout: Kafka header getter for W3C trace context propagation
private val kafkaHeaderGetter = object : TextMapGetter<ConsumerRecord<*, *>> {
    override fun keys(carrier: ConsumerRecord<*, *>): Iterable<String> =
        carrier.headers().map { it.key() }

    override fun get(carrier: ConsumerRecord<*, *>?, key: String): String? =
        carrier?.headers()?.lastHeader(key)?.value()?.toString(Charsets.UTF_8)
}

fun main() {
    val options = FlagdOptions.builder()
    .withGlobalTelemetry(true)
    .build()
    val flagdProvider = FlagdProvider(options)
    OpenFeatureAPI.getInstance().setProvider(flagdProvider)

    val props = Properties()
    props[KEY_DESERIALIZER_CLASS_CONFIG] = StringDeserializer::class.java.name
    props[VALUE_DESERIALIZER_CLASS_CONFIG] = ByteArrayDeserializer::class.java.name
    props[GROUP_ID_CONFIG] = groupID
    val bootstrapServers = System.getenv("KAFKA_ADDR")
    if (bootstrapServers == null) {
        println("KAFKA_ADDR is not supplied")
        exitProcess(1)
    }
    props[BOOTSTRAP_SERVERS_CONFIG] = bootstrapServers
    val consumer = KafkaConsumer<String, ByteArray>(props).apply {
        subscribe(listOf(topic))
    }

    // CUP-1: OTel tracer and fraud detection counter
    val otel = GlobalOpenTelemetry.get()
    val tracer: Tracer = otel.getTracer("fraud-detection")
    val meter = otel.getMeter("fraud-detection")
    val fraudChecksCounter: LongCounter = meter.counterBuilder("app.fraud.checks")
        .setDescription("Number of orders inspected by the fraud detection service")
        .setUnit("{order}")
        .build()

    var totalCount = 0L

    consumer.use {
        while (true) {
            totalCount = consumer
                .poll(ofMillis(100))
                .fold(totalCount) { accumulator, record ->
                    val newCount = accumulator + 1

                    // Extract upstream W3C trace context from Kafka headers
                    val parentContext = otel.propagators.textMapPropagator
                        .extract(Context.current(), record, kafkaHeaderGetter)

                    // Create a consumer span linked to the checkout producer span
                    val span = tracer.spanBuilder("$topic process")
                        .setParent(parentContext)
                        .setSpanKind(SpanKind.CONSUMER)
                        .setAttribute("messaging.system", "kafka")
                        .setAttribute("messaging.operation", "process")
                        .setAttribute("messaging.destination.name", topic)
                        .setAttribute("messaging.consumer.group.name", groupID)
                        .startSpan()

                    val scope = span.makeCurrent()
                    try {
                        if (getFeatureFlagValue("kafkaQueueProblems") > 0) {
                            logger.info("FeatureFlag 'kafkaQueueProblems' is enabled, sleeping 1 second")
                            Thread.sleep(1000)
                        }
                        val orders = OrderResult.parseFrom(record.value())
                        span.setAttribute("app.order.id", orders.orderId)
                        span.setAttribute("app.order.items.count", orders.itemsCount.toLong())
                        logger.info("Consumed record with orderId: ${orders.orderId}, and updated total count to: $newCount")

                        // CUP-1: increment fraud check counter
                        fraudChecksCounter.add(1, Attributes.of(
                            AttributeKey.stringKey("app.fraud.result"), "checked"
                        ))
                        span.setStatus(StatusCode.OK)
                    } catch (e: Exception) {
                        span.setStatus(StatusCode.ERROR, e.message ?: "unknown error")
                        span.recordException(e)
                        logger.error("Failed to process order record", e)
                    } finally {
                        scope.close()
                        span.end()
                    }

                    newCount
                }
        }
    }
}

/**
* Retrieves the status of a feature flag from the Feature Flag service.
*
* @param ff The name of the feature flag to retrieve.
* @return `true` if the feature flag is enabled, `false` otherwise or in case of errors.
*/
fun getFeatureFlagValue(ff: String): Int {
    val client = OpenFeatureAPI.getInstance().client
    // TODO: Plumb the actual session ID from the frontend via baggage?
    val uuid = UUID.randomUUID()

    val clientAttrs = mutableMapOf<String, Value>()
    clientAttrs["session"] = Value(uuid.toString())
    client.evaluationContext = ImmutableContext(clientAttrs)
    val intValue = client.getIntegerValue(ff, 0)
    return intValue
}
