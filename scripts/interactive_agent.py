import asyncio
import json
import traceback
import sys
import os

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

# Configure the OpenAI client to point to the local Ollama instance
OLLAMA_BASE_URL = os.getenv("OLLAMA_HOST", "http://localhost:11434") + "/v1"
MODEL_NAME = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:14b") # Updated to use your preferred Qwen coder model

class ToolSelection(BaseModel):
    selected_tool_name: str = Field(..., description="The exact name of the tool to execute, or 'NONE' if no tool is needed")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="The arguments to pass to the tool, matching its schema exactly")
    reasoning: str = Field(..., description="Why this tool was chosen and how arguments were populated")
    agent_response: str = Field(..., description="A natural language response communicating back to the user.")

async def decide_tool_with_llm(client: instructor.AsyncInstructor, prompt: str, tools: List[dict]) -> ToolSelection:
    print(f"  [Agent] Connecting to local Ollama LLM (Model: {MODEL_NAME}) at {OLLAMA_BASE_URL}...")
    
    # Format tools for the LLM prompt
    tools_context = []
    for t in tools:
        tools_context.append(f"- Tool Name: {t['name']}\n  Description: {t['description']}\n  Schema: {json.dumps(t['inputSchema'])}")
    
    system_prompt = (
        "You are an advanced AI Server Administrator Agent for Dell infrastructure.\n"
        "You have access to the following dynamic server management tools via the Model Context Protocol (MCP):\n"
        f"{chr(10).join(tools_context)}\n\n"
        "Your job is to read the user prompt and decide WHICH tool to use and WHAT arguments to pass it.\n"
        "If a tool isn't needed, return 'NONE' for selected_tool_name and respond conversationally in agent_response.\n"
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

    print("[SYSTEM] Connecting to FastMCP Proxy Server to discover live tools...")
    try:
        async with sse_client("http://localhost:8000/mcp/sse") as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                print("  -> Connected to MCP proxy successfully.")

                # List tools available via MCP
                tools_response = await session.list_tools()
                available_tools = []
                for t in tools_response.tools:
                    available_tools.append({
                        "name": t.name,
                        "description": t.description or "No description",
                        "inputSchema": t.inputSchema
                    })
                print(f"  -> Discovered {len(available_tools)} live server tools in the registry.\n")

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
                            print(f"\n[SYSTEM] Agent executing tool '{selection.selected_tool_name}' via MCP...")
                            print(f"  - Parameters passed: {selection.arguments}")
                            
                            # Validate the tool actually exists
                            tool_names = [t["name"] for t in available_tools]
                            if selection.selected_tool_name not in tool_names:
                                print(f"  [ERROR] Agent selected a non-existent tool: {selection.selected_tool_name}")
                                continue

                            # Execute the chosen tool via MCP
                            result = await session.call_tool(
                                selection.selected_tool_name, 
                                arguments=selection.arguments
                            )
                            
                            print("\n[SYSTEM] Tool Execution Complete. Result payload:")
                            for content in result.content:
                                if content.type == "text":
                                    try:
                                        parsed_text = json.loads(content.text)
                                        print(json.dumps(parsed_text, indent=2))
                                    except Exception:
                                        print(content.text)
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
