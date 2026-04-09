from __future__ import annotations

import typer
import uvicorn

from deepwiki.server.api import create_app


def register_serve(app: typer.Typer) -> None:
    @app.command("serve")
    def serve(
        host: str = typer.Option("0.0.0.0", "--host", help="Bind host"),
        port: int = typer.Option(8001, "--port", help="Bind port"),
        reload: bool = typer.Option(False, "--reload", help="Enable auto reload"),
        cors_origins: str = typer.Option("", "--cors-origins", help="Comma-separated CORS origins"),
    ) -> None:
        origins = [item.strip() for item in cors_origins.split(",") if item.strip()]
        api = create_app(cors_origins=origins)
        uvicorn.run(api, host=host, port=port, reload=reload)
