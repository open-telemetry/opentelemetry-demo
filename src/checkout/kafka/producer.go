// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
package kafka

import (
	"context"
	"fmt"
	"log/slog"
	"os"
	"slices"
	"strconv"
	"sync"
	"time"

	"github.com/IBM/sarama"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/propagation"
)

var (
	Topic           = getTopic()
	ProtocolVersion = sarama.V3_0_0_0
)

const (
	defaultRetryQueueSize = 1000
	maxRetryBackoff       = 10 * time.Second
)

func getTopic() string {
	if topic := os.Getenv("KAFKA_TOPIC"); topic != "" {
		return topic
	}
	return "orders"
}

func getRetryQueueSize(logger *slog.Logger) int {
	if v := os.Getenv("KAFKA_RETRY_QUEUE_SIZE"); v != "" {
		if size, err := strconv.Atoi(v); err == nil && size >= 0 {
			return size
		}
		logger.Warn(fmt.Sprintf("Invalid KAFKA_RETRY_QUEUE_SIZE %q, using %d", v, defaultRetryQueueSize))
	}
	return defaultRetryQueueSize
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

func CreateKafkaProducer(brokers []string, logger *slog.Logger) (*Producer, error) {
	// Set the logger for sarama to use.
	sarama.Logger = &saramaLogger{logger: logger}

	saramaConfig := sarama.NewConfig()
	saramaConfig.Producer.Return.Successes = true
	saramaConfig.Producer.Return.Errors = true
	saramaConfig.Producer.RequiredAcks = sarama.WaitForLocal

	saramaConfig.Version = ProtocolVersion

	producer, err := sarama.NewAsyncProducer(brokers, saramaConfig)
	if err != nil {
		return nil, err
	}
	return newProducer(producer, getRetryQueueSize(logger), time.Second, logger), nil
}

// Producer gives each message sent with Send its own delivery result. Messages
// that could not be delivered are kept in a bounded queue and retried in the
// background. When the queue is full, the oldest message is dropped.
type Producer struct {
	sarama.AsyncProducer
	logger       *slog.Logger
	queueSize    int
	retryBackoff time.Duration
	wake         chan struct{}

	mu    sync.Mutex
	queue []*sarama.ProducerMessage
}

func newProducer(producer sarama.AsyncProducer, queueSize int, retryBackoff time.Duration, logger *slog.Logger) *Producer {
	p := &Producer{
		AsyncProducer: producer,
		logger:        logger,
		queueSize:     queueSize,
		retryBackoff:  retryBackoff,
		wake:          make(chan struct{}, 1),
	}
	go p.dispatchResults()
	go p.retryQueued()
	return p
}

// Send hands msg to Kafka and waits for its result. If msg cannot be delivered,
// it is queued for retry and Send returns the error. If ctx is done first, Send
// returns ctx.Err() and msg is queued if it fails later.
func (p *Producer) Send(ctx context.Context, msg *sarama.ProducerMessage) error {
	result := make(chan error, 1)
	msg.Metadata = result
	select {
	case p.Input() <- msg:
	case <-ctx.Done():
		p.enqueue(msg)
		return ctx.Err()
	}
	select {
	case err := <-result:
		if err != nil {
			p.enqueue(msg)
		}
		return err
	case <-ctx.Done():
		go func() {
			if err := <-result; err != nil {
				p.enqueue(msg)
			}
		}()
		return ctx.Err()
	}
}

// RetryEnabled reports whether messages that could not be delivered are kept
// for retry, which is the case unless KAFKA_RETRY_QUEUE_SIZE is 0.
func (p *Producer) RetryEnabled() bool {
	return p.queueSize > 0
}

// dispatchResults is the only reader of Successes and Errors. It hands each
// result to the channel in the message's Metadata.
func (p *Producer) dispatchResults() {
	successes, errs := p.Successes(), p.Errors()
	for successes != nil || errs != nil {
		select {
		case msg, ok := <-successes:
			if !ok {
				successes = nil
				continue
			}
			p.deliverResult(msg, nil)
		case perr, ok := <-errs:
			if !ok {
				errs = nil
				continue
			}
			p.deliverResult(perr.Msg, perr.Err)
		}
	}
}

func (p *Producer) deliverResult(msg *sarama.ProducerMessage, err error) {
	if result, ok := msg.Metadata.(chan error); ok {
		result <- err
	} else if err != nil {
		p.logger.Error(fmt.Sprintf("Failed to write message: %v", err))
	}
}

func (p *Producer) enqueue(msg *sarama.ProducerMessage) {
	if !p.RetryEnabled() {
		p.logger.ErrorContext(messageContext(msg), "Kafka retry queue is disabled (KAFKA_RETRY_QUEUE_SIZE is 0), dropping the message")
		return
	}
	p.mu.Lock()
	p.queue = append(p.queue, msg)
	dropped := p.dropOverflow()
	p.mu.Unlock()
	p.logDropped(dropped)
	select {
	case p.wake <- struct{}{}:
	default:
	}
}

func (p *Producer) requeueFirst(msg *sarama.ProducerMessage) {
	p.mu.Lock()
	p.queue = slices.Insert(p.queue, 0, msg)
	dropped := p.dropOverflow()
	p.mu.Unlock()
	p.logDropped(dropped)
}

// dropOverflow must be called with p.mu held. It returns the dropped messages,
// which the caller logs with logDropped after releasing p.mu.
func (p *Producer) dropOverflow() []*sarama.ProducerMessage {
	var dropped []*sarama.ProducerMessage
	for len(p.queue) > p.queueSize {
		dropped = append(dropped, p.queue[0])
		p.queue[0] = nil
		p.queue = p.queue[1:]
	}
	return dropped
}

func (p *Producer) logDropped(dropped []*sarama.ProducerMessage) {
	for _, msg := range dropped {
		p.logger.ErrorContext(messageContext(msg), fmt.Sprintf("Kafka retry queue is full (%d messages), dropping the oldest message", p.queueSize))
	}
}

func (p *Producer) popFirst() *sarama.ProducerMessage {
	p.mu.Lock()
	defer p.mu.Unlock()
	if len(p.queue) == 0 {
		return nil
	}
	msg := p.queue[0]
	p.queue[0] = nil
	p.queue = p.queue[1:]
	return msg
}

func (p *Producer) queued() int {
	p.mu.Lock()
	defer p.mu.Unlock()
	return len(p.queue)
}

func (p *Producer) retryQueued() {
	for range p.wake {
		backoff := p.retryBackoff
		for {
			time.Sleep(backoff)
			if p.resendQueued() {
				break
			}
			backoff = min(2*backoff, maxRetryBackoff)
		}
	}
}

// resendQueued sends queued messages in order, one at a time, until the queue is
// empty (true) or a message fails and is put back first in the queue (false).
func (p *Producer) resendQueued() bool {
	for {
		msg := p.popFirst()
		if msg == nil {
			return true
		}
		result := make(chan error, 1)
		msg.Metadata = result
		p.Input() <- msg
		if err := <-result; err != nil {
			p.requeueFirst(msg)
			p.logger.WarnContext(messageContext(msg), fmt.Sprintf("Retry of queued Kafka message failed, %d messages queued: %v", p.queued(), err))
			return false
		}
		p.logger.InfoContext(messageContext(msg), fmt.Sprintf("Delivered queued Kafka message on retry. offset: %v, %d messages still queued", msg.Offset, p.queued()))
	}
}

// messageContext returns the trace context carried in the message headers, so
// that retry logs are correlated with the trace of the order.
func messageContext(msg *sarama.ProducerMessage) context.Context {
	carrier := propagation.MapCarrier{}
	for _, h := range msg.Headers {
		carrier[string(h.Key)] = string(h.Value)
	}
	return otel.GetTextMapPropagator().Extract(context.Background(), carrier)
}
