from agency_swarm import Agent
from agents.tools.read_context_index.ReadContextIndex import ReadContextIndex
from agents.tools.read_json_file.ReadJsonFile import ReadJsonFile

_name = "coodinator"

_description = """
职责是拆分任务，并做一定程度的规划
"""

_output_format = """
[
    {
        "task_id": <任务编号>,
        "title": <任务标题>
        "description": <任务描述>,
    },
    ...
]
"""

_instruction = f"""
你是一名专业的任务规划和分解专家。你的目标是接收用户的原始运维请求，并将其拆解成一系列清晰、具体、可独立执行的子任务，特别是那些需要提出假设才能解决的知识探索任务。

# 注意：确保每个子任务都是原子化的

你需要严格按照以下json格式输出：
{_output_format}

其中列表中每一项表示一个被拆分出来的任务。task_id字段填入一个不重复的整数，表示任务的编号；title字段填入任务标题；description字段填入该任务的详细描述
"""


_tools = [ReadContextIndex, ReadJsonFile]

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