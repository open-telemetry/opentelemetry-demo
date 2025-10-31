package sqs

import (
	"context"
	"encoding/json"
	"fmt"

	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/config"
	"github.com/aws/aws-sdk-go-v2/service/sqs"
)

// Payload represents the message body sent to SQS.
type Payload struct {
	CustomerID string `json:"customer_id"`
	OrderID    string `json:"order_id"`
}

// SQSQueue wraps an SQS client with a specific queue URL.
type SQSQueue struct {
	client   *sqs.Client
	queueURL string
}

// NewSQSQueue initializes an SQS client (default config chain) and binds it with the provided queue URL.
func NewSQSQueue(ctx context.Context, queueURL string) (*SQSQueue, error) {
	cfg, err := config.LoadDefaultConfig(ctx)
	if err != nil {
		return nil, fmt.Errorf("load AWS config: %w", err)
	}

	return &SQSQueue{
		client:   sqs.NewFromConfig(cfg),
		queueURL: queueURL,
	}, nil
}

// SendMessage sends the given Payload as JSON to the bound queue URL.
// Returns the SQS MessageId on success.
func (q *SQSQueue) SendMessage(ctx context.Context, p Payload) (string, error) {
	b, err := json.Marshal(p)
	if err != nil {
		return "", fmt.Errorf("marshal payload: %w", err)
	}
	out, err := q.client.SendMessage(ctx, &sqs.SendMessageInput{
		QueueUrl:    aws.String(q.queueURL),
		MessageBody: aws.String(string(b)),
	})
	if err != nil {
		return "", fmt.Errorf("send message: %w", err)
	}
	if out.MessageId == nil {
		return "", fmt.Errorf("send message succeeded but MessageId was nil")
	}
	return *out.MessageId, nil
}
