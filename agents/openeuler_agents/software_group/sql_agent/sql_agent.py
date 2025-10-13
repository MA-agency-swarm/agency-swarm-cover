from agency_swarm import Agent

from agents.openeuler_agents.openeuler_agent_instruction import openeuler_agent_instruction
from agents.tools.read_json_file.ReadJsonFile import ReadJsonFile
from agents.basic_agents.job_agent.tools import ReadFile
from agents.openeuler_agents.tools.SSHExecuteCommand import SSHExecuteCommand


_name = "sql_agent"
_description = """
负责使用mysql语句管理数据库
注意：
1. cd命令和其他命令一起执行，使用`&&`连接；
2. 设置主从复制用户时，尽量修改用户插件为mysql_native_password并执行FLUSH PRIVILEGES;以避免SSL设置
3. 你需要仔细从上下文分析出连接到数据库的用户名和密码信息，不要随意生成
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