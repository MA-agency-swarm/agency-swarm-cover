from agency_swarm import Agent
from agents.openeuler_agents.rag_optimize_instruction import rag_optimize_instruction
from agents.tools.read_json_file.ReadJsonFile import ReadJsonFile
from agents.basic_agents.job_agent.tools import ReadFile

_name = "file_rag_optimizer"

_description = """
文件能力群的任务细化
"""

_group_name = "文件能力群"

_input_format = """
{
    "title": <任务名称>,
    "description": <任务描述>,
    "total_task_graph": <所有任务的规划图>,
    "last_error": <之前执行该任务时的错误信息>
}
"""

_output_format = """
{
    "description": 任务描述,
    "agent": [agent_name_1, ...]
}
"""

_agents = """
1. **text_agent**: 负责对当前任务进行分析并输出文本结果。（只会对上下文进行分析，不能对目标运维环境的文件进行读写）
2. **file_io_agent**: 负载对运维目标环境中的可编辑文件进行读写
3. **script_agent**: 负责执行脚本文件、查看脚本文件是否正常运行
"""

_instruction = rag_optimize_instruction(_group_name, _input_format, _agents, _output_format)

_tools = [ReadJsonFile,ReadFile.ReadFile]

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