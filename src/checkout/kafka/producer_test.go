// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
package kafka

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"log/slog"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/IBM/sarama"
	"github.com/IBM/sarama/mocks"
)

var errBrokerDown = errors.New("broker down")

func newMockProducer(t *testing.T) *mocks.AsyncProducer {
	config := sarama.NewConfig()
	config.Producer.Return.Successes = true
	return mocks.NewAsyncProducer(t, config)
}

func newMessage(value string) *sarama.ProducerMessage {
	return &sarama.ProducerMessage{Topic: "orders", Value: sarama.StringEncoder(value)}
}

func messageValue(msg *sarama.ProducerMessage) string {
	value, _ := msg.Value.Encode()
	return string(value)
}

// recorder notes which messages the mock broker accepted or rejected, in order.
type recorder struct {
	mu     sync.Mutex
	values []string
	result map[string]error
}

func (r *recorder) check(err error) mocks.MessageChecker {
	return func(msg *sarama.ProducerMessage) error {
		r.mu.Lock()
		defer r.mu.Unlock()
		r.values = append(r.values, messageValue(msg))
		if r.result == nil {
			r.result = map[string]error{}
		}
		r.result[messageValue(msg)] = err
		return nil
	}
}

func (r *recorder) delivered() []string {
	r.mu.Lock()
	defer r.mu.Unlock()
	return append([]string(nil), r.values...)
}

// syncBuffer is a log sink that the test can read while goroutines write to it.
type syncBuffer struct {
	mu  sync.Mutex
	buf bytes.Buffer
}

func (b *syncBuffer) Write(p []byte) (int, error) {
	b.mu.Lock()
	defer b.mu.Unlock()
	return b.buf.Write(p)
}

func (b *syncBuffer) String() string {
	b.mu.Lock()
	defer b.mu.Unlock()
	return b.buf.String()
}

func waitFor(t *testing.T, what string, cond func() bool) {
	t.Helper()
	deadline := time.Now().Add(5 * time.Second)
	for !cond() {
		if time.Now().After(deadline) {
			t.Fatalf("timed out waiting for %s", what)
		}
		time.Sleep(time.Millisecond)
	}
}

func queuedValues(p *Producer) []string {
	p.mu.Lock()
	defer p.mu.Unlock()
	values := make([]string, 0, len(p.queue))
	for _, msg := range p.queue {
		values = append(values, messageValue(msg))
	}
	return values
}

func TestSendSuccess(t *testing.T) {
	mock := newMockProducer(t)
	mock.ExpectInputAndSucceed()
	p := newProducer(mock, 10, time.Hour, slog.New(slog.DiscardHandler))

	msg := newMessage("order-1")
	if err := p.Send(context.Background(), msg); err != nil {
		t.Fatalf("Send() error = %v, want nil", err)
	}
	if msg.Offset != 1 {
		t.Errorf("offset = %d, want 1", msg.Offset)
	}
	if n := p.queued(); n != 0 {
		t.Errorf("queued = %d, want 0", n)
	}
	if err := mock.Close(); err != nil {
		t.Fatal(err)
	}
}

func TestFailedSendIsRetriedUntilDelivered(t *testing.T) {
	mock := newMockProducer(t)
	var rec recorder
	mock.ExpectInputWithMessageCheckerFunctionAndFail(rec.check(errBrokerDown), errBrokerDown)
	mock.ExpectInputWithMessageCheckerFunctionAndFail(rec.check(errBrokerDown), errBrokerDown)
	mock.ExpectInputWithMessageCheckerFunctionAndSucceed(rec.check(nil))
	var logs syncBuffer
	p := newProducer(mock, 10, 10*time.Millisecond, slog.New(slog.NewTextHandler(&logs, nil)))

	if err := p.Send(context.Background(), newMessage("order-1")); !errors.Is(err, errBrokerDown) {
		t.Fatalf("Send() error = %v, want %v", err, errBrokerDown)
	}
	waitFor(t, "delivery on the second retry", func() bool {
		return strings.Contains(logs.String(), "Delivered queued Kafka message on retry. offset: 1, 0 messages still queued")
	})
	want := []string{"order-1", "order-1", "order-1"}
	if got := rec.delivered(); fmt.Sprint(got) != fmt.Sprint(want) {
		t.Errorf("messages the broker saw = %v, want %v", got, want)
	}
	if n := strings.Count(logs.String(), "Retry of queued Kafka message failed"); n != 1 {
		t.Errorf("failed retry log lines = %d, want 1, logs:\n%s", n, logs.String())
	}

	if err := mock.Close(); err != nil {
		t.Fatal(err)
	}
}

