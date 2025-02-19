from agency_swarm import Agent
from agents.tools.read_json_file.ReadJsonFile import ReadJsonFile
_name = "scheduler"

_description = """
The responsibility is to schedule tasks.
"""

_input_format = """
{
    "main_task": ...,
    "plan_graph": {
        "task_1": {
            "title": "Task Name",
            "id": "Task ID",
            "description": "Task Description",
            "dep": "<List of predecessor task IDs>",
        },
        ...
    }
}
"""

_output_format = """
{
    "completed_tasks": ...,
    "next_tasks": [id_1, ...],
    "reason": ...
}
"""

_instruction = f"""
As a scheduler, you will receive subtask workflows and initial user requests, with the following input format:
You will receive a JSON-formatted subtask planning result <plan_graph> and a general task description <main_task>.
The input format is:
{_input_format}

You need to read the completed tasks from completed_tasks.json, read the context information from the previous task completion process from context_index.json, and consider the next subtasks to be completed in combination with the general task description step by step to ensure the completion of the general task.

Note: You should read completed_tasks.json and context_index.json every time you receive input.

You need to select all executable tasks for the next step based on completed tasks and context information, ensuring that they can be executed in parallel; if two tasks can start executing at the same time without conflicting with each other, they can be executed in parallel.

Your final scheduling result should be:
{_output_format}

You need to fill in the "reason" field with the reasons for selecting these tasks.
"""

f"""
作为调度者，你将接收到子任务流程和初始用户请求，输入格式如下:  
你将收到一个 JSON 格式的子任务规划结果 <plan_graph> 和总任务描述 <main_task>。
输入格式为:
{_input_format}

你需要从completed_tasks.json中读取已完成的任务，从context_index.json中读取之前任务完成过程中的上下文信息，并结合总任务描述一步步思考接下来需要完成的子任务，保证推进总任务的完成

注意: 你每次接收到输入时都应该读取一次completed_tasks.json和context_index.json

你需要根据已完成任务和上下文信息选出下一步可执行的所有任务，确保它们可以**并行执行**；如果两个任务可以同时开始执行而彼此不冲突，则可以并行执行。

你的最终调度结果应该为: 
{_output_format}

你需要在"reason"字段填入你选出这些任务的原因
"""

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
                 files_folder=_file_folder,
                 temperature=0.5,
                 response_format='auto',
                 max_prompt_tokens=25000,)