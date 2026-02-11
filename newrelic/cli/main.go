package main

import (
	"bufio"
	"fmt"
	"os"
	"strings"
)

// ANSI Color Codes
const (
	ColorReset  = "\033[0m"
	ColorCyan   = "\033[36m"
	ColorGreen  = "\033[32m"
	ColorYellow = "\033[33m"
	ColorRed    = "\033[31m"
	ColorBold   = "\033[1m"
	ColorDim    = "\033[2m"
)

func main() {
	config, positionals := parseArgs()

	if len(os.Args) > 1 && (os.Args[1] == "-h" || os.Args[1] == "--help") {
		printUsage()
		return
	}

	if len(positionals) >= 2 {
		config.Action, config.Target = positionals[0], positionals[1]
		if !isValidAction(config.Action) || !isValidTarget(config.Target) {
			fmt.Printf("%sError: Invalid action '%s' or target '%s'%s\n", ColorRed, config.Action, config.Target, ColorReset)
			os.Exit(1)
		}
		loadConfig(&config)
		runHandler(config.Action, config.Target, &config)
		return
	}

	interactiveLoop(&config)
}

func runHandler(action, target string, cfg *Config) {
	loadConfig(cfg)
	switch target {
	case "account", "resources":
		handleTerraform(action, target, cfg)
	case "docker":
		handleDocker(action, cfg)
	case "k8s":
		handleK8s(action, cfg)
	}
}

func interactiveLoop(cfg *Config) {
	printHeader()

	loadConfig(cfg)
	scanner := bufio.NewScanner(os.Stdin)

	// Track lines to clear for inline updates
	lastLines := 0

	for {
		// Clear previous Step 1 menu if it exists
		clearLines(lastLines)

		// Print Step 1 Menu
		printCurrentState(cfg)
		fmt.Printf("\n%sChoose an ACTION:%s\n", ColorCyan+ColorBold, ColorReset)
		fmt.Println("  1. Install")
		fmt.Println("  2. Upgrade")
		fmt.Println("  3. Uninstall")
		fmt.Println("  4. Exit")
		fmt.Printf("\n%sSelection: %s", ColorCyan, ColorReset)

		// Total Lines: 8 (State) + 2 (Header) + 4 (Options) + 1 (Newline) + 1 (Input) = 16
		lastLines = 16

		if !scanner.Scan() {
			return
		}
		switch strings.TrimSpace(scanner.Text()) {
		case "1":
			cfg.Action = "install"
		case "2":
			cfg.Action = "upgrade"
		case "3":
			cfg.Action = "uninstall"
		case "4", "exit", "q":
			return
		default:
			continue
		}

		// Step 2 Loop
		step2Lines := lastLines

		for {
			clearLines(step2Lines)

			printCurrentState(cfg)
			fmt.Printf("\n%sAction: %s | Choose a TARGET:%s\n", ColorCyan+ColorBold, strings.ToUpper(cfg.Action), ColorReset)
			fmt.Println("  1. K8s          (Helm)")
			fmt.Println("  2. Docker       (Compose)")
			fmt.Println("  3. Account      (Terraform)")
			fmt.Println("  4. Resources    (Terraform)")
			fmt.Println("  5. <-- Back to Action Menu")
			fmt.Printf("\n%sSelection: %s", ColorCyan, ColorReset)

			// Total Lines: 8 (State) + 2 (Header) + 5 (Options) + 1 (Newline) + 1 (Input) = 17
			step2Lines = 17

			if !scanner.Scan() {
				return
			}
			choice := strings.TrimSpace(scanner.Text())
			back := false

			switch choice {
			case "1":
				cfg.Target = "k8s"
			case "2":
				cfg.Target = "docker"
			case "3":
				cfg.Target = "account"
			case "4":
				cfg.Target = "resources"
			case "5", "b", "back":
				back = true
			default:
				continue
			}

			if back {
				lastLines = step2Lines
				break
			}

			// Clear menu before execution
			clearLines(step2Lines)

			// Persist state display during execution
			printCurrentState(cfg)

			fmt.Printf("\n%s>>> Executing: %s %s%s\n", ColorGreen+ColorBold, strings.ToUpper(cfg.Action), strings.ToUpper(cfg.Target), ColorReset)

			runHandler(cfg.Action, cfg.Target, cfg)

			loadConfig(cfg)

			lastLines = 0
			fmt.Printf("\n%sExecution Complete. Returning to Action menu...%s\n", ColorGreen, ColorReset)
			break
		}
	}
}

func clearLines(n int) {
	if n <= 0 {
		return
	}
	for i := 0; i < n; i++ {
		fmt.Print("\033[1A\033[2K")
	}
}

func printHeader() {
	fmt.Println(ColorCyan + "=======================================================" + ColorReset)
	fmt.Println(ColorBold + "New Relic OpenTelemetry Demo - CLI" + ColorReset)
}