func TestRetryKeepsQueueOrder(t *testing.T) {
	mock := newMockProducer(t)
	var rec recorder
	mock.ExpectInputWithMessageCheckerFunctionAndFail(rec.check(errBrokerDown), errBrokerDown)
	for range 3 {
		mock.ExpectInputWithMessageCheckerFunctionAndSucceed(rec.check(nil))
	}
	var logs syncBuffer
	p := newProducer(mock, 10, 10*time.Millisecond, slog.New(slog.NewTextHandler(&logs, nil)))

	p.mu.Lock()
	p.queue = append(p.queue, newMessage("order-1"), newMessage("order-2"), newMessage("order-3"))
	p.mu.Unlock()
	p.wake <- struct{}{}

	waitFor(t, "the queue to drain", func() bool {
		return strings.Count(logs.String(), "Delivered queued Kafka message on retry") == 3
	})
	want := []string{"order-1", "order-1", "order-2", "order-3"}
	if got := rec.delivered(); fmt.Sprint(got) != fmt.Sprint(want) {
		t.Errorf("messages in the order the broker saw them = %v, want %v", got, want)
	}
	if err := mock.Close(); err != nil {
		t.Fatal(err)
	}
}

func TestFullQueueDropsOldest(t *testing.T) {
	mock := newMockProducer(t)
	// Only order-1 reaches the broker. The later ones are queued behind it.
	mock.ExpectInputAndFail(errBrokerDown)
	var logs syncBuffer
	p := newProducer(mock, 2, time.Hour, slog.New(slog.NewTextHandler(&logs, nil)))

	for i := 1; i <= 4; i++ {
		if err := p.Send(context.Background(), newMessage(fmt.Sprintf("order-%d", i))); err == nil {
			t.Fatalf("Send(order-%d) error = nil, want an error", i)
		}
	}
	if got, want := queuedValues(p), []string{"order-3", "order-4"}; fmt.Sprint(got) != fmt.Sprint(want) {
		t.Errorf("queue = %v, want %v", got, want)
	}
	if n := strings.Count(logs.String(), "dropping the oldest message"); n != 2 {
		t.Errorf("drop log lines = %d, want 2, logs:\n%s", n, logs.String())
	}
	if err := mock.Close(); err != nil {
		t.Fatal(err)
	}
}

// lockProbe is a log handler that counts the records logged while p.mu was held.
type lockProbe struct {
	p          *Producer
	logs, held int
}

func (h *lockProbe) Enabled(context.Context, slog.Level) bool { return true }
func (h *lockProbe) WithAttrs([]slog.Attr) slog.Handler       { return h }
func (h *lockProbe) WithGroup(string) slog.Handler            { return h }

func (h *lockProbe) Handle(context.Context, slog.Record) error {
	h.logs++
	if h.p.mu.TryLock() {
		h.p.mu.Unlock()
	} else {
		h.held++
	}
	return nil
}

