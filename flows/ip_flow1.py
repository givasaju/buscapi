from crewai.flow.flow import Flow, listen, start
from pydantic import BaseModel
from typing import Dict, List, Any
import json

from agents.ip_agents import IPAgents
from tasks.ip_tasks import IPTaskManager
from database.persist_dados import BuscapiDB


class PropriedadeIntelectualState(BaseModel):
    """Estado do fluxo de propriedade intelectual."""
    search_criteria: str = ""
    raw_data: List[Dict[str, Any]] = []
    classified_data: List[Dict[str, Any]] = []
    analysis_results: Dict[str, Any] = {}
    visualizations: Dict[str, str] = {}
    insights: str = ""
    flow_id: str = ""


class PropriedadeIntelectualFlow(Flow[PropriedadeIntelectualState]):
    """Fluxo principal para análise de propriedade intelectual."""

    def __init__(self, search_criteria: str = "IA na Educação"):
        super().__init__()
        self.agents = IPAgents()
        self.task_manager = IPTaskManager(self.agents)
        self.state.search_criteria = search_criteria

        # Inicializar conexão ao banco
        self.db = BuscapiDB(
            dbname="buscapi_bd",
            user="postgres",
            password="givas2025",
            host="localhost",
            port=5432
        )

        # Registrar busca e armazenar search_query_id
        self.search_query_id = self.db.insert_search_query(criteria=search_criteria, status='pending')

        # Para associar resultados brutos com classificados
        self.raw_result_ids = []

    @start()
    def iniciar_pesquisa(self) -> str:
        print(f"\n🚀 Iniciando fluxo de análise de propriedade intelectual")
        print(f"📋 Critérios de busca: {self.state.search_criteria}")
        print(f"🆔 ID do fluxo: {self.state.id}")
        self.state.flow_id = str(self.state.id)
        self.db.insert_search_log(self.search_query_id, "Fluxo iniciado.")
        return f"Fluxo iniciado para: {self.state.search_criteria}"

    @listen(iniciar_pesquisa)
    def coletar_dados(self, mensagem_inicial: str) -> str:
        print(f"\n📊 Coletando dados: {mensagem_inicial}")

        try:
            # Buscar explicitamente pelo tipo da ferramenta
            collection_task = self.task_manager.task_factory.create_data_collection_task(self.state.search_criteria)
            data_tool = next(t for t in collection_task.agent.tools if t.__class__.__name__ == "IPDataCollectorTool")
            raw_data_json = data_tool._run(self.state.search_criteria)

            try:
                raw_data = json.loads(raw_data_json)
                # garantir sempre lista
                if isinstance(raw_data, dict):
                    raw_data = [raw_data]
            except Exception as e:
                print(f"Erro ao processar dados brutos: {e}")
                raw_data = []

            valid_raw_data = []
            valid_raw_result_ids = []
            for item in raw_data:
                if isinstance(item, dict) and "error" in item:
                    print(f"[WARN] Ignorando resultado bruto inválido: {item.get('error')}")
                    continue
                valid_raw_data.append(item)
            # ... (persistência)
            for item in valid_raw_data:
                # Inserir resultado bruto no banco e guardar id
                raw_id = self.db.insert_search_result_raw(
                    search_query_id=self.search_query_id,
                    source=item.get('source', 'unknown'),
                    raw_json=item
                )
                valid_raw_result_ids.append(raw_id)

            if not valid_raw_data:
                print("❌ Nenhum dado bruto válido coletado! Abortando pipeline.")
                return "Erro: Nenhum dado bruto válido coletado"

            self.state.raw_data = valid_raw_data
            self.raw_result_ids = valid_raw_result_ids

            self.db.insert_search_log(self.search_query_id, f"{len(valid_raw_data)} resultados brutos persistidos.")

            print(f"✅ Coletados e persistidos {len(valid_raw_data)} registros válidos de dados brutos")
            return f"Dados coletados: {len(valid_raw_data)} registros válidos"
        except Exception as e:
            self.db.insert_search_log(self.search_query_id, f"Erro na coleta: {str(e)}")
            print(f"❌ Erro na coleta de dados: {str(e)}")
            return f"Erro na coleta: {str(e)}"

    @listen(coletar_dados)
    def classificar_dados(self, resultado_coleta: str) -> str:
        print(f"\n🏷️ Classificando dados: {resultado_coleta}")
        if not self.state.raw_data:
            return "Nenhum dado para classificar"
        try:
            classification_task = self.task_manager.task_factory.create_data_classification_task()
            classified_data_json = classification_task.agent.tools[0]._run(json.dumps(self.state.raw_data))
            classified_data = json.loads(classified_data_json)

            valid_classified_data = []
            count_saved = 0
            for idx, item in enumerate(classified_data):
                if not item or (isinstance(item, dict) and "error" in item):
                    print(f"[WARN] Ignorando resultado classificado inválido ou erro.")
                    continue
                raw_id = self.raw_result_ids[idx] if idx < len(self.raw_result_ids) else None
                if raw_id is None:
                    print(f"[WARN] Ignorando classificado sem raw_result_id correspondente.")
                    continue

                self.db.insert_search_result_structured(
                    search_result_raw_id=raw_id,
                    category=item.get("category", "Outros"),
                    title=item.get("title", ""),
                    date_found=item.get("filingDate") or item.get("publicationDate"),
                    applicant=item.get("applicantName") or item.get("applicant", ""),
                    summary=item.get("abstract") or item.get("summary", ""),
                    structured_json=item
                )
                valid_classified_data.append(item)
                count_saved += 1

            self.state.classified_data = valid_classified_data
            self.db.insert_search_log(self.search_query_id, f"{count_saved} resultados classificados persistidos.")

            print(f"✅ Classificação concluída e persistida: {count_saved} registros válidos")
            return f"Classificação concluída: {count_saved} registros válidos"
        except Exception as e:
            self.db.insert_search_log(self.search_query_id, f"Erro na classificação: {str(e)}")
            print(f"❌ Erro na classificação: {str(e)}")
            return f"Erro na classificação: {str(e)}"

    @listen(classificar_dados)
    def analisar_dados(self, resultado_classificacao: str) -> str:
        print(f"\n📈 Analisando dados: {resultado_classificacao}")
        if not self.state.classified_data:
            return "Nenhum dado classificado para analisar"
        try:
            analysis_task = self.task_manager.task_factory.create_analysis_task()
            analysis_results_json = analysis_task.agent.tools[0]._run(json.dumps(self.state.classified_data))
            self.state.analysis_results = json.loads(analysis_results_json)

            # Gerar insights (método interno)
            insights = self._generate_insights_from_analysis()
            self.state.insights = insights

            self.db.insert_search_log(self.search_query_id, "Análise concluída com sucesso.")

            print(f"✅ Análise concluída com {len(self.state.analysis_results)} métricas")
            return f"Análise concluída: {insights[:100]}..."
        except Exception as e:
            self.db.insert_search_log(self.search_query_id, f"Erro na análise: {str(e)}")
            print(f"❌ Erro na análise: {str(e)}")
            return f"Erro na análise: {str(e)}"

    @listen(analisar_dados)
    def gerar_visualizacoes(self, resultado_analise: str) -> str:
        print(f"\n📊 Gerando visualizações: {resultado_analise}")
        if not self.state.analysis_results:
            return "Nenhum resultado de análise para visualizar"
        try:
            visualization_task = self.task_manager.task_factory.create_visualization_task()
            visualizations = {}

            if "count_by_category" in self.state.analysis_results:
                bar_chart = visualization_task.agent.tools[1]._run(
                    json.dumps(self.state.analysis_results),
                    "bar",
                    "category_distribution.png",
                )
                visualizations["category_chart"] = bar_chart

            if "count_by_year" in self.state.analysis_results:
                line_chart = visualization_task.agent.tools[1]._run(
                    json.dumps(self.state.analysis_results),
                    "line",
                    "yearly_trends.png",
                )
                visualizations["trend_chart"] = line_chart

            self.state.visualizations = visualizations
            self.db.insert_search_log(self.search_query_id, f"{len(visualizations)} visualizações geradas.")

            print(f"✅ Visualizações geradas: {len(visualizations)} gráficos")
            return f"Visualizações prontas: {list(visualizations.keys())}"
        except Exception as e:
            self.db.insert_search_log(self.search_query_id, f"Erro na geração de visualizações: {str(e)}")
            print(f"❌ Erro na geração de visualizações: {str(e)}")
            return f"Erro nas visualizações: {str(e)}"

    def _generate_insights_from_analysis(self) -> str:
        insights = []
        if "count_by_category" in self.state.analysis_results:
            categories = self.state.analysis_results["count_by_category"]
            total = sum(categories.values())
            most_common = max(categories, key=categories.get)
            insights.append(
                f"A categoria mais comum é '{most_common}' com {categories[most_common]} registros"
                f" ({categories[most_common] / total * 100:.1f}% do total)."
            )
        if "count_by_year" in self.state.analysis_results:
            years = self.state.analysis_results["count_by_year"]
            if len(years) > 1:
                years_sorted = sorted(years.items())
                trend = (
                    "crescente"
                    if years_sorted[-1][1] > years_sorted[0][1]
                    else "decrescente"
                )
                insights.append(
                    f"A tendência temporal é {trend}, com {years_sorted[-1][1]} registros "
                    f"no ano mais recente ({years_sorted[-1][0]})."
                )
        return " ".join(insights) if insights else "Análise concluída com dados básicos."

    def get_final_report(self) -> Dict[str, Any]:
        # Atualizar status no banco para completed
        try:
            self.db.update_search_query_status(self.search_query_id, "completed")
            self.db.insert_search_log(self.search_query_id, "Busca marcada como concluída.")
        except Exception as e:
            print(f"[WARN] Falha ao atualizar status da busca no banco: {e}")

        return {
            "flow_id": self.state.flow_id,
            "search_criteria": self.state.search_criteria,
            "data_collected": len(self.state.raw_data),
            "data_classified": len(self.state.classified_data),
            "analysis_results": self.state.analysis_results,
            "insights": self.state.insights,
            "visualizations": self.state.visualizations,
            "status": "completed",
        }
