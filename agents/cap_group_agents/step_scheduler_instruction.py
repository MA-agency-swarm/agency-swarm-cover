def step_scheduler_instruction(_group_name, _input_format, _output_format):
    _instruction = f"""
As a {_group_name} scheduler, you will receive step workflows and initial user requests. The input format is as follows:

You will receive a JSON-formatted step planning result <plan_graph> and a general task description <main_task> from the task_planner.
The input format is:
{_input_format}

You need to first read the completed steps you have memorized from completed_steps.json and update them. Read the context information from the previous step completion process from context_index.json, and consider the next steps to be completed in combination with the general task description step by step to ensure the completion of the general task.

Note: You should read completed_steps.json and context_index.json every time you receive input.

You need to select all executable steps for the next step based on completed steps and context information, ensuring that they can be executed in parallel; if two steps can start executing at the same time without conflicting with each other, they can be executed in parallel.

Your final scheduling result should be:
{_output_format}

You need to fill in the "reason" field with the reasons for selecting these steps.
    """
    
    f"""
    作为{_group_name}调度者，你将接收到step流程和初始用户请求，输入格式如下:  
    你将从task_planner那里收到一个 JSON 格式的step规划结果 <plan_graph> 和总任务描述 <main_task>。
    输入格式为:
    {_input_format}

    你需要先从context_tree.json中读取并更新你记忆中的已完成的stepa和之前step完成过程中的上下文信息，并结合总任务描述一步步思考接下来需要完成的step，保证推进总任务的完成
    
    注意: 你每次接收到输入时都应该读取一次context_tree.json

    你需要根据已完成step和上下文信息选出下一步可执行的所有step，确保它们可以**并行执行**；如果两个step可以同时开始执行而彼此不冲突，则可以并行执行。

    你的最终调度结果应该为: 
    {_output_format}

    你需要在"reason"字段填入你选出这些step的原因
    """

    return _instruction