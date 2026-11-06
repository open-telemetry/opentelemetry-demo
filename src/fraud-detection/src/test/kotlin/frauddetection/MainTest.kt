/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */

package frauddetection

import org.apache.kafka.clients.consumer.ConsumerConfig.*
import org.apache.kafka.clients.CommonClientConfigs.SECURITY_PROTOCOL_CONFIG
import org.apache.kafka.common.config.SaslConfigs.SASL_JAAS_CONFIG
import org.apache.kafka.common.config.SaslConfigs.SASL_MECHANISM
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertNull
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.assertThrows

class MainTest {

    @Test
    fun testJaasEscape() {
        assertEquals("", jaasEscape(""))
        assertEquals("test", jaasEscape("test"))
        assertEquals("test\\\\backslash", jaasEscape("test\\backslash"))
        assertEquals("test\\\"quote", jaasEscape("test\"quote"))
        assertEquals("\\\\", jaasEscape("\\"))
        assertEquals("\\\"", jaasEscape("\""))
        assertEquals("a\\\"b\\\\c", jaasEscape("a\"b\\c"))
        assertEquals("user@domain", jaasEscape("user@domain"))
        assertEquals("p@ss\\\"w0rd", jaasEscape("p@ss\"w0rd"))
    }

    @Test
    fun testConfigureKafkaSecurity_UnsetProtocol() {
        val props = java.util.Properties()
        configureKafkaSecurity(props, null, null, null, null)
        
        assertNull(props[SECURITY_PROTOCOL_CONFIG])
        assertNull(props[SASL_MECHANISM])
        assertNull(props[SASL_JAAS_CONFIG])
    }

    @Test
    fun testConfigureKafkaSecurity_Plaintext() {
        val props = java.util.Properties()
        configureKafkaSecurity(props, "PLAINTEXT", null, null, null)
        
        assertEquals("PLAINTEXT", props[SECURITY_PROTOCOL_CONFIG])
        assertNull(props[SASL_MECHANISM])
        assertNull(props[SASL_JAAS_CONFIG])
    }

    @Test
    fun testConfigureKafkaSecurity_SSL() {
        val props = java.util.Properties()
        configureKafkaSecurity(props, "SSL", null, null, null)
        
        assertEquals("SSL", props[SECURITY_PROTOCOL_CONFIG])
        assertNull(props[SASL_MECHANISM])
        assertNull(props[SASL_JAAS_CONFIG])
    }

    @Test
    fun testConfigureKafkaSecurity_SASL_SSL_PLAIN() {
        val props = java.util.Properties()
        configureKafkaSecurity(props, "SASL_SSL", "PLAIN", "testuser", "testpass")
        
        assertEquals("SASL_SSL", props[SECURITY_PROTOCOL_CONFIG])
        assertEquals("PLAIN", props[SASL_MECHANISM])
        assertEquals(
            "org.apache.kafka.common.security.plain.PlainLoginModule required username=\"testuser\" password=\"testpass\";",
            props[SASL_JAAS_CONFIG]
        )
    }

    @Test
    fun testConfigureKafkaSecurity_SASL_SSL_DefaultsToPlain() {
        val props = java.util.Properties()
        configureKafkaSecurity(props, "SASL_SSL", null, "testuser", "testpass")
        
        assertEquals("SASL_SSL", props[SECURITY_PROTOCOL_CONFIG])
        assertEquals("PLAIN", props[SASL_MECHANISM])
        assertEquals(
            "org.apache.kafka.common.security.plain.PlainLoginModule required username=\"testuser\" password=\"testpass\";",
            props[SASL_JAAS_CONFIG]
        )
    }

    @Test
    fun testConfigureKafkaSecurity_SASL_SSL_SCRAM_SHA256() {
        val props = java.util.Properties()
        configureKafkaSecurity(props, "SASL_SSL", "SCRAM-SHA-256", "testuser", "testpass")
        
        assertEquals("SASL_SSL", props[SECURITY_PROTOCOL_CONFIG])
        assertEquals("SCRAM-SHA-256", props[SASL_MECHANISM])
        assertEquals(
            "org.apache.kafka.common.security.scram.ScramLoginModule required username=\"testuser\" password=\"testpass\";",
            props[SASL_JAAS_CONFIG]
        )
    }

