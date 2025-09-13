from typing import Dict, Optional
from flows.ip_flow import PropriedadeIntelectualFlow

class IPFlowManager:
    def __init__(self):
        self.active_flows: Dict[str, PropriedadeIntelectualFlow] = {}

    def create_flow(self, flow_id: str, search_criteria: str, category_rules_file: str = "category_rules.json") -> PropriedadeIntelectualFlow:
        flow = PropriedadeIntelectualFlow(search_criteria, category_rules_file)
        self.active_flows[flow_id] = flow
        return flow

    def get_flow(self, flow_id: str) -> Optional[PropriedadeIntelectualFlow]:
        return self.active_flows.get(flow_id)

    def execute_flow(self, flow_id: str) -> dict:
        flow = self.get_flow(flow_id)
        if not flow:
            return {"error": f"Fluxo '{flow_id}' não encontrado"}
        try:
            result = flow.kickoff()
            report = flow.get_final_report()
            return report
        except Exception as e:
            return {"error": f"Erro ao executar fluxo: {str(e)}"}

    def list_flows(self):
        return list(self.active_flows.keys())
