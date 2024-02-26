// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
package kafka

import (
	"context"
	pb "github.com/open-telemetry/opentelemetry-demo/src/accountingservice/genproto/oteldemo"

	"github.com/IBM/sarama"
	"github.com/sirupsen/logrus"
	"google.golang.org/protobuf/proto"
)

var (
	Topic           = "orders"
	ProtocolVersion = sarama.V3_0_0_0
	GroupID         = "accountingservice"
)

func StartConsumerGroup(ctx context.Context, brokers []string, log *logrus.Logger) (sarama.ConsumerGroup, error) {
	saramaConfig := sarama.NewConfig()
	saramaConfig.Version = ProtocolVersion
	// So we can know the partition and offset of messages.
	saramaConfig.Producer.Return.Successes = true
	saramaConfig.Consumer.Interceptors = []sarama.ConsumerInterceptor{NewOTelInterceptor(GroupID)}

	consumerGroup, err := sarama.NewConsumerGroup(brokers, GroupID, saramaConfig)
	if err != nil {
		return nil, err
	}

	handler := groupHandler{
		log: log,
	}

	err = consumerGroup.Consume(ctx, []string{Topic}, &handler)
	if err != nil {
		return nil, err
	}

	return consumerGroup, nil
}

type groupHandler struct {
	log *logrus.Logger
}

func (g *groupHandler) Setup(_ sarama.ConsumerGroupSession) error {
	return nil
}

func (g *groupHandler) Cleanup(_ sarama.ConsumerGroupSession) error {
	return nil
}

func (g *groupHandler) ConsumeClaim(session sarama.ConsumerGroupSession, claim sarama.ConsumerGroupClaim) error {
	for {
		select {
		case message := <-claim.Messages():
			orderResult := pb.OrderResult{}
			err := proto.Unmarshal(message.Value, &orderResult)
			if err != nil {
				return err
			}

			g.log.WithFields(logrus.Fields{
				"orderId":          orderResult.OrderId,
				"messageTimestamp": message.Timestamp,
				"messageTopic":     message.Topic,
			}).Info("Message claimed")
			session.MarkMessage(message, "")

		case <-session.Context().Done():
			return nil
		}
	}
}
