from agency_swarm import Agent
from agents.openeuler_agents.planner_instruction import planner_instruction
from agents.tools.read_json_file.ReadJsonFile import ReadJsonFile
from agents.basic_agents.job_agent.tools import ReadFile

_name = "file_planner"

_description = """
文件能力群的步骤规划
"""

_group_name = "文件能力群"

_input_format = """
{
    "title": <本次子任务的名称>,
    "description": <本次子任务的描述>,
    "total_subtask_graph": <所有子任务的规划图>
}
"""

_agents = """
1. **text_agent**: 负责对当前任务进行分析并输出文本结果。（只会对上下文进行分析，不能对目标运维环境的文件进行读写）
2. **file_io_agent**: 负载对运维目标环境中的可编辑文件进行读写
3. **script_agent**: 负责执行脚本文件、查看脚本文件是否正常运行
"""

_output_format = """
{
    "step_1": {
        "title": 步骤名称,
        "id": 步骤ID, 
        "agent": [agent_name_1, ...],
        "description": 步骤描述, 
        "dep": <前置步骤ID列表>
    },
    ...
}
"""

_instruction = planner_instruction(_group_name, _input_format, _agents, _output_format)+"注意：1. 尽可能避免规划归纳总结类步骤,能力agnet具有自己收集上下文信息的能力;2. 不要单独规划编写脚本的任务，智能体可以直接生成并部署脚本；3. 脚本**执行**后，请仔细判断脚本有没有正常运行"+"python类型脚本运行之后的出错可能不会在标准输出中体现，请规划步骤检查运行后的输出日志"

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