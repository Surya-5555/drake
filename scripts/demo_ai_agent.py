import asyncio
import json
import traceback
import sys
import os
import difflib

from pydantic import BaseModel, Field
from typing import Dict, Any, List
from mcp import ClientSession
from mcp.client.sse import sse_client
from dotenv import load_dotenv

load_dotenv()

try:
    from openai import AsyncOpenAI
    import instructor
except ImportError:
    print("Please install openai and instructor: pip install openai instructor")
    sys.exit(1)

# --- Configuration from environment (NO hardcoding) ---
OLLAMA_BASE_URL = os.getenv("OLLAMA_HOST", "http://localhost:11434") + "/v1"
MODEL_NAME = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:14b")
MCP_PROXY_URL = os.getenv("MCP_PROXY_URL", "http://localhost:8000/mcp/sse")


class ToolSelection(BaseModel):
    selected_tool_name: str = Field(..., description="The exact name of the tool to execute, or 'NONE' if no tool is needed")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="The arguments to pass to the tool, matching its schema exactly")
    reasoning: str = Field(..., description="Why this tool was chosen and how arguments were populated")
    agent_response: str = Field(..., description="A natural language response communicating back to the user.")


async def verify_llm_server() -> bool:
    """Performs a real server-level health check against the LLM backend. No fallback."""
    print(f"  [Pre-flight] Checking LLM server at {OLLAMA_BASE_URL}...")
    try:
        raw_client = AsyncOpenAI(base_url=OLLAMA_BASE_URL, api_key="ollama")
        models = await raw_client.models.list()
        model_ids = [m.id for m in models.data]
        print(f"  [Pre-flight] LLM server is LIVE. Available models: {', '.join(model_ids)}")
        if MODEL_NAME not in model_ids:
            print(f"  [Pre-flight] WARNING: Requested model '{MODEL_NAME}' not found in available models!")
            print(f"  [Pre-flight] Available models: {model_ids}")
            return False
        print(f"  [Pre-flight] Model '{MODEL_NAME}' confirmed available.")
        return True
    except Exception as e:
        print(f"  [Pre-flight] FAILED to reach LLM server: {e}")
        return False


async def decide_tool_with_llm(client: instructor.AsyncInstructor, prompt: str, tools: List[dict]) -> ToolSelection:
    """Uses the REAL LLM to pick the right tool. NO fallback, NO fake responses."""
    print(f"  [Agent] Sending prompt to LLM (Model: {MODEL_NAME}) at {OLLAMA_BASE_URL}...")

    # Format tools for the LLM prompt
    tools_context = []
    tool_names_list = []
    for t in tools:
        tool_names_list.append(t['name'])
        tools_context.append(f"- Tool Name: {t['name']}\n  Description: {t['description']}\n  Schema: {json.dumps(t['inputSchema'])}")

    system_prompt = (
        "You are an advanced AI Server Administrator Agent for Dell infrastructure.\n"
        "You have access to the following dynamic server management tools via the Model Context Protocol (MCP):\n"
        f"{chr(10).join(tools_context)}\n\n"
        "Your job is to read the user prompt and decide WHICH tool to use and WHAT arguments to pass it.\n\n"
        "RULES YOU MUST FOLLOW:\n"
        f"1. The selected_tool_name MUST BE EXACTLY ONE OF THESE: {', '.join(tool_names_list)}. Do not invent or guess tool names.\n"
        "2. ARGUMENTS MUST ONLY contain keys that exist in the selected tool's 'Schema'. Do NOT pass arguments that are not in the schema.\n"
        "3. Before returning, VERIFY: check the selected tool's Schema 'properties' — every key in your arguments dict must be a valid property in that schema. If the schema has no properties or is empty, pass an empty dict {}.\n"
        "4. Match the tool by its DESCRIPTION — pick the tool whose description best matches the user's intent.\n"
        "5. If a tool isn't needed, return 'NONE' for selected_tool_name and respond conversationally in agent_response.\n"
        "Always be concise and clear."
    )

    # NO try/except wrapping to fallback — if LLM fails, we crash loud
    selection = await client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        response_model=ToolSelection,
        max_retries=2
    )
    return selection