class IPFlowManager:
    """Gerenciador para múltiplos fluxos de propriedade intelectual."""
    
    def __init__(self):
            self.active_flows = {}
    
    def create_flow(self, flow_id: str, search_criteria: str) -> PropriedadeIntelectualFlow:
            """Cria um novo fluxo."""
            flow = PropriedadeIntelectualFlow(search_criteria)
            self.active_flows[flow_id] = flow
            return flow
    
    def get_flow(self, flow_id: str) -> PropriedadeIntelectualFlow:
            """Retorna um fluxo específico."""
            return self.active_flows.get(flow_id)
    
    def execute_flow(self, flow_id: str) -> Dict[str, Any]:
            """Executa um fluxo completo."""
            flow = self.get_flow(flow_id)
            if not flow:
                return {"error": "Fluxo não encontrado"}
    
            try:
                # Executar o fluxo
                result = flow.kickoff()
                # self.db.update_search_query_status(self.search_query_id, 'completed') # PERPLEXITY
                # Atualizar o status da busca no banco - PERPLEXITY
                return flow.get_final_report()
            except Exception as e:
                return {"error": f"Erro na execução do fluxo: {str(e)}"}
    
    def list_flows(self) -> List[str]:
            """Lista todos os fluxos ativos."""
            return list(self.active_flows.keys())
    
    def __del__(self):
            try:
                self.db.close()
            except Exception:
                pass
