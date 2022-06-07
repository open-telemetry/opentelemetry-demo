package instr

import "go.opentelemetry.io/otel/attribute"

const AppPrefix = "app."

const (
	SessionId = attribute.Key(AppPrefix + "session.id")
	RequestId = attribute.Key(AppPrefix + "request.id")
	UserId    = attribute.Key(AppPrefix + "user.id")

	Currency = attribute.Key(AppPrefix + "currency")
)
