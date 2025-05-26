from agency_swarm.tools import BaseTool
from pydantic import Field
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

from agents.basic_agents.api_agents.tools.api_database import search_from_sqlite, API_DATABASE_FILE
from agents.basic_agents.api_agents.tools.utils import try_parse_json, assert_list_of_dicts

class SelectParamTable(BaseTool):
    '''
    根据用户需求，选择一个 API 在一张参数表中的所有需要填写的参数字段。
    '''

    user_requirement: str = Field(..., description="自然语言的用户需求")
    api_name: str = Field(..., description="目标API名")
    table_id: int = Field(default=0, description="表号，常见于“详情请参见表...”，默认值为0")

    def select_parameter(self, row):
        returned_keys = ["parameter", "description", "type"]
        returned_info = {key: row[key] for key in returned_keys if key in row and row[key] is not None}
        
        # 1. add mandatory simple parameters by default
        if row["mandatory"] == 1 and not ("type" in row and row["type"] is not None and ("array" in row["type"].lower() or "object" in row["type"].lower())):
            return [returned_info]

        # have to let agent decide
        # 2. construct the message
        message_obj = {
            "user_requirement": self.user_requirement,
            "api_name": self.api_name,
            "parameter": row["parameter"],
            "description": row["description"],
        }
        if row["type"] is not None:
            message_obj["type"] = row["type"]
        if row["mandatory"] == 1:
            message_obj["mandatory"] = row["mandatory"]
        
        # 3. send the message and handle response
        selected_str = self.send_message_to_agent(recipient_agent_name="Param Selector", message=json.dumps(message_obj, ensure_ascii=False))
        
        if "不需要该参数" in selected_str:
            return []
        elif "需要该参数" in selected_str:
            return [returned_info]
        else:
            selected = try_parse_json(selected_str)
            assert_list_of_dicts(selected)
            return selected

    def run(self):

        # 1. for each parameter in this table, call Param Selector to decide whether to select it.
        param_table_df = search_from_sqlite(database_path=API_DATABASE_FILE, table_name='request_parameters', condition=f"api_name='{self.api_name}' AND table_id='{self.table_id}'")
        selected_params = []

        with ThreadPoolExecutor() as executor:
            futures = []
            for _, row in param_table_df.iterrows():
                futures.append(executor.submit(self.select_parameter, row))
            for future in as_completed(futures):
                selected_params += future.result()

        return json.dumps(selected_params, ensure_ascii=False)
