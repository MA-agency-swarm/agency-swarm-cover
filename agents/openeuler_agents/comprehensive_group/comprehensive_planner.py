from agency_swarm import Agent
from agents.openeuler_agents.planner_instruction import planner_instruction
from agents.tools.read_json_file.ReadJsonFile import ReadJsonFile
from agents.basic_agents.job_agent.tools import ReadFile

_name = "comprehensive_planner"

_description = """
综合能力群的步骤规划
"""

_group_name = "综合能力群"

_input_format = """
{
    "title": <本次子任务的名称>,
    "description": <本次子任务的描述>,
    "total_subtask_graph": <所有子任务的规划图>
}
"""

_agents = """
1. **text_agent**: 负责对当前任务进行分析并输出文本结果。
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

_instruction = planner_instruction(_group_name, _input_format, _agents, _output_format)+"注意：请规划尽可能少的步骤完成需求，并且尽可能避免规划归纳总结类步骤，能力agnet具有自己收集上下文信息的能力"

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