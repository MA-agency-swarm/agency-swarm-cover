from agency_swarm import Agent
from agents.tools.read_json_file.ReadJsonFile import ReadJsonFile
from agents.tools.ask_user.AskUser import AskUser

_name = "task_manager_rag"

_description = """
职责是负责能力群之间的消息管理
"""

_input_format = """
{
    "result": "QUERY",
    "context": <请求内容>
}
"""

_instruction = f"""
作为任务规划者，你将接收到来自某个能力群manager的消息请求，请求格式如下:
{_input_format}
一步步思考，你应该根据请求内容选择合适的能力群manager进行询问并返回结果，如果没有合适的能力群manager，请通过`AskUser`向用户直接询问如何回答请求并返回结果

"""


_tools = [ReadJsonFile, AskUser]

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