func TestPermanentRejectionIsDropped(t *testing.T) {
	for _, rejection := range []error{
		sarama.ErrMessageSizeTooLarge,
		sarama.ConfigurationError("Attempt to produce message larger than configured Producer.MaxMessageBytes: 1048577 > 1048576"),
		sarama.ErrInvalidTopic,
		sarama.ErrInvalidRecord,
	} {
		t.Run(rejection.Error(), func(t *testing.T) {
			mock := newMockProducer(t)
			mock.ExpectInputAndFail(rejection)
			var logs syncBuffer
			p := newProducer(mock, 10, time.Hour, slog.New(slog.NewTextHandler(&logs, nil)))

			if err := p.Send(context.Background(), newMessage("order-1")); !errors.Is(err, rejection) {
				t.Fatalf("Send() error = %v, want %v", err, rejection)
			}
			if n := p.queued(); n != 0 {
				t.Errorf("queued = %d, want 0", n)
			}
			if !strings.Contains(logs.String(), "Kafka rejected the message, dropping it without retry") {
				t.Errorf("drop not logged, logs:\n%s", logs.String())
			}
			if err := mock.Close(); err != nil {
				t.Fatal(err)
			}
		})
	}
}

func TestPermanentRejectionOnRetryDoesNotBlockTheQueue(t *testing.T) {
	mock := newMockProducer(t)
	var rec recorder
	mock.ExpectInputWithMessageCheckerFunctionAndFail(rec.check(sarama.ErrMessageSizeTooLarge), sarama.ErrMessageSizeTooLarge)
	mock.ExpectInputWithMessageCheckerFunctionAndSucceed(rec.check(nil))
	var logs syncBuffer
	p := newProducer(mock, 10, 10*time.Millisecond, slog.New(slog.NewTextHandler(&logs, nil)))

	p.mu.Lock()
	p.queue = append(p.queue, newMessage("order-1"), newMessage("order-2"))
	p.mu.Unlock()
	p.wake <- struct{}{}

	waitFor(t, "order-2 to be delivered", func() bool {
		return strings.Contains(logs.String(), "Delivered queued Kafka message on retry")
	})
	if got, want := rec.delivered(), []string{"order-1", "order-2"}; fmt.Sprint(got) != fmt.Sprint(want) {
		t.Errorf("messages the broker saw = %v, want %v", got, want)
	}
	if n := p.queued(); n != 0 {
		t.Errorf("queued = %d, want 0", n)
	}
	if !strings.Contains(logs.String(), "Kafka rejected the message, dropping it without retry") {
		t.Errorf("drop not logged, logs:\n%s", logs.String())
	}
	if strings.Contains(logs.String(), "Retry of queued Kafka message failed") {
		t.Errorf("rejected message was retried, logs:\n%s", logs.String())
	}
	if err := mock.Close(); err != nil {
		t.Fatal(err)
	}
}

func TestShutdownDeliversQueuedMessages(t *testing.T) {
	mock := newMockProducer(t)
	var rec recorder
	mock.ExpectInputWithMessageCheckerFunctionAndFail(rec.check(errBrokerDown), errBrokerDown)
	mock.ExpectInputWithMessageCheckerFunctionAndSucceed(rec.check(nil))
	mock.ExpectInputWithMessageCheckerFunctionAndSucceed(rec.check(nil))
	var logs syncBuffer
	p := newProducer(mock, 10, time.Hour, slog.New(slog.NewTextHandler(&logs, nil)))
	// order-1 fails, order-2 is queued behind it, and the retry loop waits an hour.
	_ = p.Send(context.Background(), newMessage("order-1"))
	_ = p.Send(context.Background(), newMessage("order-2"))

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	p.Shutdown(ctx)
	if ctx.Err() != nil {
		t.Fatal("Shutdown returned only at the deadline")
	}
	if got, want := rec.delivered(), []string{"order-1", "order-1", "order-2"}; fmt.Sprint(got) != fmt.Sprint(want) {
		t.Errorf("messages the broker saw = %v, want %v", got, want)
	}
	if strings.Contains(logs.String(), "dropping") {
		t.Errorf("messages dropped, logs:\n%s", logs.String())
	}
	select {
	case _, open := <-mock.Successes():
		if open {
			t.Error("unexpected success after Shutdown")
		}
	case <-time.After(time.Second):
		t.Error("Shutdown did not close the producer")
	}
}

