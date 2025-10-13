from agency_swarm import Agent

from agents.openeuler_agents.openeuler_agent_instruction import openeuler_agent_instruction
from agents.tools.read_json_file.ReadJsonFile import ReadJsonFile
from agents.basic_agents.job_agent.tools import ReadFile
from agents.openeuler_agents.tools.SSHExecuteCommand import SSHExecuteCommand


_name = "script_agent"
_description = """
负责执行脚本文件。
注意：
1. cd命令和其他命令一起执行，使用`&&`连接；
"""

import os

current_path = os.path.abspath(os.path.dirname(__file__))
_instruction = openeuler_agent_instruction(_name,_description)

_tools = [ReadJsonFile, SSHExecuteCommand,ReadFile.ReadFile]

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
                 files_folder=files_folder,
                 temperature=0.5,
                 response_format='auto',
                 max_prompt_tokens=25000,)