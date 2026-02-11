package main

import (
	"fmt"
	"os"
	"path/filepath"
)

func handleDocker(action string, cfg *Config) {
	checkTools("docker")

	// 1. Always use the standard docker-compose.yml as the base
	basePath := Paths["docker-compose"]

	// Define env file paths relative to cli/ (repo root)
	envPath := filepath.Join("..", "..", ".env")
	envOverridePath := filepath.Join("..", "..", ".env.override")

	if action == "uninstall" {
		args := []string{
			"compose",
			"--env-file", envPath,
			"--env-file", envOverridePath,
			"-f", basePath,
			"down",
		}
		env := append(os.Environ(), "NEW_RELIC_LICENSE_KEY=uninstall_dummy")
		runCommand("docker", args, env)
		return
	}

	// Explicitly ask if the user wants to enable Browser Monitoring
	enableBrowser := promptBool("Do you want to enable Digital Experience Monitoring (Browser)?")
	cfg.EnableBrowser = &enableBrowser
	if *cfg.EnableBrowser {
		setupBrowser(cfg)
	}

	// Track cleanups for temporary files
	var cleanups []func()
	defer func() {
		for _, clean := range cleanups {
			clean()
		}
	}()

	// 2. Start building args with just the base file
	args := []string{
		"compose",
		"--env-file", envPath,
		"--env-file", envOverridePath,
		"-f", basePath,
	}

	// 3. Dynamically append the browser override if enabled
	if cfg.EnableBrowser != nil && *cfg.EnableBrowser {
		replacements := map[string]string{
			"$LICENSE_KEY":    cfg.Browser["LICENSE_KEY"],
			"$APPLICATION_ID": cfg.Browser["APPLICATION_ID"],
			"$ACCOUNT_ID":     cfg.Browser["ACCOUNT_ID"],
			"$TRUST_KEY":      cfg.Browser["TRUST_KEY"],
			"$AGENT_ID":       cfg.Browser["AGENT_ID"],
		}

		tmpJsPath, jsCleanup, err := createPatchedTempFile(Paths["docker-patch"], replacements)
		if err == nil {
			cleanups = append(cleanups, jsCleanup)

			// Create the override YAML that mounts the patched file
			overrideContent := fmt.Sprintf(`
services:
  frontend:
    volumes:
      - %s:/app/monkey-patch.js
    command: 
      - "--require=./Instrumentation.js"
      - "--require=./monkey-patch.js"
      - "server.js"
`, tmpJsPath)

			tmpYaml, err := os.CreateTemp("", "tmp_docker-compose-*.yaml")
			if err == nil {
				tmpYaml.Write([]byte(overrideContent))
				tmpYaml.Close()
				cleanups = append(cleanups, func() { os.Remove(tmpYaml.Name()) })

				// Append the override file (-f) to the arguments.
				// Docker merges this ON TOP of the basePath.
				args = append(args, "-f", tmpYaml.Name())
			} else {
				fmt.Printf("Warning: Failed to create temp override YAML: %v\n", err)
			}
		} else {
			fmt.Printf("Warning: Failed to create temp patch JS: %v\n", err)
		}
	}

	// Final execution arguments
	args = append(args, "up", "--force-recreate", "--remove-orphans", "--detach")

	env := append(os.Environ(), "NEW_RELIC_LICENSE_KEY="+cfg.LicenseKey)
	runCommand("docker", args, env)
}
