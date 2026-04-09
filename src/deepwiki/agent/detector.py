from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class AgentContext:
    agent_name: str
    provider: str | None
    model: str | None
    api_key: str | None
    api_base: str | None
    passthrough_available: bool
    env_vars: dict[str, str]


class AgentDetector:
    @staticmethod
    def _build_generic_context() -> AgentContext:
        provider = os.getenv("DEEPWIKI_AGENT_PROVIDER")
        model = os.getenv("DEEPWIKI_AGENT_MODEL")
        api_key = os.getenv("DEEPWIKI_AGENT_API_KEY")
        api_base = os.getenv("DEEPWIKI_AGENT_API_BASE")
        name = os.getenv("DEEPWIKI_AGENT_NAME", "generic")
        passthrough = provider is not None and model is not None

        env_vars = {
            key: value
            for key, value in {
                "DEEPWIKI_AGENT_NAME": os.getenv("DEEPWIKI_AGENT_NAME"),
                "DEEPWIKI_AGENT_PROVIDER": provider,
                "DEEPWIKI_AGENT_MODEL": model,
                "DEEPWIKI_AGENT_API_KEY": api_key,
                "DEEPWIKI_AGENT_API_BASE": api_base,
            }.items()
            if value is not None
        }

        return AgentContext(
            agent_name=name,
            provider=provider,
            model=model,
            api_key=api_key,
            api_base=api_base,
            passthrough_available=passthrough,
            env_vars=env_vars,
        )

    @staticmethod
    def detect() -> AgentContext | None:
        if os.getenv("DEEPWIKI_AGENT_NAME"):
            return AgentDetector._build_generic_context()

        if os.getenv("CLAUDE_CODE") == "1":
            return AgentContext(
                agent_name="claude-code",
                provider="anthropic",
                model=os.getenv("ANTHROPIC_MODEL") or os.getenv("DEEPWIKI_MODEL"),
                api_key=os.getenv("ANTHROPIC_API_KEY"),
                api_base=os.getenv("ANTHROPIC_BASE_URL"),
                passthrough_available=os.getenv("ANTHROPIC_API_KEY") is not None,
                env_vars={"CLAUDE_CODE": "1"},
            )

        if os.getenv("CURSOR_SESSION"):
            return AgentContext(
                agent_name="cursor",
                provider=None,
                model=None,
                api_key=None,
                api_base=None,
                passthrough_available=False,
                env_vars={"CURSOR_SESSION": os.getenv("CURSOR_SESSION", "")},
            )

        if os.getenv("GITHUB_COPILOT"):
            return AgentContext(
                agent_name="github-copilot",
                provider=None,
                model=None,
                api_key=None,
                api_base=None,
                passthrough_available=False,
                env_vars={"GITHUB_COPILOT": os.getenv("GITHUB_COPILOT", "")},
            )

        if os.getenv("AIDER_MODEL"):
            return AgentContext(
                agent_name="aider",
                provider=None,
                model=os.getenv("AIDER_MODEL"),
                api_key=None,
                api_base=None,
                passthrough_available=False,
                env_vars={"AIDER_MODEL": os.getenv("AIDER_MODEL", "")},
            )

        return None
