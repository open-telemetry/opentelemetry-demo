/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */

package frauddetection

import io.opentelemetry.api.GlobalOpenTelemetry
import io.opentelemetry.api.trace.SpanKind
import io.opentelemetry.api.trace.StatusCode
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
import dev.openfeature.sdk.Client
import dev.openfeature.sdk.EvaluationContext
import dev.openfeature.sdk.ImmutableContext
import dev.openfeature.sdk.Value
import dev.openfeature.sdk.OpenFeatureAPI

const val topic = "orders"
const val groupID = "fraud-detection"

private val logger: Logger = LogManager.getLogger(groupID)
private val tracer = GlobalOpenTelemetry.getTracer(groupID)
private val kafkaTraceContextGetter = object : TextMapGetter<ConsumerRecord<String, ByteArray>> {
    override fun keys(carrier: ConsumerRecord<String, ByteArray>): Iterable<String> =
        carrier.headers().map { header -> header.key() }

    override fun get(carrier: ConsumerRecord<String, ByteArray>?, key: String): String? {
        val header = carrier?.headers()?.lastHeader(key) ?: return null
        return header.value()?.toString(Charsets.UTF_8)
    }
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
    // Read from the start of the topic so a freshly-joined consumer group still
    // processes orders produced before it finished joining, matching the
    // accounting consumer's behaviour. Without this the Kafka default of
    // "latest" silently drops those orders, so fraud-detection may emit no
    // telemetry on a quiet/cold start.
    props[AUTO_OFFSET_RESET_CONFIG] = "earliest"
    val bootstrapServers = System.getenv("KAFKA_ADDR")
    if (bootstrapServers == null) {
        println("KAFKA_ADDR is not supplied")
        exitProcess(1)
    }
    props[BOOTSTRAP_SERVERS_CONFIG] = bootstrapServers
    val consumer = KafkaConsumer<String, ByteArray>(props).apply {
        subscribe(listOf(topic))
    }

    var totalCount = 0L

    consumer.use {
        while (true) {
            totalCount = consumer
                .poll(ofMillis(100))
                .fold(totalCount) { accumulator, record ->
                    processRecord(accumulator, record)
                }
        }
    }
}

fun processRecord(accumulator: Long, record: ConsumerRecord<String, ByteArray>): Long {
    val parentContext = GlobalOpenTelemetry.getPropagators()
        .textMapPropagator
        .extract(Context.current(), record, kafkaTraceContextGetter)
    val span = tracer.spanBuilder("orders process")
        .setSpanKind(SpanKind.CONSUMER)
        .setParent(parentContext)
        .setAttribute("messaging.system", "kafka")
        .setAttribute("messaging.destination.name", record.topic())
        .setAttribute("messaging.operation", "process")
        .setAttribute("messaging.kafka.consumer.group", groupID)
        .setAttribute("messaging.kafka.partition", record.partition().toLong())
        .setAttribute("messaging.kafka.message.offset", record.offset())
        .startSpan()
    val scope = span.makeCurrent()

    try {
        val newCount = accumulator + 1
        if (getFeatureFlagValue("kafkaQueueProblems") > 0) {
            logger.info("FeatureFlag 'kafkaQueueProblems' is enabled, sleeping 1 second")
            Thread.sleep(1000)
        }
        val orders = OrderResult.parseFrom(record.value())
        span.setAttribute("demo.order.id", orders.orderId)
        logger.info("Consumed record with orderId: ${orders.orderId}, and updated total count to: $newCount")
        return newCount
    } catch (e: Throwable) {
        span.recordException(e)
        span.setStatus(StatusCode.ERROR)
        throw e
    } finally {
        scope.close()
        span.end()
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
