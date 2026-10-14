"""Versioned prompts stored as YAML files under prompts/<id>/v<N>.yaml.

Every answer and every trace records the prompt id, version and a SHA-256 of
its content, so a change of wording is visible in the audit log and in the
evaluation history. A prompt file is never edited in place once released:
a change means a new version, which must pass the evaluation gate.
"""
from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from . import config


@dataclass(frozen=True)
class Prompt:
    id: str
    version: int
    system: str
    user_template: str
    sha256: str

    @property
    def ref(self) -> str:
        return f"{self.id}@v{self.version}"

    def render(self, **kwargs) -> str:
        return self.user_template.format(**kwargs)


def versions(prompt_id: str, root: Path = config.PROMPTS) -> list[int]:
    out = []
    for f in (root / prompt_id).glob("v*.yaml"):
        if m := re.fullmatch(r"v(\d+)\.yaml", f.name):
            out.append(int(m.group(1)))
    return sorted(out)


def load(prompt_id: str, version: int | str | None = None, root: Path = config.PROMPTS) -> Prompt:
    env = os.environ.get(f"CCP_PROMPT_{prompt_id.upper()}_VERSION")
    version = version or env or "latest"
    if version == "latest":
        available = versions(prompt_id, root)
        if not available:
            raise FileNotFoundError(f"no prompt versions for {prompt_id!r}")
        version = available[-1]
    path = root / prompt_id / f"v{int(version)}.yaml"
    raw = path.read_bytes()
    data = yaml.safe_load(raw)
    if data["id"] != prompt_id or int(data["version"]) != int(version):
        raise ValueError(f"{path} declares {data['id']}@v{data['version']}")
    return Prompt(prompt_id, int(version), data["system"], data["user_template"], hashlib.sha256(raw).hexdigest()[:12])
