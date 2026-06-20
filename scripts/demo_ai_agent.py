import asyncio
import json
import traceback
import instructor
from ollama import AsyncClient as OllamaAsyncClient
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

from mcp import ClientSession
from mcp.client.sse import sse_client

class ToolSelection(BaseModel):
    selected_tool_name: str = Field(..., description="The name of the tool to execute")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="The arguments to pass to the tool, matching its schema")
    reasoning: str = Field(..., description="Why this tool was chosen and how arguments were populated")

async def decide_tool_with_llm(prompt: str, tools: List[dict]) -> ToolSelection:
    """Uses a local LLM to pick the right tool and populate arguments based on the prompt."""
    print(f"  [Agent] Connecting to local LLM (Ollama) to analyze the prompt...")
    
    # Format tools for the LLM prompt
    tools_context = []
    for t in tools:
        tools_context.append(f"- Tool Name: {t['name']}\n  Description: {t['description']}\n  Schema: {json.dumps(t['inputSchema'])}")
    
    system_prompt = (
        "You are a helpful AI Server Administrator Agent.\n"
        "You have access to the following server management tools (workflows):\n"
        f"{chr(10).join(tools_context)}\n\n"
        "Your job is to read the user prompt and decide WHICH tool to use and WHAT arguments to pass it.\n"
        "Return the JSON structure matching the required schema."
    )

    try:
        # Some versions of instructor use `from_ollama` or `patch`
        import instructor
        from ollama import AsyncClient as OllamaAsyncClient
        try:
            client = instructor.from_ollama(OllamaAsyncClient())
        except AttributeError:
            client = instructor.patch(OllamaAsyncClient())
            
        selection = await client.chat.completions.create(
            model="llama3", # or any default model like llama3, mistral, or phi3
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            response_model=ToolSelection,
            max_retries=2
        )
        return selection
    except Exception as e:
        print(f"  [Agent] Local LLM failed (is Ollama running?): {e}")
        print(f"  [Agent] Falling back to rule-based mock LLM...")
        
        # Mock fallback for demonstration purposes if Ollama isn't running
        if "reset" in prompt.lower() and "120" in prompt:
            return ToolSelection(
                selected_tool_name="mini_sys_reset_workflow",
                arguments={"ComputerSystemId": "sys-idrac-120"},
                reasoning="Mock LLM detected 'reset' and '120' in prompt, mapped to sys-idrac-120 reset workflow."
            )
        else:
            raise ValueError("Could not determine tool via mock fallback.")

async def run_ai_agent(user_prompt: str):
    print("=====================================================================")
    print("                DELL DRAKE: AI AGENT ORCHESTRATION DEMO")
    print("=====================================================================\n")
    print(f"[1] Agent received user prompt:\n    \"{user_prompt}\"\n")

    print("[2] Agent connecting to FastMCP Server to discover available tools...")
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
                print(f"  -> Discovered {len(available_tools)} available tools in the MCP registry.\n")

                # Ask the LLM (or mock) to decide
                print("[3] Agent 'thinking' (matching prompt to tools)...")
                selection = await decide_tool_with_llm(user_prompt, available_tools)
                
                print(f"\n[4] Agent Decision:")
                print(f"  - Reasoning: {selection.reasoning}")
                print(f"  - Selected Tool: {selection.selected_tool_name}")
                print(f"  - Arguments: {selection.arguments}\n")

                # Validate the tool actually exists
                tool_names = [t["name"] for t in available_tools]
                if selection.selected_tool_name not in tool_names:
                    print(f"  [ERROR] Agent selected a non-existent tool: {selection.selected_tool_name}")
                    return

                # Execute the chosen tool via MCP
                print(f"[5] Agent executing tool '{selection.selected_tool_name}' via MCP...")
                result = await session.call_tool(
                    selection.selected_tool_name, 
                    arguments=selection.arguments
                )
                
                print("\n[6] Execution Complete. Tool Output:")
                for content in result.content:
                    if content.type == "text":
                        try:
                            parsed_text = json.loads(content.text)
                            print(json.dumps(parsed_text, indent=2))
                        except Exception:
                            print(content.text)

                print("\n=====================================================================")
                print("                      AGENT WORKFLOW COMPLETE")
                print("=====================================================================")

    except Exception as e:
        print(f"\n[ERROR] Connection or execution failed: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    import sys
    prompt = "Please reset the computer system with ID sys-idrac-120."
    if len(sys.argv) > 1:
        prompt = " ".join(sys.argv[1:])
    
    asyncio.run(run_ai_agent(prompt))
