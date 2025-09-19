from agency_swarm import Agent
from agents.cap_group_agents.OS_group.cap_agents.OS_agent.tools import (
    ReadAPI, GetEndPointAndProjectID, AskManagerParams
)
from agents.cap_group_agents.cap_agent_instruction import cap_agent_instruction
from agents.basic_agents.job_agent.tools.CallAPI import CallAPI

_name = "OS_agent"
_manager_name = "OS_manager"
_description = """
OS_agent: 负责华为云ECS操作系统管理任务，包括重装弹性云服务器操作系统（安装 Cloud-init）、切换弹性云服务器操作系统（安装 Cloud-init）、重装弹性云服务器操作系统（未安装 Cloud-init）、切换弹性云服务器操作系统（未安装 Cloud-init）。"""

import os

current_path = os.path.abspath(os.path.dirname(__file__))
_instruction = cap_agent_instruction(_name,_description,_manager_name)

_tools = [ReadAPI.ReadAPI, CallAPI, GetEndPointAndProjectID.GetEndPointAndProjectID, AskManagerParams.AskManagerParams,ReadJsonFile]

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