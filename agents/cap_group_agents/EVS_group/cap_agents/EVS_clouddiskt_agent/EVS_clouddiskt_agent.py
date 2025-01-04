from agency_swarm import Agent
from agents.cap_group_agents.CES_group.cap_agents.monitor_alarm_history_agent.tools import (
    read, rizhi
)

_name = "EVS_clouddiskt_agent"

_description = """
负责华为云云硬盘管理任务，包括：创建云硬盘、更新云硬盘、查询所有云硬盘详情、查询单个云硬盘详情、扩容云硬盘、删除云硬盘。
"""

_instruction = "./instructions.md"

_tools = [read, rizhi]

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