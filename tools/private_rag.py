import logging
import threading
import time
from urllib.parse import urljoin
from typing import Any

import requests

from config import (
    DOMAIN_B_BASE_URL,
    DOMAIN_B_LOGIN_PATH,
    DOMAIN_B_ASK_PATH,
    DOMAIN_B_USERNAME,
    DOMAIN_B_PASSWORD,
    JWT_B_CACHE_SECONDS,
    HTTP_TIMEOUT_SECONDS,
)


logger = logging.getLogger(__name__)

# =================================================
# HTTP CLIENT AND DOMAIN B JWT CACHE
# =================================================

http = requests.Session()

_jwt_b = None
_jwt_b_expires_at = 0.0
_jwt_lock = threading.Lock()

# Retry one time for transient failures.
MAX_RAG_ATTEMPTS = 2


def domain_b_url(path: str) -> str:
    """Build a URL for an endpoint on Domain B."""
    return urljoin(DOMAIN_B_BASE_URL, path.lstrip("/"))


# =================================================
# DOMAIN B LOGIN - OBTAIN JWT B
# =================================================

def login_to_domain_b(force_refresh: bool = False) -> str:
    """Log in to Domain B and cache its JWT."""
    global _jwt_b, _jwt_b_expires_at

    if not DOMAIN_B_USERNAME or not DOMAIN_B_PASSWORD:
        raise RuntimeError(
            "Domain B service credentials are not configured."
        )

    with _jwt_lock:
        if (
            not force_refresh
            and _jwt_b
            and time.monotonic() < _jwt_b_expires_at
        ):
            return _jwt_b

        response = http.post(
            domain_b_url(DOMAIN_B_LOGIN_PATH),
            data={
                "username": DOMAIN_B_USERNAME,
                "password": DOMAIN_B_PASSWORD,
            },
            timeout=HTTP_TIMEOUT_SECONDS,
        )

        response.raise_for_status()
        data = response.json()

        token = data.get("access_token")

        if not token:
            raise RuntimeError(
                "Domain B login did not return access_token."
            )

        _jwt_b = token
        _jwt_b_expires_at = (
            time.monotonic() + JWT_B_CACHE_SECONDS
        )

        logger.info("Successfully authenticated with Domain B.")

        return _jwt_b


# =================================================
# PRIVATE RAG STRUCTURED RESULT
# =================================================

def _error_result(
    answer: str,
    error: str,
) -> dict[str, Any]:
    """Build a consistent structured error result."""
    return {
        "answer": answer,
        "source": [],
        "status": "error",
        "error": error,
    }