    @Test
    fun testConfigureKafkaSecurity_SASL_SSL_SCRAM_SHA512() {
        val props = java.util.Properties()
        configureKafkaSecurity(props, "SASL_SSL", "SCRAM-SHA-512", "testuser", "testpass")
        
        assertEquals("SASL_SSL", props[SECURITY_PROTOCOL_CONFIG])
        assertEquals("SCRAM-SHA-512", props[SASL_MECHANISM])
        assertEquals(
            "org.apache.kafka.common.security.scram.ScramLoginModule required username=\"testuser\" password=\"testpass\";",
            props[SASL_JAAS_CONFIG]
        )
    }

    @Test
    fun testConfigureKafkaSecurity_SASL_PLAINTEXT() {
        val props = java.util.Properties()
        configureKafkaSecurity(props, "SASL_PLAINTEXT", "PLAIN", "testuser", "testpass")
        
        assertEquals("SASL_PLAINTEXT", props[SECURITY_PROTOCOL_CONFIG])
        assertEquals("PLAIN", props[SASL_MECHANISM])
        assertEquals(
            "org.apache.kafka.common.security.plain.PlainLoginModule required username=\"testuser\" password=\"testpass\";",
            props[SASL_JAAS_CONFIG]
        )
    }

    @Test
    fun testConfigureKafkaSecurity_InvalidProtocol() {
        val props = java.util.Properties()
        val exception = assertThrows<IllegalArgumentException> {
            configureKafkaSecurity(props, "INVALID", null, null, null)
        }
        assertTrue(exception.message!!.contains("Unsupported KAFKA_SECURITY_PROTOCOL"))
        assertTrue(exception.message!!.contains("INVALID"))
    }

    @Test
    fun testConfigureKafkaSecurity_InvalidMechanism() {
        val props = java.util.Properties()
        val exception = assertThrows<IllegalArgumentException> {
            configureKafkaSecurity(props, "SASL_SSL", "GSSAPI", "testuser", "testpass")
        }
        assertTrue(exception.message!!.contains("Unsupported KAFKA_SASL_MECHANISM"))
        assertTrue(exception.message!!.contains("GSSAPI"))
    }

    @Test
 fun testConfigureKafkaSecurity_PasswordWithSpecialChars() {
        val props = java.util.Properties()
        configureKafkaSecurity(props, "SASL_SSL", "PLAIN", "user", "p@ss\"w0rd\\slash")
        
        assertEquals(
            "org.apache.kafka.common.security.plain.PlainLoginModule required username=\"user\" password=\"p@ss\\\"w0rd\\\\slash\";",
            props[SASL_JAAS_CONFIG]
        )
    }

    @Test
    fun testConfigureKafkaSecurity_MissingUsername() {
        val props = java.util.Properties()
        val exception = assertThrows<IllegalArgumentException> {
            configureKafkaSecurity(props, "SASL_SSL", "PLAIN", null, "testpass")
        }
        assertTrue(exception.message!!.contains("KAFKA_SASL_USERNAME is required"))
    }

    @Test
    fun testConfigureKafkaSecurity_MissingPassword() {
        val props = java.util.Properties()
        val exception = assertThrows<IllegalArgumentException> {
            configureKafkaSecurity(props, "SASL_SSL", "PLAIN", "testuser", null)
        }
        assertTrue(exception.message!!.contains("KAFKA_SASL_PASSWORD is required"))
    }

    @Test
    fun testConfigureKafkaSecurity_CaseInsensitiveProtocol() {
        val props = java.util.Properties()
        configureKafkaSecurity(props, "ssl", null, null, null)
        
        assertEquals("ssl", props[SECURITY_PROTOCOL_CONFIG])
    }

    @Test
    fun testConfigureKafkaSecurity_CaseInsensitiveMechanism() {
        val props = java.util.Properties()
        configureKafkaSecurity(props, "SASL_SSL", "scram-sha-256", "testuser", "testpass")
        
        assertEquals("scram-sha-256", props[SASL_MECHANISM])
    }
}
