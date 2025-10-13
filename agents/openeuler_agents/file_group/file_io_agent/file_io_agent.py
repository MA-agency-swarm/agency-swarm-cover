from agency_swarm import Agent

from agents.openeuler_agents.openeuler_agent_instruction import openeuler_agent_instruction
from agents.tools.read_json_file.ReadJsonFile import ReadJsonFile
from agents.basic_agents.job_agent.tools import ReadFile
from agents.openeuler_agents.tools.SSHExecuteCommand import SSHExecuteCommand


_name = "file_io_agent"
_description = """
负责使用echo、cat等命令对可编辑文件进行读写。
注意：
1. cd命令和其他命令一起执行，使用`&&`连接；
2. 若要写入脚本内容，请自己根据用户请求生成正确的、可在OpenEuler环境中可执行的脚本并写入目标环境
3. 读取文件时，尽量避免一次性输出完整内容，须进行分块或截取读取，以防止文本超长。默认只读取文件的前后部分，例如：
cd /path && head -n 50 filename
或
cd /path && tail -n 50 filename
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