package main

import (
	"os"
	"path/filepath"
	"strings"
)

const (
	OtelDemoChartVersion = "0.40.2"
	NrK8sChartVersion    = "0.10.0"
	OtelDemoNamespace    = "opentelemetry-demo"
)

var (
	isOpenShift = false

	Paths = map[string]string{
		"otel-values":         filepath.Join("..", "k8s", "helm", "opentelemetry-demo.yaml"),
		"otel-browser-values": filepath.Join("..", "k8s", "helm", "nr-browser.yaml"),
		"nr-k8s-values":       filepath.Join("..", "k8s", "helm", "nr-k8s-otel-collector.yaml"),
		"docker-compose":      filepath.Join("..", "docker", "docker-compose.yml"),
		"docker-patch":        filepath.Join("..", "docker", "config", "monkey-patch.js"),
		"tf-account":          filepath.Join("..", "terraform", "nr_account"),
		"tf-resources":        filepath.Join("..", "terraform", "nr_resources"),
	}

	Charts = map[string]struct{ Name, Repo, Version, NS string }{
		"nr-k8s":    {"nr-k8s-otel-collector", "newrelic/nr-k8s-otel-collector", NrK8sChartVersion, OtelDemoNamespace},
		"otel-demo": {"otel-demo", "open-telemetry/opentelemetry-demo", OtelDemoChartVersion, OtelDemoNamespace},
	}
)

type Config struct {
	LicenseKey, ApiKey, AccountId, Region, Target, Action string
	EnableBrowser                                         *bool
	SubaccountName, AdminGroupName                        string
	ReadonlyUserEmail, ReadonlyUserName                   string
	Browser                                               map[string]string
}

func loadConfig(cfg *Config) {
	if cfg.Region == "" {
		cfg.Region = strings.ToUpper(getEnvOrDefault("NEW_RELIC_REGION", "US"))
	}

	if cfg.LicenseKey == "" {
		cfg.LicenseKey = os.Getenv("NEW_RELIC_LICENSE_KEY")
	}
	if cfg.ApiKey == "" {
		cfg.ApiKey = os.Getenv("NEW_RELIC_API_KEY")
	}
	if cfg.AccountId == "" {
		cfg.AccountId = os.Getenv("NEW_RELIC_ACCOUNT_ID")
	}

	if cfg.Action == "uninstall" {
		return
	}

	if cfg.Target == "k8s" || cfg.Target == "docker" {
		if cfg.LicenseKey == "" {
			cfg.LicenseKey = promptUser("License Key (ends in NRAL)", validateLicenseKey)
		}

		// REMOVED: Global prompt for EnableBrowser.
		// We still check if it was set via flags (e.g. --NEW_RELIC_ENABLE_BROWSER=true)
		// allowing handlers to handle prompt
		if cfg.EnableBrowser != nil && *cfg.EnableBrowser {
			setupBrowser(cfg)
		}
	}

	if cfg.Target == "account" || cfg.Target == "resources" {
		if cfg.ApiKey == "" {
			cfg.ApiKey = promptUser("User API Key (NRAK)", validateUserApiKey)
		}
		if cfg.AccountId == "" {
			cfg.AccountId = promptUser("Parent Account ID", validateNotEmpty)
		}
	}

	if cfg.Target == "account" {
		if cfg.SubaccountName == "" {
			cfg.SubaccountName = promptUser("New Subaccount Name", validateNotEmpty)
		}
		if cfg.AdminGroupName == "" {
			cfg.AdminGroupName = promptUser("Existing Admin Group Name", validateNotEmpty)
		}
		if cfg.ReadonlyUserEmail == "" {
			cfg.ReadonlyUserEmail = promptUser("New Read-Only User Email", validateNotEmpty)
		}
		if cfg.ReadonlyUserName == "" {
			cfg.ReadonlyUserName = promptUser("New Read-Only User Name", validateNotEmpty)
		}
	}
}

func setupBrowser(cfg *Config) {
	keys := []string{"LICENSE_KEY", "APPLICATION_ID", "ACCOUNT_ID", "TRUST_KEY", "AGENT_ID"}
	if cfg.Browser == nil {
		cfg.Browser = make(map[string]string)
	}
	for _, k := range keys {
		if cfg.Browser[k] != "" {
			continue
		}
		envKey := "BROWSER_" + k
		if val := os.Getenv(envKey); val != "" {
			cfg.Browser[k] = val
			continue
		}
		cfg.Browser[k] = promptUser("Browser "+k, validateNotEmpty)
	}
}
