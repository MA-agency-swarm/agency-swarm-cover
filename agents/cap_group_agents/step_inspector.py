from agency_swarm import Agent
from agents.tools.read_json_file.ReadJsonFile import ReadJsonFile

_name = "step_inspector"

_description = """
职责是检查step_planner规划的任务是否合理
"""
_input_format = """
{
    "user_request": "...",
    "task_graph": {
        "step_1": {
            "title": "Step Name",
            "id": "Step ID",
            "agent": ["agent_name_1", ...],
            "description": "Step Description",
            "dep": "<List of predecessor step IDs>",
        },
        ...
    }
}
"""

_output_format = """
{
    "review": "YES"/"NO",
    "explain": <Explanation of reasons>
}
"""

_instruction = f"""
As a reviewer, you will receive a JSON-formatted task planning result <task_graph> and the original user request <user_request> from the task_planner.

The input format is:
{_input_format}

You need to read the existing context information from the environment from context_index.json using `ReadJsonFile`.

Please think step by step:
0. You need to ensure that the <task_graph> in the input is in JSON format;
1. You need to check whether <user_request> can be decomposed into <task_graph>, and ensure that the task splitting and execution order of <task_graph> are reasonable;
2. Ensure that there are no operations in <task_graph> that are not implemented by **Huawei Cloud API or ssh connection command line instructions or writing and running scripts**;
3. The environment already has authentication information such as Huawei Cloud access authentication, and has been learned by the required agent. Ensure that there are no steps such as obtaining access credentials in the task plan;
4. Unless <user_request> or context_index.json has instructions, the task execution environment should not create **any resources** at the beginning. Ensure that the resources required for each task should be created in the **preceding task**;
5. You need to ensure that there are no **redundant** confirmation or query steps in the task plan.

You should evaluate the TASK according to the following JSON format:
{_output_format}

If the task splitting and process are reasonable, please fill in "YES" in the "review" field; if there is a problem with the task process, please fill in "NO" in the "review" field, and fill in the "explain" field with the reasons you think are unreasonable.


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