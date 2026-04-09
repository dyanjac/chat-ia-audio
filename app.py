import logging

from sales_agent.config import settings
from sales_agent.ui import build_interface


logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)


if __name__ == "__main__":
    app = build_interface()
    app.launch(server_name=settings.gradio_host, server_port=settings.gradio_port)