func TestShutdownLogsDroppedMessages(t *testing.T) {
	mock := newMockProducer(t)
	mock.ExpectInputAndFail(errBrokerDown) // the first send of order-1
	mock.ExpectInputAndFail(errBrokerDown) // the last attempt at shutdown
	var logs syncBuffer
	p := newProducer(mock, 10, time.Hour, slog.New(slog.NewTextHandler(&logs, nil)))
	for i := 1; i <= 3; i++ {
		_ = p.Send(context.Background(), newMessage(fmt.Sprintf("order-%d", i)))
	}

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	p.Shutdown(ctx)
	if !strings.Contains(logs.String(), "Shutting down with 3 messages in the Kafka retry queue, dropping them") {
		t.Errorf("drop not logged, logs:\n%s", logs.String())
	}
}

func TestShutdownReturnsAtTheDeadline(t *testing.T) {
	mock := newMockProducer(t)
	release := make(chan struct{})
	mock.ExpectInputWithMessageCheckerFunctionAndSucceed(func(*sarama.ProducerMessage) error {
		<-release
		return nil
	})
	var logs syncBuffer
	p := newProducer(mock, 10, time.Hour, slog.New(slog.NewTextHandler(&logs, nil)))
	p.enqueue(newMessage("order-1"))
	p.enqueue(newMessage("order-2"))

	ctx, cancel := context.WithTimeout(context.Background(), 100*time.Millisecond)
	defer cancel()
	start := time.Now()
	p.Shutdown(ctx) // the broker does not answer the last attempt for order-1
	if d := time.Since(start); d > 2*time.Second {
		t.Errorf("Shutdown took %v, want about 100ms", d)
	}
	if !strings.Contains(logs.String(), "Shutting down with 1 messages in the Kafka retry queue, dropping them") {
		t.Errorf("drop not logged, logs:\n%s", logs.String())
	}
	close(release)
	select {
	case <-p.retryDone:
	case <-time.After(5 * time.Second):
		t.Fatal("the retry loop did not stop after its last attempt")
	}
	// Shutdown left the producer open, so it can be closed here.
	if err := mock.Close(); err != nil {
		t.Fatal(err)
	}
}

func TestSendQueuesBehindQueuedMessages(t *testing.T) {
	mock := newMockProducer(t)
	p := newProducer(mock, 10, time.Hour, slog.New(slog.DiscardHandler))
	p.enqueue(newMessage("order-1"))

	ctx, cancel := context.WithTimeout(context.Background(), time.Second)
	defer cancel()
	if err := p.Send(ctx, newMessage("order-2")); !errors.Is(err, errQueuedBehind) {
		t.Fatalf("Send() error = %v, want %v", err, errQueuedBehind)
	}
	if got, want := queuedValues(p), []string{"order-1", "order-2"}; fmt.Sprint(got) != fmt.Sprint(want) {
		t.Errorf("queue = %v, want %v", got, want)
	}
	// The mock has no expectations, so it fails the test if anything was sent.
	if err := mock.Close(); err != nil {
		t.Fatal(err)
	}
}

func TestSendQueuesBehindMessageBeingResent(t *testing.T) {
	mock := newMockProducer(t)
	var rec recorder
	entered, release := make(chan struct{}), make(chan struct{})
	mock.ExpectInputWithMessageCheckerFunctionAndSucceed(func(msg *sarama.ProducerMessage) error {
		close(entered)
		<-release
		return rec.check(nil)(msg)
	})
	mock.ExpectInputWithMessageCheckerFunctionAndSucceed(rec.check(nil))
	var logs syncBuffer
	p := newProducer(mock, 10, time.Millisecond, slog.New(slog.NewTextHandler(&logs, nil)))
	p.enqueue(newMessage("order-1"))
	<-entered // the retry loop took order-1 from the queue and is resending it

	ctx, cancel := context.WithTimeout(context.Background(), time.Second)
	defer cancel()
	if err := p.Send(ctx, newMessage("order-2")); !errors.Is(err, errQueuedBehind) {
		t.Fatalf("Send() error = %v, want %v", err, errQueuedBehind)
	}
	close(release)
	waitFor(t, "both messages to be delivered", func() bool {
		return strings.Count(logs.String(), "Delivered queued Kafka message on retry") == 2
	})
	if got, want := rec.delivered(), []string{"order-1", "order-2"}; fmt.Sprint(got) != fmt.Sprint(want) {
		t.Errorf("messages in the order the broker saw them = %v, want %v", got, want)
	}
	if err := mock.Close(); err != nil {
		t.Fatal(err)
	}
}

