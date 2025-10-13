from agency_swarm import Agent
from agents.openeuler_agents.planner_instruction import planner_instruction
from agents.tools.read_json_file.ReadJsonFile import ReadJsonFile
from agents.basic_agents.job_agent.tools import ReadFile

_name = "os_planner"

_description = """
负责操作系统能力群的步骤规划
"""

_group_name = "操作系统能力群"

_input_format = """
{
    "title": <本次子任务的名称>,
    "description": <本次子任务的描述>,
    "total_subtask_graph": <所有子任务的规划图>
}
"""

_agents = """
1. **permissions_agent**: 负责管理OpenEuler系统上的用户权限和文件访问等权限。
2. **network_agent**: 负责管理OpenEuler系统上的防火墙规则等网络配置。
3. **user_agent**: 负责管理OpenEuler系统上的用户权限以及用户创建的相关进程的查看、终止。
4. **basic_agent**: 负责执行OpenEuler系统上的基本命令操作，如文件操作、系统信息查询等。
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

_instruction = planner_instruction(_group_name, _input_format, _agents, _output_format)

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