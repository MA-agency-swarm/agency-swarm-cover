from agency_swarm import Agent
from agents.tools.read_json_file.ReadJsonFile import ReadJsonFile
from agents.basic_agents.job_agent.tools import ReadFile

_name = "task_inspector_rag"

_description = """
职责是检查task_planner_rag规划的任务是否合理
"""
_input_format = """
{
    "user_request": ...,
    "task_graph": {
        "task_1": {
            "title": 任务名称,
            "id": 任务ID,
            "capability_group": <能力群名称>,
            "description": 任务描述,
            "dep": <前置任务ID列表>
        },
        ...
    }
}
"""

_output_format = """
{
    "review": "YES"/"NO",
    "explain": <解释原因>
}
"""

_instruction = f"""作为审查者，你将从task_planner_rag那里收到一个 JSON 格式的任务规划结果 <task_graph> 和原始任务请求 <user_request>。
输入格式为:
{_input_format}

注意：每次得到输入时，你都需要通过`ReadJsonFile`从context_tree.json中读取已完成的所有步骤所产生的上下文信息。

请严谨专业地一步步思考:
1. 首先，你需要确保**输入中的 <task_graph> 是JSON格式**；
2. 你需要检查<user_request>是否可以分解为<task_graph>，且确保<task_graph>任务的拆分和执行顺序合理；
3. 确保<task_graph>中所有操作都可通过**回复中文文字或执行命令行**实现；
4. 你需要保证<task_graph>中没有**多余**的确认或查询步骤，如确认资源是否存在等；
5. 确保<task_graph>中每个任务的执行能力群"capability_group"名称正确且合理，所有能力群名称和介绍如下：
    a. "软件能力群": 负责软件包管理、代码仓库管理、软件配置优化（A-Tune工具）；
    b. "安全能力群": 负责漏洞扫描（secScanner工具）、漏洞修复（SysCare工具）；
    c. "操作系统能力群": 负责用户和文件等权限管理、网络及防火墙管理；
    d. "文件能力群": 负责进行结构化分析汇总和文本结构化输出等文本相关任务、对目标服务器进行可编辑文件的读写、执行脚本文件；
    e. "弹性云服务器(ECS)管理能力群": ECS管理能力群提供全面的ECS实例管理功能，包括创建、删除、查询、修改、迁移、启动、停止、重启等核心操作，以及克隆、规格推荐、网卡和硬盘配置等扩展功能；
    f. "镜像管理能力群": 负责华为云镜像资源管理任务，包括：查询镜像列表，更新镜像信息，制作镜像，镜像文件快速导入，使用外部镜像文件制作数据镜像，制作整机镜像，注册镜像，导出镜像，查询镜像支持的OS列表;
    g. "统一身份认证服务IAM能力群": 负责华为云账户信息管理，包括获取AK和SK，用于身份验证和授权；
    h. "VPC网络管理能力群": VPC网络管理能力群提供对虚拟私有云（VPC）的管理功能，包括创建、删除和修改VPC；创建、删除和修改子网；配置安全组规则，控制网络流量。

你应该按照以下json格式评估<task_graph>:
{_output_format}

如果任务拆分和流程合理，请在"review"字段填入"YES"；如果任务拆分和流程有问题，请在"review"字段填入"NO"，并在"explain"字段填入你觉得不合理的原因。
"""

_tools = [ReadJsonFile]

_file_folder = ""


def create_agent(
    *,
    description=_description,
    instuction=_instruction,
    tools=_tools,
    files_folder=_file_folder,
):
    return Agent(
        name=_name,
        tools=tools,
        description=description,
        instructions=instuction,
        files_folder=files_folder,
        temperature=0.5,
        response_format="auto",
        max_prompt_tokens=25000,
    )
