from agency_swarm import Agent
from agents.cap_group_agents.VPC_network.cap_agents.VPC_subnet_agent.tools import (
    ReadAPI
)
from agents.cap_group_agents import cap_agent_instruction

_name = "VPC_subnet_agent"
_manager_name = "VPC_manager"
_description = """
负责华为云子网管理任务，包括创建子网、查询子网、查询子网列表、更新子网、删除子网。
"""

import os

current_path = os.path.abspath(os.path.dirname(__file__))
_instruction = cap_agent_instruction(_name, _description, _manager_name)

_tools = [ReadAPI.ReadAPI]

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