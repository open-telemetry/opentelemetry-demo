package main

import (
	"github.com/sirupsen/logrus"
)

type LogFields map[string]interface{}

func logWithFields(l *logrus.Logger, level logrus.Level, msg string, fields LogFields) {
	// Always add service name
	if fields == nil {
		fields = LogFields{}
	}
	fields["service.name"] = "checkout"

	entry := l.WithFields(logrus.Fields(fields))
	switch level {
	case logrus.DebugLevel:
		entry.Debug(msg)
	case logrus.InfoLevel:
		entry.Info(msg)
	case logrus.WarnLevel:
		entry.Warn(msg)
	case logrus.ErrorLevel:
		entry.Error(msg)
	case logrus.FatalLevel:
		entry.Fatal(msg)
	}
}

func logDebug(msg string, fields LogFields) {
	logWithFields(log, logrus.DebugLevel, msg, fields)
}

func logInfo(msg string, fields LogFields) {
	logWithFields(log, logrus.InfoLevel, msg, fields)
}

func logWarn(msg string, fields LogFields) {
	logWithFields(log, logrus.WarnLevel, msg, fields)
}

func logError(msg string, fields LogFields) {
	logWithFields(log, logrus.ErrorLevel, msg, fields)
}

func logFatal(msg string, fields LogFields) {
	logWithFields(log, logrus.FatalLevel, msg, fields)
}
