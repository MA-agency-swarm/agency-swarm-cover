from agency_swarm import Agent
from agents.cap_group_agents.CES_group.cap_agents.CES_dashboard_agent.tools import (
    ReadLog, WriteLog
)

_name = "CES_dashboard_agent"

_description = """
负责华为云的监控看板及视图管理管理任务，包括：创建监控看板、查询监控看板列表、修改监控看板、批量删除监控看板、创建监控视图、查询监控视图列表、查询监控视图、删除监控视图、批量更新监控视图。
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