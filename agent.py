
import ast
import logging
import re
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
# NEW: EXTRACT PRIVATE RAG METADATA
# =================================================

def extract_rag_metadata(observation: str) -> dict[str, Any]:
    """
    Extract source and status from the existing Private RAG
    string observation. The observation itself remains unchanged.
    """
    text = str(observation or "")

    metadata = {
        "source": [],
        "status": "unknown",
    }

    if "PRIVATE RAG ERROR:" in text:
        metadata["status"] = "error"
        return metadata

    if "Status: Document sources were returned." in text:
        metadata["status"] = "sources_found"

        match = re.search(
            r"(?m)^Sources:\s*(.+)$",
            text,
        )

        if match:
            raw_sources = match.group(1).strip()

            try:
                parsed = ast.literal_eval(raw_sources)

                if isinstance(parsed, list):
                    metadata["source"] = parsed
                elif isinstance(parsed, dict):
                    metadata["source"] = [parsed]
                elif isinstance(parsed, str):
                    metadata["source"] = [parsed]

            except (ValueError, SyntaxError):
                # Keep unparseable source references instead of losing them.
                metadata["source"] = [raw_sources]

        return metadata

    if "NO PRIVATE DOCUMENT SOURCES WERE RETURNED" in text:
        metadata["status"] = "unverified"
        return metadata

    return metadata


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
# Unchanged
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
    """Run the agent and return its answer, sources, and status."""

    if not isinstance(query, str) or not query.strip():
        return {
            "response": {
                "action": "None",
                "action_input": "",
                "observation": [],
                "final_answer": "Please enter a question.",
                "tools_used": [],
                "source": [],
                "status": "unknown",
            }
        }

    try:
        result = agent_executor.invoke({
            "input": query.strip()
        })

        steps = result.get("intermediate_steps", [])

        observations = []
        tools_used = []
        sources = []
        rag_statuses = []
        last_action_input = ""

        for action, observation in steps:
            tool_name = getattr(action, "tool", "None")
            tool_input = getattr(action, "tool_input", "")

            if tool_name != "None":
                tools_used.append(tool_name)

            last_action_input = tool_input

            # Preserve the original observation for existing consumers.
            observation_text = str(observation)

            observations.append({
                "tool": tool_name,
                "tool_input": tool_input,
                "observation": observation_text,
            })

            # NEW: extract metadata from Private RAG observations.
            if tool_name == "Private_RAG":
                metadata = extract_rag_metadata(observation_text)

                rag_statuses.append(metadata["status"])
                sources.extend(metadata["source"])

        # Preserve tool order and remove duplicate names.
        tools_used = list(dict.fromkeys(tools_used))

        # NEW: remove duplicate source entries.
        unique_sources = []
        seen_sources = set()

        for source in sources:
            source_key = repr(source)

            if source_key not in seen_sources:
                seen_sources.add(source_key)
                unique_sources.append(source)

        # NEW: derive status from Private RAG results, not LLM wording.
        if "error" in rag_statuses:
            status = "error"
        elif "unverified" in rag_statuses:
            status = "unverified"
        elif "sources_found" in rag_statuses:
            status = "sources_found"
        else:
            status = "unknown"

        return {
            "response": {
                # Existing fields remain unchanged.
                "action": (
                    ", ".join(tools_used)
                    if tools_used
                    else "None"
                ),
                "action_input": last_action_input,
                "observation": observations,
                "final_answer": result.get("output", ""),
                "tools_used": tools_used,

                # NEW: structured metadata for the API and Vue.
                "source": unique_sources,
                "status": status,
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

                # NEW: stable metadata fields on failure.
                "source": [],
                "status": "error",
            }
        }
