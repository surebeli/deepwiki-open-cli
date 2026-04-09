import typer

from deepwiki import __version__
from deepwiki.cli.ask import register_ask
from deepwiki.cli.config_cmd import register_config
from deepwiki.cli.export import register_export
from deepwiki.cli.generate import register_generate
from deepwiki.cli.repl import register_repl
from deepwiki.cli.research import register_research
from deepwiki.cli.serve import register_serve

app = typer.Typer(help="DeepWiki CLI", no_args_is_help=True)
register_generate(app)
register_ask(app)
register_config(app)
register_export(app)
register_research(app)
register_repl(app)
register_serve(app)


@app.command("version")
def version() -> None:
    typer.echo(__version__)


def main() -> None:
    app()
