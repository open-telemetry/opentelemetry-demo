package frauddetectionservice

import org.apache.kafka.clients.consumer.ConsumerConfig.*
import org.apache.kafka.clients.consumer.KafkaConsumer
import org.apache.kafka.common.serialization.StringDeserializer
import java.time.Duration.ofMillis
import java.util.Properties
import kotlin.system.exitProcess

const val topic = "orders"
const val groupID = "frauddetectionservice"

fun main(args: Array<String>) {
    val props = Properties()
    props[KEY_DESERIALIZER_CLASS_CONFIG] = StringDeserializer::class.java.name
    props[VALUE_DESERIALIZER_CLASS_CONFIG] = StringDeserializer::class.java.name
    props[GROUP_ID_CONFIG] = groupID
    val bootstrapServers = System.getenv("KAFKA_SERVICE_ADDR")
    if (bootstrapServers == null) {
        println("KAFKA_SERVICE_ADDR is not supplied")
        exitProcess(1)
    }
    props[BOOTSTRAP_SERVERS_CONFIG] = bootstrapServers
    val consumer = KafkaConsumer<String, String>(props).apply {
        subscribe(listOf(topic))
    }

    var totalCount = 0L

    consumer.use {
        while (true) {
            totalCount = consumer
                .poll(ofMillis(100))
                .fold(totalCount) { accumulator, record ->
                    val newCount = accumulator + 1
                    println("Consumed record with key ${record.key()} and value ${record.value()}, and updated total count to $newCount")
                    newCount
                }
        }
    }
}