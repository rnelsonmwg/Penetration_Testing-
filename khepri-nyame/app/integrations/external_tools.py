from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from typing import Sequence

from app.core.safety import validate_workflow_name


@dataclass
class ToolResult:
    tool: str
    available: bool
    command: list[str]
    return_code: int | None = None
    stdout: str = ""
    stderr: str = ""


class ExternalToolRunner:
    """Human-approved wrapper for external security tooling.

    The MVP defaults to dry-run mode. Integrations are intentionally explicit and
    conservative so operators can inspect commands before execution.
    """

    ALLOWED_TOOLS = {"httpx", "nuclei", "katana", "amass", "subfinder", "nmap", "ffuf", "zap-baseline.py", "trufflehog", "semgrep"}

    def build_command(self, tool: str, args: Sequence[str]) -> list[str]:
        if tool not in self.ALLOWED_TOOLS:
            raise ValueError(f"Tool integration not allowlisted: {tool}")
        validate_workflow_name(" ".join([tool, *args]))
        return [tool, *args]

    def run(self, tool: str, args: Sequence[str], approved: bool = False) -> ToolResult:
        command = self.build_command(tool, args)
        available = shutil.which(tool) is not None
        if not approved or not available:
            return ToolResult(tool=tool, available=available, command=command)
        completed = subprocess.run(command, capture_output=True, text=True, timeout=120, check=False)
        return ToolResult(
            tool=tool,
            available=available,
            command=command,
            return_code=completed.returncode,
            stdout=completed.stdout[-10000:],
            stderr=completed.stderr[-5000:],
        )
