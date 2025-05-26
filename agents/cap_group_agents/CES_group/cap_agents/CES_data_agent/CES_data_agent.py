from agency_swarm import Agent
from agents.cap_group_agents.CES_group.cap_agents.CES_data_agent.tools import (
    ReadLog, WriteLog
)

_name = "CES_data_agent"

_description = """
负责处理华为云的监控数据管理相关操作，包括：查询监控数据、添加监控数据、批量查询监控数据、查询主机配置数据。
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