def rag_search_structured(query: str) -> dict[str, Any]:
    """
    Query Domain B and return structured RAG data.

    Retries once after transient request failures, timeouts,
    or HTTP 5xx responses.

    HTTP 401 triggers a JWT refresh and one immediate retry.
    """

    logger.info("Private RAG tool called.")

    if not isinstance(query, str) or not query.strip():
        return {
            "answer": "Please provide a question.",
            "source": [],
            "status": "unverified",
            "error": None,
        }

    url = domain_b_url(DOMAIN_B_ASK_PATH)
    last_error = "request_failed"

    for attempt in range(1, MAX_RAG_ATTEMPTS + 1):
        try:
            token = login_to_domain_b()

            # 20-10-2026 - Debbuging
            logger.info("Sending request to Domain B, attempt %s", attempt)

            response = http.post(
                url,
                json={"prompt": query},
                headers={
                    "Authorization": f"Bearer {token}",
                },
                timeout=HTTP_TIMEOUT_SECONDS,
            )

            # Refresh JWT and retry immediately once on 401.
            if response.status_code == 401:
                logger.warning(
                    "Domain B returned 401; refreshing JWT."
                )

                token = login_to_domain_b(force_refresh=True)

                response = http.post(
                    url,
                    json={"prompt": query},
                    headers={
                        "Authorization": f"Bearer {token}",
                    },
                    timeout=HTTP_TIMEOUT_SECONDS,
                )

            # Retry server-side errors if another attempt remains.
            if response.status_code >= 500:
                last_error = "server_error"

                if attempt < MAX_RAG_ATTEMPTS:
                    logger.warning(
                        "Domain B returned HTTP %s; "
                        "retrying attempt %s.",
                        response.status_code,
                        attempt + 1,
                    )
                    continue

                response.raise_for_status()

            response.raise_for_status()

            data = response.json()

            if not isinstance(data, dict):
                raise ValueError(
                    "Domain B returned an unexpected JSON response."
                )

            answer = data.get("answer") or "No answer was returned."
            raw_sources = data.get("sources") or []

            if isinstance(raw_sources, list):
                sources = raw_sources
            elif isinstance(raw_sources, dict):
                sources = [raw_sources]
            else:
                sources = [raw_sources] if raw_sources else []

            return {
                "answer": str(answer),
                "source": sources,
                "status": (
                    "sources_found" if sources else "unverified"
                ),
                "error": None,
            }

        except requests.Timeout:
            last_error = "timeout"

            logger.warning(
                "Domain B request timed out (attempt %s/%s).",
                attempt,
                MAX_RAG_ATTEMPTS,
            )

            if attempt < MAX_RAG_ATTEMPTS:
                continue

            return _error_result(
                (
                    "The request timed out. "
                    "No verified result was obtained from Domain B."
                ),
                last_error,
            )

        except requests.RequestException:
            last_error = "request_failed"

            logger.exception(
                "Domain B HTTP request failed (attempt %s/%s).",
                attempt,
                MAX_RAG_ATTEMPTS,
            )

            if attempt < MAX_RAG_ATTEMPTS:
                continue

            return _error_result(
                (
                    "Domain B is unavailable or the request failed. "
                    "No verified result was obtained."
                ),
                last_error,
            )

        except Exception:
            logger.exception("Private RAG tool failed.")

            return _error_result(
                (
                    "The tool could not complete the request. "
                    "Check the server configuration and logs."
                ),
                "tool_failed",
            )

    return _error_result(
        "Domain B did not return a successful result.",
        last_error,
    )


# =================================================
# PRIVATE RAG LANGCHAIN TOOL
# =================================================

def rag_search(query: str) -> str:
    """
    Preserve the original string-based LangChain tool interface.

    The agent will be updated separately to avoid making an
    unnecessary second successful Domain B request.
    """

    result = rag_search_structured(query)

    answer = result["answer"]
    sources = result["source"]
    status = result["status"]

    if status == "sources_found":
        return (
            "PRIVATE RAG RESULTS\n"
            "Status: Document sources were returned.\n"
            "The answer was generated by Domain B using its "
            "retrieval workflow. Check source relevance before "
            "attributing individual claims to documents.\n\n"
            f"Question: {query}\n"
            f"Answer: {answer}\n"
            f"Sources: {sources}"
        )

    if status == "unverified":
        return (
            "PRIVATE RAG RESULTS\n"
            "Status: NO PRIVATE DOCUMENT SOURCES WERE RETURNED.\n"
            "IMPORTANT: The answer below is NOT verified by "
            "retrieved private documents. Domain B may have "
            "generated it using general LLM knowledge.\n\n"
            f"Question: {query}\n"
            f"Unverified answer: {answer}\n\n"
            "Instructions for the agent: Do not present this answer "
            "as a fact from internal documents. If appropriate, use "
            "Wikipedia to investigate the question independently, "
            "or tell the user that no supporting private sources "
            "were returned."
        )

    if result.get("error") == "timeout":
        return (
            "PRIVATE RAG ERROR: The request timed out. "
            "No verified result was obtained from Domain B."
        )

    if result.get("error") == "server_error":
        return (
            "PRIVATE RAG ERROR: Domain B returned a server error. "
            "No verified result was obtained."
        )

    if result.get("error") == "request_failed":
        return (
            "PRIVATE RAG ERROR: Domain B is unavailable or the "
            "request failed. No verified result was obtained."
        )

    return (
        "PRIVATE RAG ERROR: The tool could not complete the "
        "request. Check the server configuration and logs."
    )
