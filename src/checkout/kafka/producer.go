// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
package kafka

import (
	"github.com/IBM/sarama"
	"github.com/sirupsen/logrus"
)

var (
	Topic           = "orders"
	ProtocolVersion = sarama.V3_0_0_0
)

func CreateKafkaProducer(brokers []string, log *logrus.Logger) (sarama.AsyncProducer, error) {
	sarama.Logger = log

	saramaConfig := sarama.NewConfig()
	saramaConfig.Producer.Return.Successes = true
	saramaConfig.Producer.Return.Errors = true

	// Sarama has an issue in a single broker kafka if the kafka broker is restarted.
	// This setting is to prevent that issue from manifesting itself, but may swallow failed messages.
	saramaConfig.Producer.RequiredAcks = sarama.NoResponse

	saramaConfig.Version = ProtocolVersion

	// So we can know the partition and offset of messages.
	saramaConfig.Producer.Return.Successes = true

	producer, err := sarama.NewAsyncProducer(brokers, saramaConfig)
	if err != nil {
		return nil, err
	}

	// We will log to STDOUT if we're not able to produce messages.
	go func() {
		for err := range producer.Errors() {
			log.Errorf("Failed to write message: %+v", err)
		}
	}()
	return producer, nil
}
