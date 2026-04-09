from deepwiki.core.models import WikiPage, WikiResult
from deepwiki.core.prompts import PAGE_PROMPT_TEMPLATE
from deepwiki.providers.base import BaseLLMProvider, CompletionRequest


class WikiGenerator:
    def __init__(self, provider: BaseLLMProvider, provider_name: str, model_name: str):
        self.provider = provider
        self.provider_name = provider_name
        self.model_name = model_name

    async def generate(self, repo_name: str, files: list[tuple[str, str]]) -> WikiResult:
        summary_lines = [f"- {path}" for path, _ in files]
        files_summary = "\n".join(summary_lines) if summary_lines else "(no readable files)"
        prompt = PAGE_PROMPT_TEMPLATE.format(title="Repository Overview", files_summary=files_summary)
        response = await self.provider.complete(
            CompletionRequest(
                prompt=prompt,
                model=self.model_name,
                provider=self.provider_name,
                stream=False,
            )
        )
        page = WikiPage(title="Repository Overview", content=response.content)
        return WikiResult(title=f"Wiki for {repo_name}", pages=[page])
