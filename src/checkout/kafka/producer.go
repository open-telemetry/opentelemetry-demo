// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
package kafka

import (
	"context"
	"errors"
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

	// ErrInFlight is returned by Send when ctx is done before Kafka answered.
	// The result is logged when it arrives, and the message is queued for
	// retry if it failed.
	ErrInFlight = errors.New("no answer from Kafka yet, the message is still in flight")

	errQueuedBehind = errors.New("not sent, earlier messages are still queued for retry")
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
	stop         chan struct{} // closed by Shutdown
	retryDone    chan struct{} // closed when retryQueued returns
	resultsDone  chan struct{} // closed when dispatchResults returns

	mu        sync.Mutex
	queue     []*sarama.ProducerMessage
	resending bool // a message taken from the queue is being resent
	closed    bool // set by Shutdown, nothing is taken from the queue after it
}

func newProducer(producer sarama.AsyncProducer, queueSize int, retryBackoff time.Duration, logger *slog.Logger) *Producer {
	p := &Producer{
		AsyncProducer: producer,
		logger:        logger,
		queueSize:     queueSize,
		retryBackoff:  retryBackoff,
		wake:          make(chan struct{}, 1),
		stop:          make(chan struct{}),
		retryDone:     make(chan struct{}),
		resultsDone:   make(chan struct{}),
	}
	go p.dispatchResults()
	go p.retryQueued()
	return p
}

// Send hands msg to Kafka and waits for its result. If msg cannot be delivered,
// it is queued for retry and Send returns the error. While earlier messages are
// queued for retry, msg is queued behind them without being sent, so that it
// cannot overtake them, and Send returns at once. If ctx is done before msg
// was handed over, msg is queued and Send returns ctx.Err(). If ctx is done
// while msg is in flight, Send returns an error that wraps ErrInFlight and
// ctx.Err(), and the late result is handled by awaitLateResult.
func (p *Producer) Send(ctx context.Context, msg *sarama.ProducerMessage) error {
	if p.enqueueBehind(msg) {
		return errQueuedBehind
	}
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
			p.enqueueUnlessPermanent(msg, err)
		}
		return err
	case <-ctx.Done():
		go p.awaitLateResult(msg, result)
		return fmt.Errorf("%w: %w", ErrInFlight, ctx.Err())
	}
}

// awaitLateResult logs the result of a message whose Send returned before Kafka
// answered, and queues the message if it failed.
func (p *Producer) awaitLateResult(msg *sarama.ProducerMessage, result <-chan error) {
	if err := <-result; err != nil {
		p.logger.ErrorContext(messageContext(msg), fmt.Sprintf("Failed to write message after the context ended: %v", err))
		p.enqueueUnlessPermanent(msg, err)
		return
	}
	p.logger.InfoContext(messageContext(msg), fmt.Sprintf("Delivered Kafka message after the context ended. offset: %v", msg.Offset))
}

// IsPermanent reports whether err means that the message itself was rejected,
// so that every retry would fail the same way. That is the case when it is
// larger than Producer.MaxMessageBytes (sarama returns a ConfigurationError)
// or than the broker's limit, or when the broker finds its topic or record
// invalid.
func IsPermanent(err error) bool {
	var configErr sarama.ConfigurationError
	return errors.As(err, &configErr) ||
		errors.Is(err, sarama.ErrMessageSizeTooLarge) ||
		errors.Is(err, sarama.ErrInvalidTopic) ||
		errors.Is(err, sarama.ErrInvalidRecord)
}

// enqueueUnlessPermanent queues msg for retry, or drops it with a log line if
// err is permanent.
func (p *Producer) enqueueUnlessPermanent(msg *sarama.ProducerMessage, err error) {
	if IsPermanent(err) {
		p.logRejected(msg, err)
		return
	}
	p.enqueue(msg)
}