async def run_ai_agent(user_prompt: str):
    print("=====================================================================")
    print("                DELL DRAKE: AI AGENT ORCHESTRATION DEMO")
    print("=====================================================================\n")
    print(f" LLM Backend : Ollama ({OLLAMA_BASE_URL})")
    print(f" Model       : {MODEL_NAME}")
    print(f" MCP Proxy   : {MCP_PROXY_URL}\n")

    # --- STEP 1: Server-level LLM health check (NO fallback) ---
    print("[1] Pre-flight: Verifying LLM server is alive...")
    llm_ok = await verify_llm_server()
    if not llm_ok:
        print("\n[FATAL] LLM server check FAILED. Cannot proceed without a live LLM.")
        print("  -> Ensure Ollama is running: `ollama serve`")
        print(f"  -> Ensure model is pulled: `ollama pull {MODEL_NAME}`")
        print("  -> NO fallback. NO fake responses. Exiting.")
        return

    # Initialize the instructor-patched OpenAI client pointing to Ollama
    client = instructor.from_openai(
        AsyncOpenAI(
            base_url=OLLAMA_BASE_URL,
            api_key="ollama",
        ),
        mode=instructor.Mode.JSON
    )

    print(f"\n[2] Agent received user prompt:")
    print(f'    "{user_prompt}"\n')

    # --- STEP 2: Connect to MCP and discover tools ---
    print("[3] Connecting to FastMCP Proxy Server to discover available tools...")
    try:
        async with sse_client(MCP_PROXY_URL) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                print("  -> Connected to MCP proxy successfully.")

                tools_response = await session.list_tools()
                available_tools = []
                for t in tools_response.tools:
                    available_tools.append({
                        "name": t.name,
                        "description": t.description or "No description",
                        "inputSchema": t.inputSchema
                    })
                print(f"  -> Discovered {len(available_tools)} available tools in the MCP registry.\n")

                # --- STEP 3: Ask the REAL LLM to decide (no mock, no fallback) ---
                print("[4] Agent 'thinking' (LLM analyzing prompt against tool schemas)...")
                selection = await decide_tool_with_llm(client, user_prompt, available_tools)

                print(f"\n[5] Agent Decision:")
                print(f"  - Agent Response : {selection.agent_response}")
                print(f"  - Reasoning      : {selection.reasoning}")
                print(f"  - Selected Tool  : {selection.selected_tool_name}")
                print(f"  - Arguments      : {json.dumps(selection.arguments, indent=2)}\n")

                # If no tool needed
                if selection.selected_tool_name.upper() == "NONE":
                    print("[6] Agent decided no tool execution is needed for this prompt.")
                    print("=====================================================================")
                    print("                      AGENT WORKFLOW COMPLETE")
                    print("=====================================================================")
                    return

                # Validate the tool exists (with fuzzy matching for LLM typos)
                tool_names = [t["name"] for t in available_tools]
                if selection.selected_tool_name not in tool_names:
                    close_matches = difflib.get_close_matches(selection.selected_tool_name, tool_names, n=1, cutoff=0.8)
                    if close_matches:
                        print(f"  [SYSTEM] Auto-correcting tool name typo: '{selection.selected_tool_name}' -> '{close_matches[0]}'")
                        selection.selected_tool_name = close_matches[0]
                    else:
                        print(f"  [ERROR] Agent selected a non-existent tool: {selection.selected_tool_name}")
                        print(f"  [ERROR] No close matches found. Available tools: {tool_names[:10]}...")
                        return

                # --- STEP 4: Execute the chosen tool via MCP ---
                print(f"[6] Executing tool '{selection.selected_tool_name}' via MCP...")
                result = await session.call_tool(
                    selection.selected_tool_name,
                    arguments=selection.arguments
                )

                print("\n[7] Execution Complete. Full Tool Output:")
                print("---------------------------------------------------------------------")
                for content in result.content:
                    if content.type == "text":
                        try:
                            parsed_text = json.loads(content.text)
                            print(json.dumps(parsed_text, indent=2))
                        except Exception:
                            print(content.text)
                    else:
                        print(f"  [{content.type}]: {content}")
                print("---------------------------------------------------------------------")

                print("\n=====================================================================")
                print("                      AGENT WORKFLOW COMPLETE")
                print("=====================================================================")

    except Exception as e:
        print(f"\n[ERROR] Connection or execution failed: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python demo_ai_agent.py <your prompt here>")
        print('Example: python demo_ai_agent.py "List all available server systems"')
        sys.exit(1)

    prompt = " ".join(sys.argv[1:])
    asyncio.run(run_ai_agent(prompt))
