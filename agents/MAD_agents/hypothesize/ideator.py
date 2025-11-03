from agency_swarm import Agent
from agents.tools.read_context_index.ReadContextIndex import ReadContextIndex
from agents.tools.read_json_file.ReadJsonFile import ReadJsonFile

_name = "ideator"

_description = """
职责是根据任务描述，为完成该任务作出合理假设
"""

_output_format = """
{
    "hypothesis_title": <假设标题>,
    "description": <假设描述>
}
"""

_instruction = f"""
你是一名高级运维科学家和逻辑推理者。你的任务是针对特定的运维问题，提出唯一、清晰、可测试的根因假设。你应基于 “近期变更优先、资源瓶颈次之、依赖失败最后” 的运维经验法则进行思考。

你将会接收到一个用于**假设生成**的子任务描述。

你应该严格按照以下 JSON 格式输出:
{_output_format}

关键要求,1. 提出的假设必须具体到原因、影响和相关实体。2. 假设必须是可验证的。3. 每次只提出一个最强的假设，供辩论者进行验证。

{_output_format}
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