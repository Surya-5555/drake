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

# Configure from environment (no hardcoding)
OLLAMA_BASE_URL = os.getenv("OLLAMA_HOST", "http://localhost:11434") + "/v1"
MODEL_NAME = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:14b")
MCP_PROXY_URL = os.getenv("MCP_PROXY_URL", "http://localhost:8000/mcp/sse")


def validate_arguments(tool_name: str, arguments: Dict[str, Any], tools: List[dict]) -> tuple[bool, str]:
    """Validate that LLM-selected arguments match the tool's actual schema."""
    tool = next((t for t in tools if t["name"] == tool_name), None)
    if not tool:
        return False, f"Tool '{tool_name}' not found in registry"
    
    schema = tool.get("inputSchema", {})
    valid_props = set(schema.get("properties", {}).keys())
    required_props = set(schema.get("required", []))
    given_props = set(arguments.keys())
    
    # Check for unexpected arguments
    unexpected = given_props - valid_props
    if unexpected:
        return False, (
            f"Invalid arguments {unexpected} for tool '{tool_name}'.\n"
            f"  Valid arguments are: {valid_props or '(none - pass empty dict)'}\n"
            f"  Required arguments: {required_props or '(none)'}"
        )
    
    # Check for missing required arguments
    missing = required_props - given_props
    if missing:
        return False, (
            f"Missing required arguments {missing} for tool '{tool_name}'.\n"
            f"  Required: {required_props}"
        )
    
    return True, "OK"

class ToolSelection(BaseModel):
    selected_tool_name: str = Field(..., description="The exact name of the tool to execute, or 'NONE' if no tool is needed")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="The arguments to pass to the tool, matching its schema exactly")
    reasoning: str = Field(..., description="Why this tool was chosen and how arguments were populated")
    agent_response: str = Field(..., description="A natural language response communicating back to the user.")

async def decide_tool_with_llm(client: instructor.AsyncInstructor, prompt: str, tools: List[dict]) -> ToolSelection:
    print(f"  [Agent] Connecting to local Ollama LLM (Model: {MODEL_NAME}) at {OLLAMA_BASE_URL}...")
    
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

async def interactive_loop():
    print("=====================================================================")
    print("           DELL DRAKE: INTERACTIVE AI AGENT TERMINAL")
    print("=====================================================================")
    print(f" LLM Backend: Ollama ({OLLAMA_BASE_URL})")
    print(" Type 'exit' or 'quit' to leave the terminal.\n")

    # Initialize the instructor-patched OpenAI client pointing to Ollama
    client = instructor.from_openai(
        AsyncOpenAI(
            base_url=OLLAMA_BASE_URL,
            api_key="ollama", # API key is required by the SDK, but ignored by Ollama
        ),
        mode=instructor.Mode.JSON
    )

    print(f"[SYSTEM] Connecting to FastMCP Proxy Server ({MCP_PROXY_URL})...")
    try:
        async with sse_client(MCP_PROXY_URL) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                print("  -> Connected to MCP proxy successfully.")

                # List tools available via MCP (these are ONLY approved workflows)
                tools_response = await session.list_tools()
                available_tools = []
                for t in tools_response.tools:
                    available_tools.append({
                        "name": t.name,
                        "description": t.description or "No description",
                        "inputSchema": t.inputSchema
                    })
                
                # Display approved tool summary
                print(f"  -> Discovered {len(available_tools)} approved workflow tools:\n")
                for i, t in enumerate(available_tools, 1):
                    params = list(t["inputSchema"].get("properties", {}).keys())
                    params_str = ', '.join(params) if params else '(no params)'
                    print(f"     {i:3d}. {t['name']:<50s} [{params_str}]")
                print()

                while True:
                    user_prompt = input("\n[USER]> ")
                    if user_prompt.lower() in ["exit", "quit"]:
                        print("\nShutting down AI Agent terminal...")
                        break
                    
                    if not user_prompt.strip():
                        continue

                    print("\n[SYSTEM] Agent is thinking...")
                    try:
                        selection = await decide_tool_with_llm(client, user_prompt, available_tools)
                        
                        print(f"\n[AGENT]> {selection.agent_response}")
                        print(f"  [Agent Internal Reasoning]: {selection.reasoning}")

                        if selection.selected_tool_name and selection.selected_tool_name.upper() != "NONE":
                            print(f"\n[SYSTEM] Agent selected tool '{selection.selected_tool_name}'")
                            print(f"  - Parameters: {json.dumps(selection.arguments, indent=2)}")
                            
                            tool_names = [t["name"] for t in available_tools]
                            
                            # Fuzzy matching to fix LLM typo/hallucinations
                            if selection.selected_tool_name not in tool_names:
                                close_matches = difflib.get_close_matches(selection.selected_tool_name, tool_names, n=1, cutoff=0.8)
                                if close_matches:
                                    print(f"  [SYSTEM] Auto-correcting tool name: '{selection.selected_tool_name}' -> '{close_matches[0]}'")
                                    selection.selected_tool_name = close_matches[0]
                                else:
                                    print(f"  [ERROR] Tool '{selection.selected_tool_name}' does not exist. Available tools:")
                                    for tn in tool_names:
                                        print(f"    - {tn}")
                                    continue

                            # Pre-execution schema validation
                            valid, msg = validate_arguments(selection.selected_tool_name, selection.arguments, available_tools)
                            if not valid:
                                print(f"\n  [VALIDATION FAILED] {msg}")
                                print(f"  [SYSTEM] Skipping execution — LLM passed invalid arguments.")
                                continue

                            # Execute the chosen tool via MCP
                            print(f"\n[SYSTEM] Executing '{selection.selected_tool_name}' via MCP...")
                            result = await session.call_tool(
                                selection.selected_tool_name, 
                                arguments=selection.arguments
                            )
                            
                            print("\n[SYSTEM] Tool Execution Complete. Result payload:")
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
                        else:
                            print("\n[SYSTEM] Agent did not invoke any tools for this prompt.")
                    
                    except Exception as llm_err:
                        print(f"\n[ERROR] Local LLM encountered an error: {llm_err}")
                        print("Please ensure Ollama is running (`ollama run llama3`) in another terminal.")

    except Exception as e:
        print(f"\n[CRITICAL ERROR] Connection to FastMCP proxy failed: {e}")
        print("Please ensure your proxy server is running (python -m uvicorn src.proxy.server:app --port 8000)")

if __name__ == "__main__":
    asyncio.run(interactive_loop())
