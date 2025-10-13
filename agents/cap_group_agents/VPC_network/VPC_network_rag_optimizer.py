from agency_swarm import Agent
from agents.cap_group_agents.rag_optimize_instruction import rag_optimize_instruction
from agents.tools.read_json_file.ReadJsonFile import ReadJsonFile

_name = "VPC_network_rag_optimizer"

_description = """
负责VPC网络管理能力群的任务细化
"""

_group_name = "VPC网络管理能力群"

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
1. **VPC_secgroup_agent**: 负责华为云安全组管理任务，包括创建安全组、查询安全组、删除安全组，创建安全组规则、查询安全组规则、删除安全组规则；
2. **VPC_subnet_agent**: 负责华为云子网管理任务，包括创建子网、查询子网、查询子网列表、更新子网、删除子网；
3. **VPC_vpc_agent**：负责华为云VPC管理任务，包括创建VPC、查询VPC、查询VPC列表、更新VPC、删除VPC。
"""

_instruction = rag_optimize_instruction(_group_name, _input_format, _agents, _output_format)

_tools = [ReadJsonFile]

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