from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from gradio import mount_gradio_app
from starlette.staticfiles import StaticFiles

from sales_agent.api import public_router, router as api_router
from sales_agent.ui import build_interface


def create_app() -> FastAPI:
    base_dir = Path(__file__).resolve().parent
    static_dir = base_dir / "static"

    app = FastAPI(title="TechShop Service")
    app.include_router(api_router)
    app.include_router(public_router)
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    demo = build_interface()
    app = mount_gradio_app(app, demo, path="/demo")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/chat", include_in_schema=False)
    def chat() -> FileResponse:
        return FileResponse(static_dir / "chat.html")

    return app


app = create_app()
