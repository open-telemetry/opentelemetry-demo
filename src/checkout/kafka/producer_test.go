// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
package kafka

import (
	"testing"

	"github.com/IBM/sarama"
)

func TestConfigureSecurity(t *testing.T) {
	tests := []struct {
		name            string
		env             map[string]string
		wantErr         bool
		wantTLS         bool
		wantSASL        bool
		wantMechanism   sarama.SASLMechanism
		wantSCRAM       bool
	}{
		{name: "unset keeps plaintext", env: map[string]string{}},
		{name: "plaintext", env: map[string]string{"KAFKA_SECURITY_PROTOCOL": "PLAINTEXT"}},
		{name: "ssl", env: map[string]string{"KAFKA_SECURITY_PROTOCOL": "SSL"}, wantTLS: true},
		{
			name: "sasl_ssl defaults to plain",
			env: map[string]string{"KAFKA_SECURITY_PROTOCOL": "SASL_SSL",
				"KAFKA_SASL_USERNAME": "user", "KAFKA_SASL_PASSWORD": "secret"},
			wantTLS:       true,
			wantSASL:      true,
			wantMechanism: sarama.SASLTypePlaintext,
		},
		{
			name: "sasl_plaintext scram-sha-256",
			env: map[string]string{"KAFKA_SECURITY_PROTOCOL": "sasl_plaintext",
				"KAFKA_SASL_MECHANISM": "scram-sha-256", "KAFKA_SASL_USERNAME": "user",
				"KAFKA_SASL_PASSWORD": "secret"},
			wantSASL:      true,
			wantMechanism: sarama.SASLTypeSCRAMSHA256,
			wantSCRAM:     true,
		},
		{
			name: "sasl_ssl scram-sha-512",
			env: map[string]string{"KAFKA_SECURITY_PROTOCOL": "SASL_SSL",
				"KAFKA_SASL_MECHANISM": "SCRAM-SHA-512", "KAFKA_SASL_USERNAME": "user",
				"KAFKA_SASL_PASSWORD": "secret"},
			wantTLS:       true,
			wantSASL:      true,
			wantMechanism: sarama.SASLTypeSCRAMSHA512,
			wantSCRAM:     true,
		},
		{name: "unknown protocol", env: map[string]string{"KAFKA_SECURITY_PROTOCOL": "TLS"}, wantErr: true},
		{name: "unknown mechanism", env: map[string]string{"KAFKA_SECURITY_PROTOCOL": "SASL_SSL", "KAFKA_SASL_MECHANISM": "GSSAPI"}, wantErr: true},
		{name: "missing username", env: map[string]string{"KAFKA_SECURITY_PROTOCOL": "SASL_SSL", "KAFKA_SASL_PASSWORD": "secret"}, wantErr: true},
		{name: "missing password", env: map[string]string{"KAFKA_SECURITY_PROTOCOL": "SASL_SSL", "KAFKA_SASL_USERNAME": "user"}, wantErr: true},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			for _, key := range []string{"KAFKA_SECURITY_PROTOCOL", "KAFKA_SASL_MECHANISM", "KAFKA_SASL_USERNAME", "KAFKA_SASL_PASSWORD"} {
				t.Setenv(key, tt.env[key])
			}

			cfg := sarama.NewConfig()

			err := configureSecurity(cfg)

			if (err != nil) != tt.wantErr {
				t.Fatalf("configureSecurity() error = %v, wantErr %v", err, tt.wantErr)
			}

			if tt.wantErr {
				return
			}

			if cfg.Net.TLS.Enable != tt.wantTLS {
				t.Errorf("TLS.Enable = %v, want %v", cfg.Net.TLS.Enable, tt.wantTLS)
			}

			if cfg.Net.SASL.Enable != tt.wantSASL {
				t.Errorf("SASL.Enable = %v, want %v", cfg.Net.SASL.Enable, tt.wantSASL)
			}

			if tt.wantSASL && cfg.Net.SASL.Mechanism != tt.wantMechanism {
				t.Errorf("SASL.Mechanism = %v, want %v", cfg.Net.SASL.Mechanism, tt.wantMechanism)
			}

			if (cfg.Net.SASL.SCRAMClientGeneratorFunc != nil) != tt.wantSCRAM {
				t.Errorf("SCRAMClientGeneratorFunc set = %v, want %v", cfg.Net.SASL.SCRAMClientGeneratorFunc != nil, tt.wantSCRAM)
			}

			if err := cfg.Validate(); err != nil {
				t.Errorf("sarama config does not validate: %v", err)
			}
		})
	}
}
