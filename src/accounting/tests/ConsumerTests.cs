// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

using System;
using Xunit;
using Environment = System.Environment;

namespace Accounting.Tests;

public class ConsumerTests
{
    [Fact]
    public void Consumer_NoSecurity_UsesPlaintext()
    {
        Environment.SetEnvironmentVariable("KAFKA_SECURITY_PROTOCOL", null);
        Environment.SetEnvironmentVariable("KAFKA_SASL_MECHANISM", null);
        Environment.SetEnvironmentVariable("KAFKA_SASL_USERNAME", null);
        Environment.SetEnvironmentVariable("KAFKA_SASL_PASSWORD", null);

        var exception = Record.Exception(() => Consumer.BuildConsumer("localhost:9092"));
        
        // BuildConsumer doesn't connect immediately, so it should not throw for config
        Assert.Null(exception);
    }

    [Fact]
    public void Consumer_SSL_SetsSecurityProtocol()
    {
        Environment.SetEnvironmentVariable("KAFKA_SECURITY_PROTOCOL", "SSL");
        Environment.SetEnvironmentVariable("KAFKA_SASL_MECHANISM", null);
        Environment.SetEnvironmentVariable("KAFKA_SASL_USERNAME", null);
        Environment.SetEnvironmentVariable("KAFKA_SASL_PASSWORD", null);

        var exception = Record.Exception(() => Consumer.BuildConsumer("localhost:9092"));
        
        Assert.Null(exception);
    }

    [Fact]
    public void Consumer_SASL_Plaintext_WithValidCredentials()
    {
        Environment.SetEnvironmentVariable("KAFKA_SECURITY_PROTOCOL", "SASL_PLAINTEXT");
        Environment.SetEnvironmentVariable("KAFKA_SASL_MECHANISM", "PLAIN");
        Environment.SetEnvironmentVariable("KAFKA_SASL_USERNAME", "testuser");
        Environment.SetEnvironmentVariable("KAFKA_SASL_PASSWORD", "testpass");

        var exception = Record.Exception(() => Consumer.BuildConsumer("localhost:9092"));
        
        Assert.Null(exception);
    }

    [Fact]
    public void Consumer_SASL_SSL_WithValidCredentials()
    {
        Environment.SetEnvironmentVariable("KAFKA_SECURITY_PROTOCOL", "SASL_SSL");
        Environment.SetEnvironmentVariable("KAFKA_SASL_MECHANISM", "PLAIN");
        Environment.SetEnvironmentVariable("KAFKA_SASL_USERNAME", "testuser");
        Environment.SetEnvironmentVariable("KAFKA_SASL_PASSWORD", "testpass");

        var exception = Record.Exception(() => Consumer.BuildConsumer("localhost:9092"));
        
        Assert.Null(exception);
    }

    [Fact]
    public void Consumer_SASL_SSL_DefaultsToPlainMechanism()
    {
        Environment.SetEnvironmentVariable("KAFKA_SECURITY_PROTOCOL", "SASL_SSL");
        Environment.SetEnvironmentVariable("KAFKA_SASL_MECHANISM", null);
        Environment.SetEnvironmentVariable("KAFKA_SASL_USERNAME", "testuser");
        Environment.SetEnvironmentVariable("KAFKA_SASL_PASSWORD", "testpass");

        var exception = Record.Exception(() => Consumer.BuildConsumer("localhost:9092"));
        
        Assert.Null(exception);
    }

    [Fact]
    public void Consumer_SASL_SSL_WithSCRAMSHA256()
    {
        Environment.SetEnvironmentVariable("KAFKA_SECURITY_PROTOCOL", "SASL_SSL");
        Environment.SetEnvironmentVariable("KAFKA_SASL_MECHANISM", "SCRAM-SHA-256");
        Environment.SetEnvironmentVariable("KAFKA_SASL_USERNAME", "testuser");
        Environment.SetEnvironmentVariable("KAFKA_SASL_PASSWORD", "testpass");

        var exception = Record.Exception(() => Consumer.BuildConsumer("localhost:9092"));
        
        Assert.Null(exception);
    }

    [Fact]
    public void Consumer_SASL_SSL_WithSCRAMSHA512()
    {
        Environment.SetEnvironmentVariable("KAFKA_SECURITY_PROTOCOL", "SASL_SSL");
        Environment.SetEnvironmentVariable("KAFKA_SASL_MECHANISM", "SCRAM-SHA-512");
        Environment.SetEnvironmentVariable("KAFKA_SASL_USERNAME", "testuser");
        Environment.SetEnvironmentVariable("KAFKA_SASL_PASSWORD", "testpass");

        var exception = Record.Exception(() => Consumer.BuildConsumer("localhost:9092"));
        
        Assert.Null(exception);
    }

