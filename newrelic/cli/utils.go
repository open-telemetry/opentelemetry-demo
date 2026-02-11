package main

import (
	"bufio"
	"fmt"
	"os"
	"os/exec"
	"strings"
)

func runCommand(name string, args []string, env []string) error {
	cmd := exec.Command(name, args...)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	cmd.Stdin = os.Stdin
	if env != nil {
		cmd.Env = env
	}
	if err := cmd.Run(); err != nil {
		fmt.Printf("Error running %s: %v\n", name, err)
		return err
	}
	return nil
}

func checkTools(tools ...string) {
	for _, t := range tools {
		if _, err := exec.LookPath(t); err != nil {
			fmt.Printf("Error: %s is not installed.\n", t)
			os.Exit(1)
		}
	}
}

// createPatchedTempFile reads a template, applies replacements, and returns the path to a temp file.
// The caller is responsible for calling the returned cleanup function.
func createPatchedTempFile(originalPath string, replacements map[string]string) (string, func(), error) {
	content, err := os.ReadFile(originalPath)
	if err != nil {
		return "", nil, fmt.Errorf("could not read template %s: %v", originalPath, err)
	}

	newContent := string(content)
	for oldStr, newStr := range replacements {
		newContent = strings.ReplaceAll(newContent, oldStr, newStr)
	}

	tmpFile, err := os.CreateTemp("", "nr-otel-tmp-*")
	if err != nil {
		return "", nil, fmt.Errorf("could not create temp file: %v", err)
	}

	if _, err := tmpFile.Write([]byte(newContent)); err != nil {
		os.Remove(tmpFile.Name())
		return "", nil, fmt.Errorf("could not write to temp file: %v", err)
	}
	tmpFile.Close()

	cleanup := func() { os.Remove(tmpFile.Name()) }
	return tmpFile.Name(), cleanup, nil
}

// -- Input & Validation Helpers --

func promptUser(label string, validator func(string) error) string {
	fmt.Printf("\x1b[?2004l") // Disable bracketed paste
	defer fmt.Printf("\x1b[?2004h")
	reader := bufio.NewReader(os.Stdin)
	for {
		fmt.Printf("%s: ", label)
		rawInput, _ := reader.ReadString('\n')
		cleanedInput := strings.TrimSpace(rawInput)
		if validator != nil {
			if err := validator(cleanedInput); err != nil {
				fmt.Printf("Invalid input: %v. Please try again.\n", err)
				continue
			}
		}
		if cleanedInput != "" {
			return cleanedInput
		}
	}
}

func promptBool(label string) bool {
	reader := bufio.NewReader(os.Stdin)
	for {
		fmt.Printf("%s [y/N]: ", label)
		text, _ := reader.ReadString('\n')
		text = strings.TrimSpace(strings.ToLower(text))
		if text == "y" || text == "yes" {
			return true
		}
		if text == "n" || text == "no" || text == "" {
			return false
		}
	}
}

func getEnvOrDefault(key, def string) string {
	if val := os.Getenv(key); val != "" {
		return val
	}
	return def
}

func validateLicenseKey(val string) error {
	if len(val) != 40 || !strings.HasSuffix(val, "NRAL") {
		return fmt.Errorf("must be 40 chars and end with 'NRAL'")
	}
	return nil
}

func validateUserApiKey(val string) error {
	if !strings.HasPrefix(val, "NRAK-") || len(val) != 32 {
		return fmt.Errorf("must start with 'NRAK-' and be 32 chars")
	}
	return nil
}

func validateNotEmpty(val string) error {
	if strings.TrimSpace(val) == "" {
		return fmt.Errorf("value is required")
	}
	return nil
}
