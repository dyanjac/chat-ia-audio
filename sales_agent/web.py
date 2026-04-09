from fastapi import FastAPI
from gradio import mount_gradio_app

from sales_agent.ui import build_interface


def create_app() -> FastAPI:
    app = FastAPI(title="TechShop Service")
    demo = build_interface()
    app = mount_gradio_app(app, demo, path="/demo")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
