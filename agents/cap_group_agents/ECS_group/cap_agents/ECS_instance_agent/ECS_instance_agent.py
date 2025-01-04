from agency_swarm import Agent
from agents.cap_group_agents.CES_group.cap_agents.monitor_alarm_history_agent.tools import (
    read, rizhi
)

_name = "ECS_instance_agent"

_description = """
负责ECS实例生命周期管理任务，包括：创建云服务器，删除云服务器，创建云服务器（按需），查询云服务器详细信息，查询云服务器详情列表，查询云服务器列表，修改云服务器，冷迁移云服务器，批量启动云服务器，批量关闭云服务器，批量重启云服务器。
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