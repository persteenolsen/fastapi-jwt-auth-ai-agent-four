
import logging
from typing import Any

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.tools import Tool
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq

from config import GROQ_API_KEY
from tools.wikipedia import wikipedia_tool
from tools.private_rag import rag_search


logger = logging.getLogger(__name__)


# =================================================
# TOOL 1: WIKIPEDIA
# =================================================

def wikipedia_search(query: str) -> str:
    """Search Wikipedia for public knowledge."""
    try:
        result = wikipedia_tool(query)

        if isinstance(result, dict):
            return str(
                result.get("content")
                or "No Wikipedia result found."
            )

        return str(result)

    except Exception:
        logger.exception("Wikipedia tool failed")
        return "Wikipedia search failed. Please try again."


# =================================================
# REGISTER AGENT TOOLS
# =================================================

tools = [
    Tool(
        name="Wikipedia",
        func=wikipedia_search,
        description=(
            "Search public Wikipedia knowledge about people, places, "
            "history, science, technology, and general facts. "
            "Use this tool when the question needs public information."
        ),
    ),
    Tool(
        name="Private_RAG",
        func=rag_search,
        description=(
            "Search the private knowledge base on Domain B, backed by "
            "PostgreSQL on Neon. Use for internal documents, uploaded "
            "files, private organizational information, or questions "
            "about the user's stored knowledge. Returns an answer "
            "and source references. Use alongside Wikipedia when "
            "a question requires both public and private knowledge."
        ),
    ),
]


# =================================================
# GROQ LLM
# =================================================

llm = ChatGroq(
    model="openai/gpt-oss-20b",
    temperature=0,
    api_key=GROQ_API_KEY,
)


# =================================================
# AGENT PROMPT
# =================================================

prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        """
You are an agentic RAG assistant with two tools:

1. Wikipedia: public information.
2. Private_RAG: private knowledge retrieved from Domain B.

TOOL SELECTION:
- ALWAYS call Private_RAG before answering any user question.
- Do not provide a final answer until Private_RAG has been called.
- Inspect the result returned by Private_RAG before answering.
- Use Wikipedia when additional public information is useful.
- If both private and public information are needed, use both tools.
- Do not invent internal documents, sources, or citations.

PRIVATE RAG SOURCE RULES:
- If document sources are returned, use them as evidence when relevant.
- Do not assume every claim in the RAG answer is supported by its sources.
- If Private_RAG reports that NO PRIVATE DOCUMENT SOURCES
  WERE RETURNED, explicitly state that no supporting private
  document sources were found.
- Do not present an answer without sources as verified private knowledge.
- You may use Wikipedia to investigate public facts independently.
- Public information does not verify private organizational facts.
- Preserve relevant source references returned by Private_RAG.

ERROR HANDLING:
- If Private_RAG fails, clearly explain that the private knowledge
  base could not be accessed or queried successfully.
- Never claim that a tool succeeded when it failed.
- Use Wikipedia if it can independently provide useful public
  information, but do not treat it as a replacement for private evidence.
- Never invent tool results or sources.

FINAL ANSWERS:
- Clearly distinguish private document evidence from public knowledge.
- Explain when no private document sources were returned.
- Be accurate, concise, and useful.
- Never fabricate facts, documents, or citations.
        """.strip(),
    ),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}"),
])


# =================================================
# CREATE AGENT
# =================================================

agent = create_tool_calling_agent(
    llm=llm,
    tools=tools,
    prompt=prompt,
)


# =================================================
# AGENT EXECUTOR
# =================================================

agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    verbose=True,
    return_intermediate_steps=True,
    max_iterations=4,
    max_execution_time=25,
    handle_parsing_errors=True,
)


# =================================================
# RUN AGENT
# =================================================

def run_agent(query: str) -> dict[str, Any]:
    """Run the agent and return its answer and tool information."""

    if not isinstance(query, str) or not query.strip():
        return {
            "response": {
                "action": "None",
                "action_input": "",
                "observation": [],
                "final_answer": "Please enter a question.",
                "tools_used": [],
            }
        }

    try:
        result = agent_executor.invoke({
            "input": query.strip()
        })

        steps = result.get("intermediate_steps", [])

        observations = []
        tools_used = []
        last_action_input = ""

        for action, observation in steps:
            tool_name = getattr(action, "tool", "None")
            tool_input = getattr(action, "tool_input", "")

            if tool_name != "None":
                tools_used.append(tool_name)

            last_action_input = tool_input

            observations.append({
                "tool": tool_name,
                "tool_input": tool_input,
                "observation": str(observation),
            })

        # Preserve order and remove duplicate names.
        tools_used = list(dict.fromkeys(tools_used))

        return {
            "response": {
                "action": (
                    ", ".join(tools_used)
                    if tools_used
                    else "None"
                ),
                "action_input": last_action_input,
                "observation": observations,
                "final_answer": result.get("output", ""),
                "tools_used": tools_used,
            }
        }

    except Exception:
        logger.exception("Agent execution failed")

        return {
            "response": {
                "action": "None",
                "action_input": "",
                "observation": [
                    {
                        "tool": "Agent",
                        "observation": "Agent execution failed.",
                    }
                ],
                "final_answer": (
                    "Sorry, the agent could not complete your "
                    "request. Please try again."
                ),
                "tools_used": [],
            }
        }