func TestDropIsLoggedAfterReleasingTheLock(t *testing.T) {
	mock := newMockProducer(t)
	probe := &lockProbe{}
	p := newProducer(mock, 1, time.Hour, slog.New(probe))
	probe.p = p

	p.enqueue(newMessage("order-1"))
	p.enqueue(newMessage("order-2"))
	if got, want := queuedValues(p), []string{"order-2"}; fmt.Sprint(got) != fmt.Sprint(want) {
		t.Errorf("queue = %v, want %v", got, want)
	}
	if probe.logs != 1 || probe.held != 0 {
		t.Errorf("drop log lines = %d, logged while holding the lock = %d, want 1 and 0", probe.logs, probe.held)
	}
	if err := mock.Close(); err != nil {
		t.Fatal(err)
	}
}

func TestZeroQueueSizeDropsFailedMessage(t *testing.T) {
	mock := newMockProducer(t)
	mock.ExpectInputAndFail(errBrokerDown)
	var logs syncBuffer
	p := newProducer(mock, 0, time.Hour, slog.New(slog.NewTextHandler(&logs, nil)))

	if p.RetryEnabled() {
		t.Error("RetryEnabled() = true, want false for queue size 0")
	}
	if err := p.Send(context.Background(), newMessage("order-1")); !errors.Is(err, errBrokerDown) {
		t.Fatalf("Send() error = %v, want %v", err, errBrokerDown)
	}
	if n := p.queued(); n != 0 {
		t.Errorf("queued = %d, want 0", n)
	}
	if n := strings.Count(logs.String(), "Kafka retry queue is disabled"); n != 1 {
		t.Errorf("drop log lines = %d, want 1, logs:\n%s", n, logs.String())
	}
	if err := mock.Close(); err != nil {
		t.Fatal(err)
	}
}

func TestGetRetryQueueSize(t *testing.T) {
	for _, tc := range []struct {
		value string
		want  int
		warn  bool
	}{
		{"", defaultRetryQueueSize, false},
		{"0", 0, false},
		{"25", 25, false},
		{"abc", defaultRetryQueueSize, true},
		{"-1", defaultRetryQueueSize, true},
	} {
		t.Run(tc.value, func(t *testing.T) {
			t.Setenv("KAFKA_RETRY_QUEUE_SIZE", tc.value)
			var logs syncBuffer
			if got := getRetryQueueSize(slog.New(slog.NewTextHandler(&logs, nil))); got != tc.want {
				t.Errorf("getRetryQueueSize() = %d, want %d", got, tc.want)
			}
			if warned := strings.Contains(logs.String(), "Invalid KAFKA_RETRY_QUEUE_SIZE"); warned != tc.warn {
				t.Errorf("warning logged = %v, want %v, logs:\n%s", warned, tc.warn, logs.String())
			}
		})
	}
}

func TestFailureAfterContextDoneIsQueued(t *testing.T) {
	mock := newMockProducer(t)
	release := make(chan struct{})
	mock.ExpectInputWithMessageCheckerFunctionAndFail(func(*sarama.ProducerMessage) error {
		<-release
		return nil
	}, errBrokerDown)
	var logs syncBuffer
	p := newProducer(mock, 10, time.Hour, slog.New(slog.NewTextHandler(&logs, nil)))

	ctx, cancel := context.WithTimeout(context.Background(), 100*time.Millisecond)
	defer cancel()
	err := p.Send(ctx, newMessage("order-1"))
	if !errors.Is(err, ErrInFlight) || !errors.Is(err, context.DeadlineExceeded) {
		t.Fatalf("Send() error = %v, want %v and %v", err, ErrInFlight, context.DeadlineExceeded)
	}
	if n := p.queued(); n != 0 {
		t.Fatalf("queued = %d before the broker answered, want 0", n)
	}
	close(release)
	waitFor(t, "the late failure to be queued", func() bool { return p.queued() == 1 })
	if !strings.Contains(logs.String(), "Failed to write message after the context ended: broker down") {
		t.Errorf("late failure not logged, logs:\n%s", logs.String())
	}
	if err := mock.Close(); err != nil {
		t.Fatal(err)
	}
}

