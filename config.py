
import os
import logging
from dotenv import load_dotenv

# -------------------------------------------------
# LOAD ENVIRONMENT VARIABLES
# -------------------------------------------------

load_dotenv()


def get_env(name: str, default: str = "") -> str:
    """Read an environment variable and strip whitespace."""
    return os.getenv(name, default).strip()


# -------------------------------------------------
# DOMAIN C - USER AUTHENTICATION (JWT C)
# -------------------------------------------------

SECRET_KEY = get_env("SECRET_KEY")
FAKE_USERNAME = get_env("FAKE_USERNAME")
FAKE_PASSWORD = get_env("FAKE_PASSWORD")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60


# -------------------------------------------------
# GROQ - LLM
# -------------------------------------------------

GROQ_API_KEY = get_env("GROQ_API_KEY")


# -------------------------------------------------
# DOMAIN B - PRIVATE RAG API
# -------------------------------------------------

DOMAIN_B_BASE_URL = get_env("DOMAIN_B_BASE_URL").rstrip("/") + "/"

DOMAIN_B_LOGIN_PATH = get_env(
    "DOMAIN_B_LOGIN_PATH", "/auth/login"
).lstrip("/")

DOMAIN_B_ASK_PATH = get_env(
    "DOMAIN_B_ASK_PATH", "/ask"
).lstrip("/")

DOMAIN_B_USERNAME = get_env("DOMAIN_B_USERNAME")
DOMAIN_B_PASSWORD = get_env("DOMAIN_B_PASSWORD")


# -------------------------------------------------
# DOMAIN B - JWT CACHE AND HTTP SETTINGS
# -------------------------------------------------

JWT_B_CACHE_SECONDS = int(
    get_env("JWT_B_CACHE_SECONDS", "300")
)

HTTP_TIMEOUT_SECONDS = 10


# -------------------------------------------------
# VALIDATE REQUIRED ENVIRONMENT VARIABLES
# -------------------------------------------------

required_env_vars = [
    "SECRET_KEY",
    "FAKE_USERNAME",
    "FAKE_PASSWORD",
    "GROQ_API_KEY",
    "DOMAIN_B_BASE_URL",
    "DOMAIN_B_USERNAME",
    "DOMAIN_B_PASSWORD",
]

missing_env_vars = [
    name for name in required_env_vars
    if not get_env(name)
]

if missing_env_vars:
    raise RuntimeError(
        "Missing required environment variables: "
        + ", ".join(missing_env_vars)
    )


# -------------------------------------------------
# VALIDATE CONFIGURATION VALUES
# -------------------------------------------------

if len(SECRET_KEY.encode("utf-8")) < 32:
    raise RuntimeError(
        "SECRET_KEY must contain at least 32 bytes."
    )

if JWT_B_CACHE_SECONDS <= 0:
    raise RuntimeError(
        "JWT_B_CACHE_SECONDS must be greater than zero."
    )


# -------------------------------------------------
# LOGGING
# -------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)
