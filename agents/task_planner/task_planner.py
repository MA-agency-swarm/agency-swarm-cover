from agency_swarm import Agent
from agents.tools.read_json_file.ReadJsonFile import ReadJsonFile
_name = "task_planner"

_description = """
职责是根据用户请求规划任务
"""
_input_format = """
"""

_output_format = """
{
    "task_1": {
        "title": 任务名称,
        "id": 任务ID, 
        "description": 任务的详细描述, 
        "dep": <前置任务ID列表>,
    },
    ...
}
"""

_instruction = """
无论用户输入什么，你都应该直接输出以下内容:
{
    "task_0": {
        "title": "获取可用的ECS规格和镜像信息",
        "id": "0",
        "description": "通过调用华为云API获取在'cn-north-4'可用区可用的ECS规格和镜像信息。",
        "dep": []
    },
    "task_1": {
        "title": "创建虚拟私有云（VPC）",
        "id": "1",
        "description": "在华为云北京'cn-north-4'可用区创建一个VPC，为ECS实例提供网络环境。",
        "dep": ["0"]
    },
    "task_2": {
        "title": "创建子网",
        "id": "2",
        "description": "在创建的VPC中创建一个子网，ECS实例将会放置在这个子网中。",
        "dep": ["1"]
    },
    "task_3": {
        "title": "创建安全组",
        "id": "3",
        "description": "创建一个安全组，用于控制ECS实例的入站和出站流量。",
        "dep": ["1"]
    },
    "task_4": {
        "title": "申请弹性公网IP（EIP）",
        "id": "4",
        "description": "为ECS实例申请一个弹性公网IP，以便能够通过公网访问。",
        "dep": []
    },
    "task_5": {
        "title": "创建ECS实例",
        "id": "5",
        "description": "在'cn-north-4'可用区创建ECS实例，并将其放入创建的VPC、子网和安全组中，同时绑定申请的弹性公网IP。",
        "dep": ["2", "3", "4"]
    }
}
"""


f"""
作为任务规划者，你需要将用户输入解析成以下 JSON 格式的多个任务: 
{_output_format}

请逐步思考，用户可能会提供修改建议，综合考虑完成此任务所需的步骤。
# 注意，拆分后的每个任务完成过程中都不能半途终止；
# 注意: 初始环境中资源都是充足的，你不需要对可用区资源是否足以执行任务进行查询；
# 注意: 除非用户请求中有提供初始条件的描述，初始环境中除了华为云账号和可用的华为云访问凭证，没有创建**任何资源**；确保你的规划有你任务中**所需资源的创建**或**所需信息的获取**步骤，否则请先完成它们；
# 注意: 为了防止用户隐私不被泄露，华为云认证信息已被执行任务的agent得知，你的任务规划中不需要获取华为云访问凭证等认证信息

如果需要重新规划，你需要从completed_tasks.json中读取已完成的任务，从context.json中读取之前任务完成过程中的上下文信息，从error.json中读取之前任务完成过程中的出现的error信息，一步步思考该在原先规划上如何修改，保证推进用户请求 (即总任务) 的完成
注意，你应该保证**已完成任务（内容不应该有任何修改）**出现在你修改后的任务规划中，并且保证新任务规划执行过程中能避免或修复error.json中的Error

对于每个任务，你需要在 "id" 字段中以"task_正整数"的形式为其分配一个单独的任务 ID，并在 "description" 字段中详细地描述任务内容，并在 "dep" 字段中写入该任务需要完成的前置任务 ID 列表（如果没有前置任务，则写入 []），允许环的构建，表示这些任务需要多次迭代执行。
确保你的任务规划尽可能并行。如果两个任务可以同时开始执行而彼此不冲突，则可以并行执行。
请注意，无论任务是什么，任务执行过程中都只能通过调用api或ssh远程命令行连接或编写、运行脚本进行操作。
"""


_tools = []

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