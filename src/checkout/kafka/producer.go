// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
package kafka

import (
	"crypto/tls"
	"fmt"
	"log/slog"
	"os"
	"strings"

	"github.com/IBM/sarama"
	"github.com/xdg-go/scram"
)

var (
	Topic           = getTopic()
	ProtocolVersion = sarama.V3_0_0_0
)

func getTopic() string {
	if topic := os.Getenv("KAFKA_TOPIC"); topic != "" {
		return topic
	}
	return "orders"
}

type saramaLogger struct {
	logger *slog.Logger
}

func (l *saramaLogger) Printf(format string, v ...interface{}) {
	l.logger.Info(fmt.Sprintf(format, v...))
}
func (l *saramaLogger) Println(v ...interface{}) {
	l.logger.Info(fmt.Sprint(v...))
}
func (l *saramaLogger) Print(v ...interface{}) {
	l.logger.Info(fmt.Sprint(v...))
}

func CreateKafkaProducer(brokers []string, logger *slog.Logger) (sarama.AsyncProducer, error) {
	// Set the logger for sarama to use.
	sarama.Logger = &saramaLogger{logger: logger}

	saramaConfig := sarama.NewConfig()
	saramaConfig.Producer.Return.Successes = true
	saramaConfig.Producer.Return.Errors = true

	// Sarama has an issue in a single broker kafka if the kafka broker is restarted.
	// This setting is to prevent that issue from manifesting itself, but may swallow failed messages.
	saramaConfig.Producer.RequiredAcks = sarama.NoResponse

	saramaConfig.Version = ProtocolVersion

	// So we can know the partition and offset of messages.
	saramaConfig.Producer.Return.Successes = true

	if err := configureSecurity(saramaConfig); err != nil {
		return nil, err
	}

	producer, err := sarama.NewAsyncProducer(brokers, saramaConfig)
	if err != nil {
		return nil, err
	}

	// We will log to STDOUT if we're not able to produce messages.
	go func() {
		for err := range producer.Errors() {
			logger.Error(fmt.Sprintf("Failed to write message: %+v", err))

		}
	}()
	return producer, nil
}

// configureSecurity applies the optional KAFKA_SECURITY_PROTOCOL, KAFKA_SASL_MECHANISM,
// KAFKA_SASL_USERNAME and KAFKA_SASL_PASSWORD settings, so the producer can connect to a
// Kafka cluster that requires TLS and/or SASL. Without them the connection stays plaintext.
func configureSecurity(saramaConfig *sarama.Config) error {
	protocol := strings.ToUpper(os.Getenv("KAFKA_SECURITY_PROTOCOL"))
	switch protocol {
	case "", "PLAINTEXT":
		return nil
	case "SSL", "SASL_PLAINTEXT", "SASL_SSL":
	default:
		return fmt.Errorf("unsupported KAFKA_SECURITY_PROTOCOL %q", protocol)
	}

	if protocol == "SSL" || protocol == "SASL_SSL" {
		saramaConfig.Net.TLS.Enable = true
		saramaConfig.Net.TLS.Config = &tls.Config{MinVersion: tls.VersionTLS12}
	}

	if protocol == "SASL_PLAINTEXT" || protocol == "SASL_SSL" {
		saramaConfig.Net.SASL.Enable = true
		saramaConfig.Net.SASL.User = os.Getenv("KAFKA_SASL_USERNAME")
		saramaConfig.Net.SASL.Password = os.Getenv("KAFKA_SASL_PASSWORD")

		if saramaConfig.Net.SASL.User == "" {
			return fmt.Errorf("KAFKA_SASL_USERNAME is required when SASL is enabled")
		}
		if saramaConfig.Net.SASL.Password == "" {
			return fmt.Errorf("KAFKA_SASL_PASSWORD is required when SASL is enabled")
		}

		switch mechanism := strings.ToUpper(os.Getenv("KAFKA_SASL_MECHANISM")); mechanism {
		case "", "PLAIN":
			saramaConfig.Net.SASL.Mechanism = sarama.SASLTypePlaintext
		case "SCRAM-SHA-256":
			saramaConfig.Net.SASL.Mechanism = sarama.SASLTypeSCRAMSHA256
			saramaConfig.Net.SASL.SCRAMClientGeneratorFunc = func() sarama.SCRAMClient {
				return &scramClient{HashGeneratorFcn: scram.SHA256}
			}
		case "SCRAM-SHA-512":
			saramaConfig.Net.SASL.Mechanism = sarama.SASLTypeSCRAMSHA512
			saramaConfig.Net.SASL.SCRAMClientGeneratorFunc = func() sarama.SCRAMClient {
				return &scramClient{HashGeneratorFcn: scram.SHA512}
			}
		default:
			return fmt.Errorf("unsupported KAFKA_SASL_MECHANISM %q", mechanism)
		}
	}

	return nil
}

// scramClient implements sarama.SCRAMClient, which sarama needs for the SCRAM-SHA-* mechanisms.
// Based on https://github.com/IBM/sarama/blob/main/examples/sasl_scram_client/scram_client.go
type scramClient struct {
	*scram.Client
	*scram.ClientConversation
	scram.HashGeneratorFcn
}

func (x *scramClient) Begin(userName, password, authzID string) (err error) {
	x.Client, err = x.HashGeneratorFcn.NewClient(userName, password, authzID)
	if err != nil {
		return err
	}
	x.ClientConversation = x.Client.NewConversation()
	return nil
}

func (x *scramClient) Step(challenge string) (string, error) {
	return x.ClientConversation.Step(challenge)
}

func (x *scramClient) Done() bool {
	return x.ClientConversation.Done()
}
