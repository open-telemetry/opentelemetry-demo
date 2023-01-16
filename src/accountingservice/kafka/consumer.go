package kafka

import (
	"context"
	"log"

	"github.com/open-telemetry/opentelemetry-demo/src/accountingservice/genproto/hipstershop"

	"github.com/Shopify/sarama"
	"github.com/sirupsen/logrus"
	"go.opentelemetry.io/contrib/instrumentation/github.com/Shopify/sarama/otelsarama"
	"google.golang.org/protobuf/proto"
)

var (
	Topic           = "orders"
	ProtocolVersion = sarama.V3_0_0_0
	GroupID         = "accountingservice"
)

func StartConsumerGroup(ctx context.Context, brokers []string, log *logrus.Logger) error {
	saramaConfig := sarama.NewConfig()
	saramaConfig.Version = ProtocolVersion
	// So we can know the partition and offset of messages.
	saramaConfig.Producer.Return.Successes = true

	consumerGroup, err := sarama.NewConsumerGroup(brokers, GroupID, saramaConfig)
	if err != nil {
		return err
	}

	handler := groupHandler{
		log: log,
	}
	wrappedHandler := otelsarama.WrapConsumerGroupHandler(&handler)

	err = consumerGroup.Consume(ctx, []string{Topic}, wrappedHandler)
	if err != nil {
		return err
	}
	return nil
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
			orderResult := hipstershop.OrderResult{}
			err := proto.Unmarshal(message.Value, &orderResult)
			if err != nil {
				return err
			}

			log.Printf("Message claimed: orderId = %s, timestamp = %v, topic = %s", orderResult.OrderId, message.Timestamp, message.Topic)
			session.MarkMessage(message, "")

		case <-session.Context().Done():
			return nil
		}
	}
}
