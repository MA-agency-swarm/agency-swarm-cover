import json

from pydantic import Field

from agency_swarm.tools import BaseTool
from agents.openeuler_agents.tools.ssh_executor import SSHCommandExecutor
import os
from datetime import datetime
HOST = "XXX"
PORT = 22
USERNAME = "root"
PASSWORD = "XXX"

SSH_CONNECTION_ERROR = -1




class SSHExecuteCommand(BaseTool):
    """通过SSH执行命令行命令"""

    command: str = Field(..., description="需要执行的命令")
    host: str = Field(..., description="SSH服务器地址")
    port: int = Field(PORT, description="SSH服务器端口")    
    username: str = Field(..., description="SSH登录用户名")
    password: str = Field(..., description="SSH登录密码")

    def run(self):

        executor = SSHCommandExecutor(
            hostname=self.host,
            username=self.username,
            password=self.password,
            port=self.port,
        )
        success_connect = executor.connect()
        print(f"SSHExecuteCommand: executing {self.command}")
        print("ssh debug log 01")
        if not success_connect:
            res = {
                "full_stdout": "",
                "full_stderr": "",
                "final_status": SSH_CONNECTION_ERROR,
            }
        else:
            res = executor.execute_command_common(command=self.command)
        print("ssh debug log 02")
        result_file = self._save_result_to_file(res)
        print("ssh debug log 03")
        print(
            "SSH:",
            json.dumps(
                {"command": self.command, "result": res}, indent=4, ensure_ascii=False
            ),
        )

        check_result = self.send_message_to_agent(
            recipient_agent_name="check_log_agent",
            message=json.dumps(
                {"command": self.command, "result": res}, indent=4, ensure_ascii=False
            ),
        )

        if "该任务执行失败" in check_result:
            return {"tool":"SSHExecuteCommand", "command": self.command, "command_result":result_file, "result": "FAIL", "context": check_result}
        return {"tool":"SSHExecuteCommand", "command": self.command, "command_result":result_file, "result": "SUCCESS", "context": check_result}
    
    def _save_result_to_file(self, res: dict) -> str:
        """将res保存到临时文件并返回文件路径"""
        agents_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"ssh_result_{timestamp}.json"
        file_path = os.path.join(agents_dir, "files", f"ssh_result_{timestamp}.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=4)
        return f"ssh_result_{timestamp}.json"

if __name__=="__main__":
    tool = SSHExecuteCommand(command="for i in $(seq 1 3); do echo 'Line $i (yield)'; sleep 1; done")
    print(tool.run())
