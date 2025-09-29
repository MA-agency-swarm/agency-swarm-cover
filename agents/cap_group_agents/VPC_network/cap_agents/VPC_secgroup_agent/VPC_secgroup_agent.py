from agency_swarm import Agent
from agents.cap_group_agents.VPC_network.cap_agents.VPC_secgroup_agent.tools import (
    ReadAPI
)
from agents.cap_group_agents.cap_agent_instruction import cap_agent_instruction
from agents.basic_agents.job_agent.tools.CallAPI import CallAPI
from agents.cap_group_agents.VPC_network.tools import (
    GetEndPointAndProjectID, AskManagerParams
)
from agents.tools.read_json_file.ReadJsonFile import ReadJsonFile

_name = "VPC_secgroup_agent"
_manager_name = "VPC_network_manager"
_description = """
负责华为云安全组管理任务，包括创建安全组、查询安全组、删除安全组，创建安全组规则、查询安全组规则、删除安全组规则。
特别注意：
1. 不同的安全组id，属于不同的安全组
2. 不同的安全组规则id，属于不同的安全组规则
3. 在判定之前任务是否已经完成时，必须严格匹配用户请求中的安全组id和安全组规则id
"""

import os

current_path = os.path.abspath(os.path.dirname(__file__))
_instruction = cap_agent_instruction(_name, _description, _manager_name)

_tools = [ReadAPI.ReadAPI, CallAPI, GetEndPointAndProjectID.GetEndPointAndProjectID, AskManagerParams.AskManagerParams, ReadJsonFile]

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