func (p *Producer) logRejected(msg *sarama.ProducerMessage, err error) {
	p.logger.ErrorContext(messageContext(msg), fmt.Sprintf("Kafka rejected the message, dropping it without retry: %v", err))
}

// RetryEnabled reports whether messages that could not be delivered are kept
// for retry, which is the case unless KAFKA_RETRY_QUEUE_SIZE is 0.
func (p *Producer) RetryEnabled() bool {
	return p.queueSize > 0
}

// dispatchResults is the only reader of Successes and Errors. It hands each
// result to the channel in the message's Metadata.
func (p *Producer) dispatchResults() {
	defer close(p.resultsDone)
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

// enqueueBehind queues msg if earlier messages are queued or being resent, so
// that msg cannot overtake them. It reports whether msg was queued.
func (p *Producer) enqueueBehind(msg *sarama.ProducerMessage) bool {
	p.mu.Lock()
	if len(p.queue) == 0 && !p.resending {
		p.mu.Unlock()
		return false
	}
	p.queue = append(p.queue, msg)
	dropped := p.dropOverflow()
	p.mu.Unlock()
	p.logDropped(dropped)
	return true
}

// finishResend marks the resend of msg as done and, if requeue is set, puts
// msg back first in the queue.
func (p *Producer) finishResend(msg *sarama.ProducerMessage, requeue bool) {
	p.mu.Lock()
	p.resending = false
	var dropped []*sarama.ProducerMessage
	if requeue {
		p.queue = slices.Insert(p.queue, 0, msg)
		dropped = p.dropOverflow()
	}
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
	if len(p.queue) == 0 || p.closed {
		return nil
	}
	msg := p.queue[0]
	p.queue[0] = nil
	p.queue = p.queue[1:]
	p.resending = true
	return msg
}

func (p *Producer) queued() int {
	p.mu.Lock()
	defer p.mu.Unlock()
	return len(p.queue)
}

// retryQueued resends the queue after each failure, waiting longer after each
// failed attempt. When Shutdown is called, it makes one last attempt at once
// and returns.
func (p *Producer) retryQueued() {
	defer close(p.retryDone)
	for {
		select {
		case <-p.wake:
		case <-p.stop:
			p.resendQueued()
			return
		}
		backoff := p.retryBackoff
		for {
			select {
			case <-time.After(backoff):
			case <-p.stop:
				p.resendQueued()
				return
			}
			if p.resendQueued() {
				break
			}
			backoff = min(2*backoff, maxRetryBackoff)
		}
	}
}

// Shutdown makes one last attempt to deliver the queued messages, logs how many
// are dropped, and closes the producer. It returns when ctx is done at the
// latest, and then leaves the producer open if the last attempt is still
// running. Send must not be called after Shutdown.
func (p *Producer) Shutdown(ctx context.Context) {
	close(p.stop)
	select {
	case <-p.retryDone:
	case <-ctx.Done():
	}
	p.mu.Lock()
	p.closed = true
	dropped := len(p.queue)
	p.queue = nil
	p.mu.Unlock()
	if dropped > 0 {
		p.logger.Error(fmt.Sprintf("Shutting down with %d messages in the Kafka retry queue, dropping them", dropped))
	}
	select {
	case <-p.retryDone:
		p.AsyncClose()
		select {
		case <-p.resultsDone:
		case <-ctx.Done():
		}
	case <-ctx.Done():
	}
}

// resendQueued sends queued messages in order, one at a time, until the queue is
// empty (true) or a message fails and is put back first in the queue (false).
// A message that is rejected permanently is dropped instead.
func (p *Producer) resendQueued() bool {
	for {
		msg := p.popFirst()
		if msg == nil {
			return true
		}
		result := make(chan error, 1)
		msg.Metadata = result
		p.Input() <- msg
		err := <-result
		if IsPermanent(err) {
			p.finishResend(msg, false)
			p.logRejected(msg, err)
			continue
		}
		p.finishResend(msg, err != nil)
		if err != nil {
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
