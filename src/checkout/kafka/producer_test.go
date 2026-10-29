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
	for range 4 {
		mock.ExpectInputAndFail(errBrokerDown)
	}
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

func TestFailureAfterContextDoneIsQueued(t *testing.T) {
	mock := newMockProducer(t)
	release := make(chan struct{})
	mock.ExpectInputWithMessageCheckerFunctionAndFail(func(*sarama.ProducerMessage) error {
		<-release
		return nil
	}, errBrokerDown)
	p := newProducer(mock, 10, time.Hour, slog.New(slog.DiscardHandler))

	ctx, cancel := context.WithTimeout(context.Background(), 100*time.Millisecond)
	defer cancel()
	if err := p.Send(ctx, newMessage("order-1")); !errors.Is(err, context.DeadlineExceeded) {
		t.Fatalf("Send() error = %v, want %v", err, context.DeadlineExceeded)
	}
	if n := p.queued(); n != 0 {
		t.Fatalf("queued = %d before the broker answered, want 0", n)
	}
	close(release)
	waitFor(t, "the late failure to be queued", func() bool { return p.queued() == 1 })
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
	p := newProducer(mock, sends, time.Hour, slog.New(slog.DiscardHandler))

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
	if n := p.queued(); n != sends/2 {
		t.Errorf("queued = %d, want %d", n, sends/2)
	}
	if err := mock.Close(); err != nil {
		t.Fatal(err)
	}
}
