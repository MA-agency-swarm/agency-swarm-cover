from agency_swarm import Agent
from agents.cap_group_agents.ECS_group.cap_agents.ECS_netcard_agent.tools import (
    ReadLog, WriteLog
)

_name = "ECS_netcard_agent"

_description = """
负责华为云ECS网卡管理任务，包括：批量添加云服务器网卡、批量删除云服务器网卡，查询云服务器网卡信息，云服务器切换虚拟私有云，更新云服务器指定网卡属性。
"""

import os

current_path = os.path.abspath(os.path.dirname(__file__))
_instruction = current_path + "/instructions.md"

_tools = [ReadLog.ReadLog, WriteLog.WriteLog]

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