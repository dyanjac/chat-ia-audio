import logging

import uvicorn

from sales_agent.config import settings
from sales_agent.web import app


logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)


if __name__ == "__main__":
    uvicorn.run(app, host=settings.gradio_host, port=settings.gradio_port)
