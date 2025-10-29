from agency_swarm.tools import BaseTool
from pydantic import Field
import json
import os

class CheckLogForFailures(BaseTool):

    read_file_path: str = Field(..., description="需要读取的文件的路径")

    def run(self):
        agents_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        target_path = os.path.join(agents_dir, "files", self.read_file_path)
        with open(target_path, 'r', encoding='utf-8') as file:
            file_content = file.read()
        if len(file_content) > 20000:
            file_content = file_content[: 20000]

        print(f"CheckLogForFailures: reading {target_path}")
        print(f"content: {file_content}")
        if file_content.strip() == "":
            return {"tool":"CallAPI", "result": "FAIL", "context": "api调用没有返回结果,执行成功"}
        check_result = self.send_message_to_agent(recipient_agent_name="check_log_agent", message=file_content)
        if "该任务执行失败" in check_result:
            return {"tool":"CallAPI", "result": "FAIL", "context": f"api调用结果保存于{target_path},判断的结果内容为{check_result}"}
        return {"tool":"CallAPI", "result": "SUCCESS", "context": f"api调用结果保存于{target_path},判断的结果内容为{check_result}"}
  