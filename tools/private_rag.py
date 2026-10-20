
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


def domain_b_url(path: str) -> str:
    """Build a URL for an endpoint on Domain B."""
    return urljoin(DOMAIN_B_BASE_URL, path.lstrip("/"))


# =================================================
# DOMAIN B LOGIN - OBTAIN JWT B
# =================================================

def login_to_domain_b(force_refresh: bool = False) -> str:
    """
    Log in to Domain B using form-encoded credentials.
    Cache the JWT on the server.
    """
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

def rag_search_structured(query: str) -> dict[str, Any]:
    """
    Return structured RAG data for the agent/backend.

    NEW: source and status are returned as separate fields.
    The existing rag_search() below still converts this to text
    for LangChain, preserving the existing tool interface.
    """
    logger.warning("========== PRIVATE RAG TOOL CALLED ==========")
    logger.warning("RAG QUERY: %s", query)

    try:
        token = login_to_domain_b()

        url = domain_b_url(DOMAIN_B_ASK_PATH)

        response = http.post(
            url,
            json={"prompt": query},
            headers={
                "Authorization": f"Bearer {token}",
            },
            timeout=HTTP_TIMEOUT_SECONDS,
        )

        # Refresh JWT and retry once if unauthorized.
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

        logger.info(
            "Private RAG HTTP status: %s",
            response.status_code,
        )

        response.raise_for_status()

        data = response.json()

        if not isinstance(data, dict):
            raise ValueError(
                "Domain B returned an unexpected JSON response."
            )

        logger.info(
            "Private RAG response keys: %s",
            list(data.keys()),
        )

        answer = data.get("answer") or "No answer was returned."

        # NEW: normalize source data for the API response.
        raw_sources = data.get("sources") or []

        if isinstance(raw_sources, list):
            sources = raw_sources
        elif isinstance(raw_sources, dict):
            sources = [raw_sources]
        else:
            sources = [raw_sources] if raw_sources else []

        # NEW: distinguish source availability from answer correctness.
        if sources:
            return {
                "answer": answer,
                "source": sources,
                "status": "sources_found",
                "error": None,
            }

        return {
            "answer": answer,
            "source": [],
            "status": "unverified",
            "error": None,
        }

    except requests.Timeout:
        logger.warning("Domain B RAG request timed out.")

        # NEW: structured error status.
        return {
            "answer": (
                "The request timed out. "
                "No verified result was obtained from Domain B."
            ),
            "source": [],
            "status": "error",
            "error": "timeout",
        }

    except requests.RequestException:
        logger.exception("Domain B RAG HTTP request failed.")

        # NEW: structured error status.
        return {
            "answer": (
                "Domain B is unavailable or the request failed. "
                "No verified result was obtained."
            ),
            "source": [],
            "status": "error",
            "error": "request_failed",
        }

    except Exception:
        logger.exception("Domain B RAG tool failed.")

        # NEW: structured error status.
        return {
            "answer": (
                "The tool could not complete the request. "
                "Check the server configuration and logs."
            ),
            "source": [],
            "status": "error",
            "error": "tool_failed",
        }


# =================================================
# PRIVATE RAG LANGCHAIN TOOL
# =================================================

def rag_search(query: str) -> str:
    """
    Preserve the existing string-based LangChain tool interface.

    NEW: build the existing human-readable tool output from the
    structured result returned by rag_search_structured().
    """
    result = rag_search_structured(query)

    answer = result["answer"]
    sources = result["source"]
    status = result["status"]

    # Keep existing output style for document-backed answers.
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

    # Keep existing output style for answers without sources.
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

    # Preserve the existing error wording for the LLM.
    if result.get("error") == "timeout":
        return (
            "PRIVATE RAG ERROR: The request timed out. "
            "No verified result was obtained from Domain B."
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
