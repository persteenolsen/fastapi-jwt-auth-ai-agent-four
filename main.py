from fastapi import FastAPI
from routes import router
from config import logger

# 22-07-2026 - For allowing a Vue frontend in another domain
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
   title="FastAPI with JWT Authentication Serving an Agentic RAG System Using LangChain",
    description=(
        "19-10-2026 - FastAPI backend with JWT authentication serving a LangChain-based "
        "agentic RAG system powered by Groq. The LLM dynamically selects "
        "between RAG-based knowledge retrieval and Wikipedia searches "
        "to generate context-aware responses"
    ),
    version="0.0.3", 
    contact={
        "name": "Per Olsen",
        "url": "https://persteenolsen.netlify.app",
    },
)


# 22-07-2026 - For allowing a Vue frontend in another domain
# Set up CORS middleware
origins = [

    # Not sure if this is needed, but adding just in case
    "https://fastapi-jwt-auth-ai-agent-four.vercel.app",

    # The domain name of the Vue 3 SPA Client
    "https://vue.fastapi.jwt.auth.ai.agent.four.persteenolsen.com",
     
    # Allow my local Vue SPA
    "http://localhost:3000"
    
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    # allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



# Include API routes
app.include_router(router)