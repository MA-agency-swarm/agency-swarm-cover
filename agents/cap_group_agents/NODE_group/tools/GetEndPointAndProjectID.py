from agency_swarm.tools import BaseTool
from pydantic import Field
import os

class GetEndPointAndProjectID(BaseTool):
    def run(self):
        project = os.getenv("PROJECT")
        project_id = os.getenv("PROJECT_ID")
        return {
            "endpoint": f"cce.{project}.myhuaweicloud.com",
            "poject_id": project_id
        }