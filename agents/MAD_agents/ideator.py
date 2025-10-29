from agency_swarm import Agent
from agents.tools.read_context_index.ReadContextIndex import ReadContextIndex
from agents.tools.read_json_file.ReadJsonFile import ReadJsonFile

_name = "ideator"

_description = """
职责是根据任务描述，为完成该任务作出合理假设
"""

_output_format = """
[
    {
        "title": <假设标题>,
        "description": <假设描述>
    },
    ...
]
"""

_instruction = f"""
你是一个假设推理者，你需要对接收到的任务认真思考，提出合理假设

{_output_format}
"""


_tools = [ReadContextIndex, ReadJsonFile]

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