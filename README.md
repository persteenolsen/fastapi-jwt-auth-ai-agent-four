# 🚀 FastAPI Agentic RAG with JWT Authentication

A full-stack AI application built with **FastAPI, Vue 3, Pinia, LangChain, Groq, and JWT authentication**.

The application combines an authenticated chat interface with a LangChain tool-calling agent that accesses two knowledge sources:

- **Private RAG:** A protected retrieval service hosted on Domain B.
- **Wikipedia:** A public knowledge source for supplementary information.

Domain A authenticates with Domain B, submits questions to its protected RAG endpoint, and receives generated answers and document source references.

The architecture separates agent orchestration, private RAG communication, and public knowledge retrieval into independent modules for maintainability, security, and extensibility.

## 🌐 Companion Vue Frontend

**Repository:** [vue-fastapi-jwt-auth-ai-agent-four](https://github.com/persteenolsen/vue-fastapi-jwt-auth-ai-agent-four)

> Replace the placeholder GitHub URL with the actual frontend repository URL.

## 📌 Project Information

| Property | Value |
|---|---|
| Version | 0.0.4 |
| Last Updated | 2026-10-20 |
| Python | 3.12 |
| Backend | FastAPI |
| Frontend | Vue 3 |
| State Management | Pinia |
| Authentication | JWT |
| LLM Provider | Groq |
| Model | `openai/gpt-oss-20b` |
| Agent Framework | LangChain |
| Private Knowledge Storage | PostgreSQL on Neon, managed by Domain B |

## ✨ Features

### 🔐 Authentication and Security

- JWT-protected API endpoints.
- SPA login and OAuth2-compatible authentication.
- Bearer token authorization.
- Environment-based configuration.
- Separate service-to-service authentication between Domain A and Domain B.
- In-memory caching of the Domain B access token.
- JWT refresh and retry after an HTTP `401 Unauthorized` response.
- Separation of frontend authentication credentials from backend service credentials.

#### Authentication Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/login-spa` | Vue SPA login |
| `POST` | `/token` | OAuth2-compatible login for Swagger UI |

**Security notice:** Keep API keys, passwords, JWT secrets, and service credentials in environment variables. Never commit secrets to GitHub.

### 🤖 LangChain Tool-Calling Agent

The agent uses Groq for inference and has access to two tools:

- **Private_RAG** — Retrieves private knowledge from Domain B.
- **Wikipedia** — Retrieves public information using Wikipedia's REST summary API and search API. The tool attempts a direct article lookup first, falls back to a search limited to five candidates, and ranks retrieved summaries using lightweight keyword matching that prioritizes article-title matches.

The system prompt instructs the agent to call `Private_RAG` before answering, inspect its result, and use Wikipedia when additional public information is useful.

The agent can:

- Retrieve information from private documents.
- Supplement private results with public information.
- Distinguish retrieved private evidence from general knowledge.
- Identify answers that lack private document sources.
- Return tool calls, inputs, observations, and the final answer.

### 🧠 Groq LLM

| Setting | Value |
|---|---|
| Model | `openai/gpt-oss-20b` |
| Temperature | `0` |
| Streaming | Disabled |
| API Key | Environment variable |

LangChain manages tool invocation, observations, and final response generation.

### 🌐 Wikipedia Public Knowledge Tool

Implemented in `tools/wikipedia.py`, this tool provides supplementary public information to the LangChain agent.

Responsibilities include:

- Direct Wikipedia article-summary lookup.
- Search fallback when direct lookup fails.
- Search limited to five candidate article titles.
- Lightweight keyword-based ranking that gives greater weight to article-title matches.
- HTTP request timeouts of seven seconds per request.
- Structured success and failure responses.
- Error logging and graceful handling of failed requests.

The tool returns an article title and summary when a page is retrieved. Its current keyword-based ranking is lightweight and does not guarantee semantic relevance. Wikipedia results supplement public knowledge; they do not verify private organizational facts.

The seven-second timeout applies to each individual HTTP request, not the total duration of a complete Wikipedia lookup.

### 📚 Private RAG — Domain B

Implemented in `tools/private_rag.py`, this module handles communication with the protected RAG API.

Responsibilities include:

- HTTP session management.
- Domain B authentication and JWT caching.
- Authenticated requests to the RAG endpoint.
- Token refresh after HTTP `401` responses.
- Configurable request timeouts.
- Retries for selected transient failures and server errors.
- Structured answers and source references.
- Verification status and error handling.

#### Example Request

```json
{
  "prompt": "What does our internal documentation say about Spring Boot?"
}
```

### 🔄 Request Workflow

```text
Vue 3 Frontend
      |
      v
Domain A - FastAPI
      |
      v
Authenticate User
      |
      v
Fetch Structured Private RAG Result
      |
      v
Request-Scoped Agent
      |
      v
    Groq LLM
      |
      +-------------------+
      |                   |
      v                   v
  Private_RAG          Wikipedia
  (captured result)    (public retrieval)
      |                   |
      v                   v
    Domain B           Public Sources
      |                   |
      +---------+---------+
                |
                v
       Final Agent Response
                |
                v
          Vue Frontend
```

The diagram shows the available components, not a guaranteed execution sequence. The system prompt requires a private RAG lookup before answering, while additional Wikipedia calls depend on agent execution.

#### Request-Scoped RAG Result

The backend fetches the structured private RAG result once per chat request. `create_request_agent()` then creates a tool that closes over that result.

This design:

- Avoids a second successful Domain B request when the agent invokes `Private_RAG`.
- Prevents concurrent requests from overwriting one another's captured RAG results.
- Keeps retrieval handling separate from agent orchestration.

The underlying RAG module retries eligible failures according to its configured policy.

## 📡 Domain A API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/login-spa` | Vue SPA login. |
| `POST` | `/token` | Swagger authentication. |
| `POST` | `/chat` | Submit a question to the agent. |
| `GET` | `/health` | Health check. |
| `GET` | `/test-groq` | Test Groq connectivity. |
| `GET` | `/test-wikipedia` | Test Wikipedia retrieval. |

These endpoints reflect the existing application. The private RAG endpoint is hosted on Domain B and is called internally by Domain A.

## 📦 Chat Response Format

The `/chat` endpoint returns a structured response for the frontend.

### Example Response

```json
{
  "response": {
    "action": "Private_RAG",
    "action_input": "Spring Boot",
    "observation": [
      {
        "tool": "Private_RAG",
        "tool_input": "Spring Boot",
        "observation": "PRIVATE RAG RESULTS..."
      }
    ],
    "final_answer": "The generated answer.",
    "tools_used": [
      "Private_RAG"
    ],
    "source": [
      "https://example.com/document.txt"
    ],
    "status": "sources_found"
  }
}
```

This is an illustrative example. Actual tool calls, observations, sources, and answers depend on execution.

### Response Fields

| Field | Description |
|---|---|
| `action` | Comma-separated tool names, or `"None"`. |
| `action_input` | Input associated with the last executed tool. |
| `observation` | Tool calls, inputs, and returned observations. |
| `final_answer` | Final answer generated by the agent. |
| `tools_used` | Ordered list of distinct tools. |
| `source` | Private RAG source references. |
| `status` | Private evidence or execution status. |

The status values are `sources_found`, `unverified`, `error`, or `unknown`.

The backend returns a structured error response if agent execution fails, rather than exposing the full exception to the user.

## ⚙️ Getting Started

### Prerequisites

Before running the application, ensure you have:

- Python 3.12.
- A Groq API key.
- Access to Domain A configuration.
- A running Domain B RAG service.
- Domain B service credentials.
- The companion Vue frontend, if using the SPA.

### 1. Clone the Repository

Replace the placeholder URL with your actual backend repository URL.

```bash
git clone https://github.com/your-username/your-repository.git
cd your-repository
```

Navigate to the backend directory if necessary.

### 2. Create a Virtual Environment

**Windows:**

```powershell
python -m venv venv
venv\Scripts\activate
```

**Linux/macOS:**

```bash
python -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

Install the project dependencies:

```bash
pip install -r requirements.txt
```

Ensure `requirements.txt` includes FastAPI, Uvicorn, Requests, LangChain, the LangChain Groq integration, and the dependencies used by your Wikipedia implementation.

### 4. Configure Environment Variables

Create a `.env` file in the location expected by your existing configuration.

Example configuration:

```dotenv
SECRET_KEY=replace_with_a_secure_random_secret
GROQ_API_KEY=your_groq_api_key

FAKE_USERNAME=admin
FAKE_PASSWORD=replace_with_a_secure_password

DOMAIN_B_BASE_URL=https://your-domain-b.example.com
DOMAIN_B_LOGIN_PATH=your-login-path
DOMAIN_B_ASK_PATH=ask
DOMAIN_B_USERNAME=your_domain_b_service_username
DOMAIN_B_PASSWORD=your_domain_b_service_password

JWT_B_CACHE_SECONDS=300
HTTP_TIMEOUT_SECONDS=20
```

These values are examples. Use the actual environment variable names and endpoint paths defined in `config.py` and the Domain B implementation.

Generate a random JWT signing secret if required:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

**Important security practices:**

- Ensure `.env` is listed in `.gitignore`.
- Never commit real credentials, API keys, passwords, or JWT secrets.
- Keep Domain B service credentials exclusively on the backend.
- Use HTTPS for deployed services.
- Replace demo authentication settings with a production-grade identity solution before public deployment.

### 5. Start the Backend

From the directory containing `main.py`, run:

```bash
uvicorn main:app --reload
```

The backend will be available at the following local URLs:

| Service | URL |
|---|---|
| API | http://127.0.0.1:8000 |
| Swagger UI | http://127.0.0.1:8000/docs |

The `--reload` option is intended for local development, not production deployment.

### 6. Start the Frontend

Clone or open the companion Vue application:

**Repository:** `vue-fastapi-jwt-auth-ai-agent-four`

Follow its README for installation, environment configuration, and startup instructions.

Ensure the frontend API configuration points to the correct Domain A backend URL.

## 🔐 Authentication Flow

### User Authentication

1. The user logs in through `/login-spa` or `/token`.
2. Domain A issues the frontend authentication token.
3. The frontend sends authenticated requests using a bearer token:

   ```http
   Authorization: Bearer <USER_ACCESS_TOKEN>
   ```

4. The protected `/chat` endpoint processes the request.

### Domain A to Domain B

1. Domain A authenticates using configured service credentials.
2. Domain B returns an access token.
3. Domain A caches the token in memory.
4. Domain A calls the protected RAG endpoint using a bearer token.
5. If the request receives HTTP `401 Unauthorized`, Domain A refreshes the JWT and retries the request once.

The frontend JWT and the Domain A-to-Domain B service JWT are separate credentials with different purposes.

## 🧪 Testing

The following scenarios can be used to validate the agent's behavior and integration.

### 1. Private Knowledge

**Question:**

> What does our internal document say about Spring Boot?

**Expected behavior:**

- The private RAG service is queried.
- Domain B returns an answer and any available source references.
- The agent inspects the private RAG result.
- The final response reflects the available evidence.

### 2. Public Knowledge

**Question:**

> What is the capital of Japan?

**Expected behavior:**

- Private RAG is queried first under the current prompt.
- Wikipedia can be used to supplement the result.
- The agent distinguishes public knowledge from private evidence when relevant.

### 3. Combined Knowledge

**Question:**

> Compare our internal Spring Boot implementation with public best practices.

**Expected behavior:**

- Private RAG supplies the available internal evidence.
- Wikipedia can provide supplementary public information.
- The final answer distinguishes the two knowledge sources.

### 4. Missing Private Sources

Ask a question unlikely to match the private documents.

**Expected behavior:**

- Domain B may return an answer without document sources.
- The result is marked `unverified`.
- The agent is instructed not to present the answer as verified private knowledge.

### 5. Error Handling

Test unavailable Domain B endpoints, timeouts, invalid credentials, and server errors in a controlled environment.

**Expected behavior:**

- The RAG module applies its configured retry and token-refresh behavior.
- Failed lookups return structured error information.
- Agent failures return a safe error response.

## 🖥️ Vue Frontend

The companion Vue 3 application provides:

- JWT authentication.
- Pinia state management.
- An AI chat interface.
- API integration.
- Final answer display.
- Tool names, inputs, and observations.
- Visibility into agent execution.

**Companion repository:** `vue-fastapi-jwt-auth-ai-agent-four`

Domain B service credentials and tokens must remain on the backend and must never be exposed to the browser.

## 🎯 Use Cases

This project is suitable for applications that combine private organizational knowledge with public information through an authenticated AI chat interface.

- **Internal Knowledge Assistants:** Answer employee questions using private documentation, technical guides, and organizational knowledge.
- **Technical Documentation Search:** Retrieve information from internal API documentation, architecture decisions, and development guidelines.
- **Private and Public Knowledge Comparison:** Compare internal implementations and policies with publicly available information.
- **AI-Powered Customer Support:** Build authenticated support assistants that retrieve approved knowledge base content and supplement it with public resources.
- **Enterprise RAG Applications:** Integrate protected retrieval services with LLM-powered agents while keeping service credentials on the backend.
- **AI Agent Prototyping:** Explore LangChain tool calling, JWT authentication, source-aware responses, and multi-service application architecture.

**Note:** Private knowledge access depends on the configured Domain B RAG service, available documents, and authentication permissions. Retrieved source references do not automatically guarantee that every generated claim is supported by the underlying documents.

## ⚠️ Current Limitations

- The agent relies on the LLM and system prompt for additional tool selection.
- Private RAG is queried before every answer, including greetings.
- Answers without private document sources are not verified against retrieved documents.
- Source references do not automatically establish that every answer claim is supported.
- Wikipedia sources are not automatically included in the private source field.
- Conversation memory is not implemented in the shown agent.
- Streaming is disabled.
- The JWT cache is process-local and is not shared between worker processes.
- Agent execution is limited to four iterations and a 25-second execution-time limit.
- Demo authentication settings may require hardening before production deployment.
- Wikipedia relevance ranking uses keyword matching rather than semantic search, so an ambiguous query may still return a less relevant article.
- Wikipedia's seven-second HTTP timeouts apply per request; a lookup involving multiple requests can take longer overall.

## 🚀 Future Improvements

Potential improvements include:

- Conditional routing to avoid unnecessary retrieval.
- Improved document ranking and retrieval evaluation.
- More detailed citations and document metadata.
- Automated tests for authentication, retries, and tool execution.
- Structured logging, latency monitoring, and health checks.
- Conversation memory where required.
- Production-grade identity management, secrets handling, and rate limiting.
- Automated deployment and regression testing.

These improvements are optional and can be introduced incrementally without redesigning the current architecture.

## 💡 Design Philosophy

The project prioritizes a working, maintainable architecture through the following principles:

- **Separation of concerns:** Agent orchestration and RAG communication remain independent.
- **Native tool calling:** LangChain manages tool execution and observations.
- **Source awareness:** Private answers without retrieved sources are marked unverified.
- **Request isolation:** Each chat request receives its own agent and captured RAG result.
- **Observability:** Intermediate steps help developers inspect execution.
- **Security:** Service credentials remain on the backend.
- **Incremental development:** Changes build on a tested baseline.

## 📄 License

This project is intended to be distributed under the **MIT License**.

Include the complete MIT license text in a `LICENSE` file at the repository root before distributing the project.