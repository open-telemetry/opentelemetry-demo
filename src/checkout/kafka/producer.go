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

func CreateClient(brokers []string, log *logrus.Logger) (sarama.Client, error) {
	sarama.Logger = log

	config := sarama.NewConfig()
	config.Producer.Return.Successes = true
	config.Producer.Return.Errors = true
	// Sarama has an issue in a single broker kafka if the kafka broker is restarted.
	// This setting is to prevent that issue from manifesting itself, but may swallow failed messages.
	config.Producer.RequiredAcks = sarama.NoResponse
	config.Version = ProtocolVersion
	// So we can know the partition and offset of messages.
	config.Producer.Return.Successes = true

	client, err := sarama.NewClient(brokers, config)
	if err != nil {
		log.Warnln("Failed to create sarama client:", err)
		return nil, err
	}
	return client, nil
}
