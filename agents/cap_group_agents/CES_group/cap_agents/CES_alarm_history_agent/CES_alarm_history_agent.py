from agency_swarm import Agent
from agents.cap_group_agents.CES_group.cap_agents.CES_alarm_history_agent.tools import (
    ReadLog, WriteLog
)
from agents.basic_agents.job_agent.tools.CallAPI import CallAPI

_name = "CES_alarm_history_agent"

_description = """
负责华为云的告警记录查询管理任务，包括：查询告警记录列表。
"""

import os

current_path = os.path.abspath(os.path.dirname(__file__))
_instruction = current_path + "/instructions.md"

_tools = [ReadLog.ReadLog, WriteLog.WriteLog, CallAPI]

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