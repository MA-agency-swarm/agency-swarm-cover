from agency_swarm import Agent
from agents.cap_group_agents.rag_optimize_instruction import rag_optimize_instruction
from agents.tools.read_json_file.ReadJsonFile import ReadJsonFile

_name = "CLUSTER_rag_optimizer"

_description = """
负责集群管理能力群的任务细化
"""

_group_name = "集群管理能力群"

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
1. **CLUSTER_lifecycle_agent**: 负责k8s集群生命周期管理任务，包括：创建集群，删除集群，更新指定的集群，获取指定的集群，集群休眠，集群唤醒，查询指定集群支持配置的参数列表，批量添加指定集群的资源标签，批量删除指定集群的资源标签。
2. **CLUSTER_specification_change_agent**: 负责k8s集群规格变更任务，包括：变更集群规格。
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