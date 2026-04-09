from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from deepwiki.core.models import WikiResult


class TerminalFormatter:
    def __init__(self) -> None:
        self.console = Console()

    def render(self, result: WikiResult) -> None:
        self.console.print(Panel(result.title, title="deepwiki"))
        for page in result.pages:
            self.console.print(Panel(Markdown(page.content), title=page.title))