    [Fact]
    public void Consumer_InvalidProtocol_Throws()
    {
        Environment.SetEnvironmentVariable("KAFKA_SECURITY_PROTOCOL", "INVALID");
        Environment.SetEnvironmentVariable("KAFKA_SASL_MECHANISM", null);
        Environment.SetEnvironmentVariable("KAFKA_SASL_USERNAME", null);
        Environment.SetEnvironmentVariable("KAFKA_SASL_PASSWORD", null);

        var exception = Assert.Throws<InvalidOperationException>(() => Consumer.BuildConsumer("localhost:9092"));
        
        Assert.Contains("Unsupported KAFKA_SECURITY_PROTOCOL", exception.Message);
        Assert.Contains("INVALID", exception.Message);
    }

    [Fact]
    public void Consumer_InvalidMechanism_Throws()
    {
        Environment.SetEnvironmentVariable("KAFKA_SECURITY_PROTOCOL", "SASL_SSL");
        Environment.SetEnvironmentVariable("KAFKA_SASL_MECHANISM", "GSSAPI");
        Environment.SetEnvironmentVariable("KAFKA_SASL_USERNAME", "testuser");
        Environment.SetEnvironmentVariable("KAFKA_SASL_PASSWORD", "testpass");

        var exception = Assert.Throws<InvalidOperationException>(() => Consumer.BuildConsumer("localhost:9092"));
        
        Assert.Contains("Unsupported KAFKA_SASL_MECHANISM", exception.Message);
        Assert.Contains("GSSAPI", exception.Message);
    }

    [Fact]
    public void Consumer_MissingUsername_Throws()
    {
        Environment.SetEnvironmentVariable("KAFKA_SECURITY_PROTOCOL", "SASL_SSL");
        Environment.SetEnvironmentVariable("KAFKA_SASL_MECHANISM", "PLAIN");
        Environment.SetEnvironmentVariable("KAFKA_SASL_USERNAME", null);
        Environment.SetEnvironmentVariable("KAFKA_SASL_PASSWORD", "testpass");

        var exception = Assert.Throws<InvalidOperationException>(() => Consumer.BuildConsumer("localhost:9092"));
        
        Assert.Contains("KAFKA_SASL_USERNAME is required", exception.Message);
    }

    [Fact]
    public void Consumer_MissingPassword_Throws()
    {
        Environment.SetEnvironmentVariable("KAFKA_SECURITY_PROTOCOL", "SASL_SSL");
        Environment.SetEnvironmentVariable("KAFKA_SASL_MECHANISM", "PLAIN");
        Environment.SetEnvironmentVariable("KAFKA_SASL_USERNAME", "testuser");
        Environment.SetEnvironmentVariable("KAFKA_SASL_PASSWORD", null);

        var exception = Assert.Throws<InvalidOperationException>(() => Consumer.BuildConsumer("localhost:9092"));
        
        Assert.Contains("KAFKA_SASL_PASSWORD is required", exception.Message);
    }

    [Fact]
    public void Consumer_CaseInsensitiveProtocol()
    {
        Environment.SetEnvironmentVariable("KAFKA_SECURITY_PROTOCOL", "ssl");
        Environment.SetEnvironmentVariable("KAFKA_SASL_MECHANISM", null);
        Environment.SetEnvironmentVariable("KAFKA_SASL_USERNAME", null);
        Environment.SetEnvironmentVariable("KAFKA_SASL_PASSWORD", null);

        var exception = Record.Exception(() => Consumer.BuildConsumer("localhost:9092"));
        
        Assert.Null(exception);
    }

    [Fact]
    public void Consumer_CaseInsensitiveMechanism()
    {
        Environment.SetEnvironmentVariable("KAFKA_SECURITY_PROTOCOL", "SASL_SSL");
        Environment.SetEnvironmentVariable("KAFKA_SASL_MECHANISM", "scram-sha-256");
        Environment.SetEnvironmentVariable("KAFKA_SASL_USERNAME", "testuser");
        Environment.SetEnvironmentVariable("KAFKA_SASL_PASSWORD", "testpass");

        var exception = Record.Exception(() => Consumer.BuildConsumer("localhost:9092"));
        
        Assert.Null(exception);
    }
}
