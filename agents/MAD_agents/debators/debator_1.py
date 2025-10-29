from agency_swarm import Agent
from agents.tools.read_context_index.ReadContextIndex import ReadContextIndex
from agents.tools.read_json_file.ReadJsonFile import ReadJsonFile

_name = "debator_1"

_description = """
职责是根据假设描述和其他debator的反馈，判断该假设的合理性和可行性
"""

_instruction = f"""

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