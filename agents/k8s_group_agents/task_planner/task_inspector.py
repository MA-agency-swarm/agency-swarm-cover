from agency_swarm import Agent
_name = "task_inspector"

_description = """
职责是检查task_planner规划的任务是否合理
"""
_input_format = """
{
    "user_request": ...,
    "task_graph": {
        "task_1": {
            "title": 任务名称,
            "id": 任务ID, 
            "description": 任务描述, 
            "dep": <前置任务ID列表>,
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

_instruction = f"""作为审查者，你将从task_planner那里收到一个 JSON 格式的任务规划结果 <task_graph> 和原始用户请求 <user_request>。
输入格式为:
{_input_format}

请严谨专业地一步步思考: 
1. 你需要确保输入中的 <task_graph> 是JSON格式；
2. 你需要检查<user_request>是否可以分解为<task_graph>，且确保<task_graph>任务的拆分和执行顺序合理；
3. 确保<task_graph>中所有操作都可通过**执行kubectl命令行**实现；
4. 除非<user_request>有说明，否则任务执行环境最开始应该没有创建**任何资源**，确保每个任务所需资源应该在**前置任务**中有所创建；
5. 你需要保证任务规划中没有**多余**的确认或查询步骤，如确认资源是否存在等。

你应该按照以下json格式评估<task_graph>: 
{_output_format}

如果任务拆分和流程合理，请在"review"字段填入"YES"；如果任务拆分和流程有问题，请在"review"字段填入"NO"，并在"explain"字段填入你觉得不合理的原因。
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