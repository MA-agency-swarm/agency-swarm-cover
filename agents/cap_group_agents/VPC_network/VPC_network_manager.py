from agency_swarm import Agent
from agents.cap_group_agents.manager_instruction import manager_instruction
from agents.tools.get_param_value.GetParamValue import GetParamValue

_name = "VPC_network_manager"

_description = """
负责VPC网络管理能力群的消息管理
"""

_group_name = "VPC网络管理能力群"

_superior_agent = "subtask_manager"

_instruction = manager_instruction(_group_name, _superior_agent)

_tools = [GetParamValue]

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