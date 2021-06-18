import os

AUTO_RELOAD = os.getenv("AUTO_RELOAD", "False").lower() in (
    "true",
    "t",
    "yes",
    "y",
    "1",
)

SENTRY_ENVIRONMENT = os.getenv("SENTRY_ENVIRONMENT", None)
DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "t", "yes", "y", "1")
PORT = int(os.getenv("PORT", "8080"))
WORKERS = int(os.getenv("WORKERS", 4))

PROJECTS_SVC = os.getenv("PROJECTS_HTTP_PORT", "").replace("tcp://", "http://")
