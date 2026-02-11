package main

import (
	"fmt"
	"os"
	"os/exec"
	"strings"
)

func handleTerraform(action, target string, cfg *Config) {
	checkTools("terraform", "jq", "curl")
	tfPath := Paths["tf-account"]
	if target == "resources" {
		tfPath = Paths["tf-resources"]
	}

	env := buildEnvMap(cfg)
	tfArgs := []string{"-chdir=" + tfPath}
	autoApprove := ""
	if os.Getenv("TF_AUTO_APPROVE") == "true" {
		autoApprove = "-auto-approve"
	}

	if action == "uninstall" {
		runCommand("terraform", append(tfArgs, "destroy", autoApprove), env)
		return
	}

	if err := runCommand("terraform", append(tfArgs, "init"), env); err != nil {
		return
	}

	if target == "account" {
		runCommand("terraform", append(tfArgs, "apply", "-target=newrelic_account_management.subaccount", autoApprove), env)
		out, _ := exec.Command("terraform", append(tfArgs, "output", "-raw", "account_id")...).Output()
		if id := strings.TrimSpace(string(out)); id != "" {
			fmt.Printf("Captured New Sub-Account ID: %s\n", id)
			cfg.AccountId = id
			env = buildEnvMap(cfg)
		}
	}

	if err := runCommand("terraform", append(tfArgs, "apply", autoApprove), env); err != nil {
		return
	}

	if target == "account" {
		out, err := exec.Command("terraform", append(tfArgs, "output", "-raw", "license_key")...).Output()
		if err == nil {
			licenseKey := strings.TrimSpace(string(out))
			if licenseKey != "" {
				cfg.LicenseKey = licenseKey
				os.Setenv("NEW_RELIC_LICENSE_KEY", licenseKey)
				fmt.Printf("\nCaptured License Key: %s\n", licenseKey)
			}
		}
	}
}

func buildEnvMap(cfg *Config) []string {
	env := os.Environ()
	mapping := map[string]string{
		"TF_VAR_newrelic_api_key":           cfg.ApiKey,
		"TF_VAR_newrelic_parent_account_id": cfg.AccountId,
		"TF_VAR_newrelic_account_id":        cfg.AccountId,
		"TF_VAR_newrelic_region":            cfg.Region,
		"TF_VAR_subaccount_name":            cfg.SubaccountName,
		"TF_VAR_admin_group_name":           cfg.AdminGroupName,
		"TF_VAR_readonly_user_email":        cfg.ReadonlyUserEmail,
		"TF_VAR_readonly_user_name":         cfg.ReadonlyUserName,
	}
	for k, v := range mapping {
		if v != "" {
			env = append(env, k+"="+v)
		}
	}
	return env
}
