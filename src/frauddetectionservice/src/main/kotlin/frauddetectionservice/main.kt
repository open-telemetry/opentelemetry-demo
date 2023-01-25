// Copyright The OpenTelemetry Authors
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

package frauddetectionservice

import hipstershop.Demo.*
import io.opentelemetry.api.trace.Span
import io.sentry.Instrumenter
import io.sentry.Sentry
import io.sentry.SentrySpanStorage
import io.sentry.opentelemetry.OpenTelemetryLinkErrorEventProcessor
import org.apache.kafka.clients.consumer.ConsumerConfig.*
import org.apache.kafka.clients.consumer.KafkaConsumer
import org.apache.kafka.common.serialization.ByteArrayDeserializer
import org.apache.kafka.common.serialization.StringDeserializer
import java.time.Duration.ofMillis
import java.util.*
import kotlin.system.exitProcess

const val topic = "orders"
const val groupID = "frauddetectionservice"

fun main(args: Array<String>) {
    println("Initializing Sentry")

    Sentry.init { options ->
        // NOTE: SENTRY_DSN is injected as environment variable and this config setting picks it up
        options.isEnableExternalConfiguration = true

        // This is required for the Sentry Java Agent to actually perform instrumentation
        options.instrumenter = Instrumenter.OTEL

        // This ensures errors are linked to transactions created from OTEL spans
        options.addEventProcessor(OpenTelemetryLinkErrorEventProcessor())

        // Send all transactions to Sentry
        options.tracesSampleRate = 1.0

        // Enable this to see more logs
        // options.isDebug = true
    }

    println("Sentry initialized")

    val props = Properties()
    props[KEY_DESERIALIZER_CLASS_CONFIG] = StringDeserializer::class.java.name
    props[VALUE_DESERIALIZER_CLASS_CONFIG] = ByteArrayDeserializer::class.java.name
    props[GROUP_ID_CONFIG] = groupID
    val bootstrapServers = System.getenv("KAFKA_SERVICE_ADDR")
    if (bootstrapServers == null) {
        println("KAFKA_SERVICE_ADDR is not supplied")
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
                    try {
                        val newCount = accumulator + 1
                        val orders = OrderResult.parseFrom(record.value())

                        println("Consumed record with orderId: ${orders.orderId}, and updated total count to: $newCount")
                        if (newCount % 3L == 0L) {
                            throw RuntimeException("thrown on purpose by frauddetectionservice")
                        }
                        newCount
                    } catch(t: Throwable) {
                        Sentry.captureException(t)
                        accumulator
                    }
                }
        }
    }
}