func TestSuccessAfterContextDoneIsLogged(t *testing.T) {
	mock := newMockProducer(t)
	release := make(chan struct{})
	mock.ExpectInputWithMessageCheckerFunctionAndSucceed(func(*sarama.ProducerMessage) error {
		<-release
		return nil
	})
	var logs syncBuffer
	p := newProducer(mock, 10, time.Hour, slog.New(slog.NewTextHandler(&logs, nil)))

	ctx, cancel := context.WithTimeout(context.Background(), 100*time.Millisecond)
	defer cancel()
	err := p.Send(ctx, newMessage("order-1"))
	if !errors.Is(err, ErrInFlight) || !errors.Is(err, context.DeadlineExceeded) {
		t.Fatalf("Send() error = %v, want %v and %v", err, ErrInFlight, context.DeadlineExceeded)
	}
	close(release)
	waitFor(t, "the late delivery to be logged", func() bool {
		return strings.Contains(logs.String(), "Delivered Kafka message after the context ended. offset: 1")
	})
	if n := p.queued(); n != 0 {
		t.Errorf("queued = %d, want 0", n)
	}
	if err := mock.Close(); err != nil {
		t.Fatal(err)
	}
}

func TestMessagesSentWithoutSendDoNotTakeResults(t *testing.T) {
	mock := newMockProducer(t)
	mock.ExpectInputAndSucceed()
	mock.ExpectInputAndFail(errBrokerDown)
	mock.ExpectInputAndSucceed()
	var logs syncBuffer
	p := newProducer(mock, 10, time.Hour, slog.New(slog.NewTextHandler(&logs, nil)))

	p.Input() <- newMessage("overload-1")
	p.Input() <- newMessage("overload-2")
	msg := newMessage("order-1")
	if err := p.Send(context.Background(), msg); err != nil {
		t.Fatalf("Send() error = %v, want nil", err)
	}
	if msg.Offset != 2 {
		t.Errorf("offset = %d, want 2", msg.Offset)
	}
	if n := p.queued(); n != 0 {
		t.Errorf("queued = %d, want 0", n)
	}
	if err := mock.Close(); err != nil {
		t.Fatal(err)
	}
	waitFor(t, "the error of the untracked message to be logged", func() bool {
		return strings.Contains(logs.String(), "Failed to write message: broker down")
	})
}

func TestConcurrentSendsGetTheirOwnResult(t *testing.T) {
	const sends = 200
	mock := newMockProducer(t)
	var rec recorder
	for i := range sends {
		if i%2 == 0 {
			mock.ExpectInputWithMessageCheckerFunctionAndSucceed(rec.check(nil))
		} else {
			mock.ExpectInputWithMessageCheckerFunctionAndFail(rec.check(errBrokerDown), errBrokerDown)
		}
	}
	// The queue is disabled so that every send reaches the broker. With a queue,
	// sends that start after the first failure would be queued behind it.
	p := newProducer(mock, 0, time.Hour, slog.New(slog.DiscardHandler))

	got := make([]error, sends)
	var wg sync.WaitGroup
	for i := range sends {
		wg.Go(func() {
			got[i] = p.Send(context.Background(), newMessage(fmt.Sprintf("order-%d", i)))
		})
	}
	wg.Wait()

	for i := range sends {
		value := fmt.Sprintf("order-%d", i)
		rec.mu.Lock()
		want, seen := rec.result[value]
		rec.mu.Unlock()
		if !seen {
			t.Fatalf("broker never saw %s", value)
		}
		if !errors.Is(got[i], want) {
			t.Errorf("Send(%s) = %v, but the broker answered %v", value, got[i], want)
		}
	}
	if err := mock.Close(); err != nil {
		t.Fatal(err)
	}
}
