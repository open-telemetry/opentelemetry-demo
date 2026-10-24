# Copyright The OpenTelemetry Authors / Bosch Incident Zero Hackathon
# SPDX-License-Identifier: Apache-2.0

"""
Repository and Deployment Context Tool.
Distinguishes repository commit history from runtime deployments:
- Clearly labels git commits as repository code context only (not runtime rollout proof).
- Adheres to Hackathon Rule 6 (zero feature-flag file reading during diagnosis).
"""

import os
import subprocess
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from oncall.models import TelemetryObservation, TelemetryCitation


class DeploymentHistoryTool:
    def __init__(self):
        self.repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

    def get_git_deployment_history(self, limit: int = 3) -> Dict[str, Any]:
        """Fetch real git commit history with author and date to provide code context."""
        try:
            res = subprocess.run(
                ["git", "log", f"-n{limit}", "--pretty=format:%h|%an|%ad|%s", "--date=iso"],
                capture_output=True,
                text=True,
                timeout=3.0,
                check=False,
                cwd=self.repo_root
            )
            commits = []
            if res.returncode == 0 and res.stdout.strip():
                for line in res.stdout.splitlines():
                    parts = line.strip().split("|")
                    if len(parts) == 4:
                        commits.append({
                            "hash": parts[0],
                            "author": parts[1],
                            "date": parts[2],
                            "message": parts[3]
                        })
            return {"available": True, "commits": commits}
        except Exception as e:
            return {"available": False, "error": str(e), "commits": []}

    def inspect_deployment_and_flags(self, service_name: str) -> TelemetryObservation:
        """
        Audit recent repository commits relevant to the service.
        Strictly labels this as repository code context, distinguishing it from runtime rollout events.
        """
        git_history = self.get_git_deployment_history(3)
        has_git = git_history.get("available", False) and bool(git_history.get("commits"))
        
        if has_git:
            latest = git_history["commits"][0]
            commit_desc = f"[{latest['hash']}] '{latest['message']}' by {latest['author']} on {latest['date']}"
            summary = (
                f"Repository History Context for '{service_name}': Inspected commits on branch 'main'. "
                f"Latest commit: {commit_desc}. [Note: Repository history provides code context only; "
                f"no runtime rollout/deployment event verified in incident window]."
            )
            citations = [
                TelemetryCitation(
                    source_type="repository_context",
                    identifier=f"git:commit:{latest['hash']}",
                    summary=f"Repository commit {latest['hash']} provides code context (runtime rollout unverified)",
                    evidence_payload={
                        "commit_hash": latest["hash"],
                        "message": latest["message"],
                        "evidence_classification": "REPOSITORY_COMMIT_CONTEXT_ONLY"
                    }
                )
            ]
        else:
            summary = f"Repository Context for '{service_name}': Git commit history unavailable in isolated container."
            citations = []

        data = {
            "service_name": service_name,
            "git_deployment_history": git_history,
            "evidence_classification": "REPOSITORY_COMMIT_CONTEXT_ONLY",
            "runtime_rollout_verified": False
        }

        return TelemetryObservation(
            tool_name="deployment_history_inspect",
            success=True,
            summary=summary,
            data=data,
            citations=citations
        )
