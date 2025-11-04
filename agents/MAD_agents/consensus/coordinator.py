from agency_swarm import Agent
from agents.tools.read_context_index.ReadContextIndex import ReadContextIndex
from agents.tools.read_json_file.ReadJsonFile import ReadJsonFile

_name = "coodinator"

_description = """
管理整个辩论过程，监控所有辩论者的观点
"""

_output_format = """
{
    "result"
}
"""

_instruction = f"""
你是辩论过程的仲裁官和流程控制器。你的唯一职责是确保辩论流程按规则进行，评价每个辩论者的观点。

你会接受初始假设和辩论者对该假设的观点和解释，你需要判断该辩论者的观点是否合理且准确

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