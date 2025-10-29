from agency_swarm import Agent, Agency

from agents.MAD_agents.test_task_planner import test_task_planner
from agents.MAD_agents.ideator import ideator
from agents.MAD_agents.debators.debator_1 import debator_1
from agents.MAD_agents.debators.debator_2 import debator_2
from agents.MAD_agents.debators.debator_3 import debator_3

from agency_swarm import set_openai_key

from dotenv import load_dotenv
import sys
import os
import datetime

load_dotenv()
set_openai_key(os.getenv('OPENAI_API_KEY'))

def main():
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file_path = os.path.join("log", f"run_log_{timestamp}.txt")
    # 创建日志文件
    log_file = open(log_file_path, 'w', encoding='utf-8', buffering=1)
    
    # 创建自定义的输出类，同时将输出发送到文件和终端
    class TeeOutput:
        def __init__(self, file, terminal):
            self.file = file
            self.terminal = terminal
            
        def write(self, message):
            self.terminal.write(message)
            self.file.write(message)
            
        def flush(self):
            self.terminal.flush()
            self.file.flush()
    
    # 保存原始的stdout，并设置新的输出重定向
    original_stdout = sys.stdout
    sys.stdout = TeeOutput(log_file, original_stdout)
    
    try:
        test_task_planner_instance = test_task_planner.create_agent()
        ideator_instance = ideator.create_agent()

        debator_1_instance = debator_1.create_agent()
        debator_2_instance = debator_2.create_agent()
        debator_3_instance = debator_3.create_agent()

        chat_graph = [test_task_planner_instance, ideator_instance,
                      debator_1_instance, debator_2_instance, debator_3_instance
                    ]

        agency_manifesto = """
        """

        thread_strategy = {
            "always_new": [
                (test_task_planner_instance, ideator_instance),
                (ideator_instance, debator_1_instance),
                (ideator_instance, debator_2_instance),
                (ideator_instance, debator_3_instance),
                (debator_1_instance, debator_2_instance),
                (debator_2_instance, debator_3_instance),
                (debator_3_instance, debator_1_instance),
            ]
        }

        agency = Agency(agency_chart=chat_graph,
                        thread_strategy=thread_strategy,
                        temperature=0.5,
                        max_prompt_tokens=25000,)

        MAD_agents = {
            "test_task_planner": test_task_planner_instance,
            "ideator": ideator_instance,
            "debators": [debator_1_instance, debator_2_instance, debator_3_instance]
        }

        agency.mad_test(MAD_agents)
    finally:
        # 关闭日志文件和恢复标准输出
        sys.stdout = original_stdout
        log_file.close()
        print(f"日志已保存到：{log_file_path}")
    

if __name__ == "__main__":
    try:
        main()
    finally: # 响铃
        import winsound
        import time
        winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        time.sleep(2)
        winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        time.sleep(2)
        winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