func parseArgs() (Config, []string) {
	cfg := Config{}
	var positionals []string
	args := os.Args[1:]

	for i := 0; i < len(args); i++ {
		arg := args[i]
		if strings.HasPrefix(arg, "-") {
			cleanArg := strings.TrimLeft(arg, "-")
			if cleanArg == "h" || cleanArg == "help" {
				printUsage()
				os.Exit(0)
			}
			parts := strings.SplitN(cleanArg, "=", 2)
			key := parts[0]
			val := ""
			if len(parts) == 2 {
				val = parts[1]
			} else if i+1 < len(args) && !strings.HasPrefix(args[i+1], "-") {
				val = args[i+1]
				i++
			}
			switch key {
			case "NEW_RELIC_LICENSE_KEY":
				cfg.LicenseKey = val
			case "NEW_RELIC_API_KEY":
				cfg.ApiKey = val
			case "NEW_RELIC_ACCOUNT_ID":
				cfg.AccountId = val
			case "NEW_RELIC_REGION":
				cfg.Region = strings.ToUpper(val)
			case "NEW_RELIC_ENABLE_BROWSER":
				if val == "" || strings.ToLower(val) == "true" {
					b := true
					cfg.EnableBrowser = &b
				}
			case "TF_VAR_SUBACCOUNT_NAME":
				cfg.SubaccountName = val
			case "TF_VAR_ADMIN_GROUP_NAME":
				cfg.AdminGroupName = val
			case "TF_VAR_READONLY_USER_EMAIL":
				cfg.ReadonlyUserEmail = val
			case "TF_VAR_READONLY_USER_NAME":
				cfg.ReadonlyUserName = val
			case "BROWSER_LICENSE_KEY", "BROWSER_APPLICATION_ID", "BROWSER_ACCOUNT_ID", "BROWSER_TRUST_KEY", "BROWSER_AGENT_ID":
				if cfg.Browser == nil {
					cfg.Browser = make(map[string]string)
				}
				cfg.Browser[strings.TrimPrefix(key, "BROWSER_")] = val
			}
		} else {
			positionals = append(positionals, arg)
		}
	}
	return cfg, positionals
}

func printUsage() {
	fmt.Printf(`
%sNew Relic OpenTelemetry Demo CLI%s

USAGE:
  # Interactive Mode
  go run newrelic-opentelemetry-demo.go

  # Batch Mode
  go run newrelic-opentelemetry-demo.go <action> <target> [flags]

ACTIONS:
  install     - Initialize and deploy the specified target
  upgrade     - Update an existing deployment
  uninstall   - Remove resources associated with the target

TARGETS:
  account     - Provision a New Relic sub-account via Terraform
  resources   - Create SLOs and other New Relic entities via Terraform
  k8s         - Deploy the demo to Kubernetes using Helm
  docker      - Deploy the demo using Docker Compose

GLOBAL FLAGS:
  --NEW_RELIC_REGION          - New Relic Region: "US" or "EU" (Default: US)
  --NEW_RELIC_ENABLE_BROWSER  - Set to "true" to enable Browser Monitoring (K8s/Docker only)

INSTALL FLAGS:
  --NEW_RELIC_LICENSE_KEY     - New Relic License Key (ends in NRAL; K8s/Docker only)

BROWSER FLAGS (Used if NEW_RELIC_ENABLE_BROWSER is true):
  --BROWSER_LICENSE_KEY       - New Relic Browser License Key
  --BROWSER_APPLICATION_ID    - New Relic Browser App ID
  --BROWSER_ACCOUNT_ID        - New Relic Browser Account ID
  --BROWSER_TRUST_KEY         - New Relic Browser Trust Key
  --BROWSER_AGENT_ID          - New Relic Browser Agent ID

TERRAFORM RESOURCES FLAGS (Required for 'resources' target):
  --NEW_RELIC_API_KEY           - New Relic User API Key (starts with NRAK-)

TERRAFORM ACCOUNT FLAGS (Required for 'account' target):
  --NEW_RELIC_API_KEY          - New Relic User API Key (starts with NRAK-)
  --NEW_RELIC_ACCOUNT_ID       - New Relic Parent Account
  --TF_VAR_SUBACCOUNT_NAME     - Display name for the new sub-account
  --TF_VAR_ADMIN_GROUP_NAME    - Name of an existing group to grant Admin access
  --TF_VAR_READONLY_USER_NAME  - Display name for the new read-only user
  --TF_VAR_READONLY_USER_EMAIL - Email address for the new read-only user

All flags above can also be set as environment variables.
If required values are missing, the CLI will prompt for them interactively.
`, ColorBold, ColorReset)
}

func isValidAction(a string) bool { return a == "install" || a == "upgrade" || a == "uninstall" }
func isValidTarget(t string) bool {
	return t == "k8s" || t == "docker" || t == "account" || t == "resources"
}

func printCurrentState(cfg *Config) {
	browserStatus := ColorDim + "Disabled" + ColorReset
	if cfg.EnableBrowser != nil {
		if *cfg.EnableBrowser {
			browserStatus = ColorGreen + "Enabled" + ColorReset
		} else {
			browserStatus = ColorYellow + "Disabled" + ColorReset
		}
	}

	fmt.Println(ColorCyan + "=======================================================" + ColorReset)
	fmt.Printf("%sCurrent Configuration:%s\n", ColorBold, ColorReset)
	fmt.Printf("  %sRegion:%s     %s\n", ColorCyan, ColorReset, cfg.Region)
	fmt.Printf("  %sAccount ID:%s %s\n", ColorCyan, ColorReset, isEmpty(cfg.AccountId))
	fmt.Printf("  %sLicense:%s    %s\n", ColorCyan, ColorReset, maskString(cfg.LicenseKey))
	fmt.Printf("  %sAPI Key:%s    %s\n", ColorCyan, ColorReset, maskString(cfg.ApiKey))
	fmt.Printf("  %sBrowser:%s    %s\n", ColorCyan, ColorReset, browserStatus)
	fmt.Println(ColorCyan + "=======================================================" + ColorReset)
}

func isEmpty(s string) string {
	if len(s) == 0 {
		return ColorDim + "N/A" + ColorReset
	}
	return s
}
func maskString(s string) string {
	if len(s) == 0 {
		return ColorDim + "N/A" + ColorReset
	}
	if len(s) <= 10 {
		return s
	}
	return s[:10] + "..."
}
