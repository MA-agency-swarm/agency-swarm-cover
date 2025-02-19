from agency_swarm import Agent
from agents.tools.read_json_file.ReadJsonFile import ReadJsonFile
from agents.tools.ask_user.AskUser import AskUser

_name = "subtask_manager"

_description = """
The responsibility is to manage messages between capability groups.
"""

_input_format = """
{
    "result": "QUERY",
    "context": "<Request content>"
}
"""

_instruction = f"""
As a subtask planner, you will receive a message request from a capability group manager. The request format is as follows:
{_input_format}

Thinking step by step, you should select the appropriate capability group manager to inquire based on the request content and return the results. If there is no suitable capability group manager, please use AskUser to directly ask the user how to answer the request and return the results.
"""


_tools = [ReadJsonFile, AskUser]

_file_folder = ""

def create_agent(*, 
                 description=_description, 
                 instuction=_instruction, 
                 tools=_tools, 
                 files_folder=_file_folder):
    return Agent(name=_name,
                 tools=tools,
                 description=description,
                 instructions=instuction,
                 files_folder=_file_folder,
                 temperature=0.5,
                 response_format='auto',
                 max_prompt_tokens=25000,)