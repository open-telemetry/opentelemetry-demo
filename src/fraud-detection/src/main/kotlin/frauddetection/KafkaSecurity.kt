/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */

package frauddetection

import org.apache.kafka.clients.CommonClientConfigs.SECURITY_PROTOCOL_CONFIG
import org.apache.kafka.common.config.SaslConfigs.SASL_JAAS_CONFIG
import org.apache.kafka.common.config.SaslConfigs.SASL_MECHANISM
import java.util.*

/**
* Escapes a value for use inside a double-quoted JAAS configuration option.
*/
fun jaasEscape(value: String): String = value.replace("\\", "\\\\").replace("\"", "\\\"")

/**
* Configures Kafka security properties for TLS and/or SASL authentication.
*
 * @param props Kafka consumer properties to configure
 * @param securityProtocol Security protocol (PLAINTEXT, SSL, SASL_PLAINTEXT, SASL_SSL), or null for PLAINTEXT
 * @param saslMechanism SASL mechanism (PLAIN, SCRAM-SHA-256, SCRAM-SHA-512), or null for PLAIN
 * @param saslUsername SASL username (required when SASL is enabled)
 * @param saslPassword SASL password (required when SASL is enabled)
 * @throws IllegalArgumentException if protocol or mechanism is unsupported
 * @throws IllegalArgumentException if SASL credentials are missing when SASL is enabled
 */
fun configureKafkaSecurity(
    props: Properties,
    securityProtocol: String?,
    saslMechanism: String?,
    saslUsername: String?,
    saslPassword: String?
) {
    val protocol = securityProtocol?.takeIf { it.isNotEmpty() }
    
    // If no protocol specified, do nothing (keep plaintext)
    if (protocol == null) {
        return
    }
    
    // Validate and set security protocol
    when (protocol.uppercase()) {
        "PLAINTEXT", "SSL", "SASL_PLAINTEXT", "SASL_SSL" -> {
            props[SECURITY_PROTOCOL_CONFIG] = protocol
        }
        else -> {
            throw IllegalArgumentException(
                "Unsupported KAFKA_SECURITY_PROTOCOL: $protocol. " +
                "Supported values: PLAINTEXT, SSL, SASL_PLAINTEXT, SASL_SSL"
            )
        }
    }
    
    // Configure SASL if protocol starts with SASL_
    if (protocol.uppercase().startsWith("SASL_")) {
        val mechanism = saslMechanism?.takeIf { it.isNotEmpty() } ?: "PLAIN"
        
        // Validate SASL mechanism
        when (mechanism.uppercase()) {
            "PLAIN", "SCRAM-SHA-256", "SCRAM-SHA-512" -> {
                props[SASL_MECHANISM] = mechanism
            }
            else -> {
                throw IllegalArgumentException(
                    "Unsupported KAFKA_SASL_MECHANISM: $mechanism. " +
                    "Supported values: PLAIN, SCRAM-SHA-256, SCRAM-SHA-512"
                )
            }
        }
        
        // Ensure credentials are provided
        if (saslUsername.isNullOrEmpty()) {
            throw IllegalArgumentException(
                "KAFKA_SASL_USERNAME is required when SASL is enabled"
            )
        }
        if (saslPassword.isNullOrEmpty()) {
            throw IllegalArgumentException(
                "KAFKA_SASL_PASSWORD is required when SASL is enabled"
            )
        }
        
        // Select login module based on mechanism
        val loginModule = if (mechanism.uppercase().startsWith("SCRAM-")) {
            "org.apache.kafka.common.security.scram.ScramLoginModule"
        } else {
            "org.apache.kafka.common.security.plain.PlainLoginModule"
        }
        
        // Construct JAAS configuration (credentials are escaped to prevent injection)
        props[SASL_JAAS_CONFIG] = "$loginModule required " +
            "username=\"${jaasEscape(saslUsername)}\" " +
            "password=\"${jaasEscape(saslPassword)}\";"
    }
}
