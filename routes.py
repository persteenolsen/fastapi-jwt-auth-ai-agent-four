import time
import uuid
import traceback
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from auth import verify_token, create_access_token
from models import (
    LoginRequest,
    TokenResponse,
    ChatRequest,
    ChatResponse
)
from config import (
    logger,
    FAKE_USERNAME,
    FAKE_PASSWORD,
    ACCESS_TOKEN_EXPIRE_MINUTES
)

from agent import run_agent, llm
from tools.wikipedia import wikipedia_tool


router = APIRouter()


# ------------------------------
# LOGIN FOR VUE SPA
# ------------------------------
@router.post("/login-spa")
def login(form: OAuth2PasswordRequestForm = Depends()):
    if form.username != FAKE_USERNAME or form.password != FAKE_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = create_access_token(
        {"sub": form.username},
        timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    return {
        "access_token": token, "token_type": "bearer", "username": FAKE_USERNAME
    }


# ------------------------------
# OAUTH2 TOKEN FOR SWAGGER
# ------------------------------
@router.post("/token", response_model=TokenResponse)
def get_token(
    form: OAuth2PasswordRequestForm = Depends()
):

    if (
        form.username != FAKE_USERNAME
        or form.password != FAKE_PASSWORD
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    access_token = create_access_token(
        {"sub": form.username},
        timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    return TokenResponse(
        access_token=access_token
    )


# ------------------------------
# CHAT
# ------------------------------
@router.post("/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    user: str = Depends(verify_token)
):
    start = time.time()

    try:
        logger.info(
            f"User: {user}, Message: {request.message}"
        )

        result = run_agent(request.message)

        logger.info(
            f"Completed in {time.time() - start:.2f}s"
        )

        return ChatResponse(
            response=result.get("response", "")
        )

    except Exception as e:
        error_id = str(uuid.uuid4())

        logger.error(f"Error ID: {error_id}")
        logger.error(traceback.format_exc())

        raise HTTPException(
            status_code=500,
            detail={
                "error_id": error_id,
                "type": type(e).__name__,
                "message": str(e)
            }
        )


# ------------------------------
# HEALTH
# ------------------------------
@router.get("/health")
def health():

    groq_live = False

    try:
        llm.invoke("ping")
        groq_live = True

    except Exception:
        pass

    return {
        "status": "ok",
        "groq": groq_live
    }


# ------------------------------
# TEST GROQ
# ------------------------------
@router.get("/test-groq")
def test_groq():

    try:
        res = llm.invoke("Tell me a joke")

        return {
            "status": "ok",
            "response": getattr(res, "content", str(res))
        }

    except Exception as e:

        return {
            "status": "failed",
            "error": str(e)
        }


# ------------------------------
# TEST WIKIPEDIA
# ------------------------------
@router.get("/test-wikipedia")
def test_wikipedia():

    try:
        result = wikipedia_tool("What is Python?")

        if result.get("success"):
            return {
                "status": "ok",
                "result": result
            }

        return {
            "status": "failed",
            "reason": result.get("content")
        }

    except Exception as e:

        return {
            "status": "failed",
            "error": str(e)
        }
