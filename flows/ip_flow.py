from crewai.flow.flow import Flow, listen, start
from pydantic import BaseModel
from typing import Dict, Any, Optional
import json
import traceback

from agents.ip_agents import IPAgents
from tools.custom_tools import (
    IPDataCollectorTool,
    NLPClassificationTool,
    DataAnalysisTool,
    VisualizationTool
)
from database.persist_dados import BuscapiDB
from tasks.ip_tasks import IPTaskManager
from tasks.pdf_worker import enqueue_pdf_job

# 1. Definir o Estado do Fluxo
class PropriedadeIntelectualState(BaseModel):
    """Estado que será passado entre os passos do fluxo."""
    search_query_id: Optional[int] = None
    search_criteria: str = ""
    
    # Os dados serão armazenados como strings JSON, pois é o que as ferramentas retornam
    raw_data_json: Optional[str] = None
    classified_data_json: Optional[str] = None
    analysis_results_json: Optional[str] = None
    visualizations_json: Optional[str] = None
    
    # Para o relatório final
    final_report: Dict[str, Any] = {}
    error_message: Optional[str] = None

# 2. Definir o Fluxo (Flow)
class PropriedadeIntelectualFlow(Flow[PropriedadeIntelectualState]):
    """Fluxo principal para análise de propriedade intelectual usando crewai-flow."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Inicializa os agentes uma vez para todo o fluxo
        self.agents = IPAgents()
        # Inicializa o gerenciador de tarefas que encapsula a criação de Tasks/Agents
        self.task_manager = IPTaskManager(self.agents)
        self.db = BuscapiDB() # Manter uma conexão aberta durante o fluxo

    def _handle_error(self, step_name: str, e: Exception):
        """Centraliza o tratamento de erros."""
        error_msg = f"Erro no passo '{step_name}': {e}"
        print(f"❌ {error_msg}\n{traceback.format_exc()}")
        self.state.error_message = error_msg
        if self.state.search_query_id:
            self.db.insert_search_log(self.state.search_query_id, error_msg)
        # Retorna a mensagem de erro para parar o fluxo
        return error_msg

    @start()
    def iniciar_pesquisa(self) -> str:
            """Ponto de entrada do fluxo. Valida o estado inicial."""
            if not self.state.search_criteria or self.state.search_query_id is None:
                return self._handle_error("iniciar_pesquisa", ValueError("Critério de busca ou ID da busca não foram definidos no estado inicial."))
        
            log_msg = f"Fluxo iniciado para a busca ID {self.state.search_query_id} com critério: '{self.state.search_criteria}'"
            print(f"🚀 {log_msg}")
            self.db.insert_search_log(self.state.search_query_id, log_msg)
            return "Início da coleta de dados."

    # flows/ip_flow.py
    @listen(iniciar_pesquisa)
    def coletar_dados(self, previous_output: str) -> str:
        if self.state.error_message: return previous_output
        print("\n📊 Coletando dados...")
        try:
            # Cria a task de coleta e delega a execução ao agent associado
            collection_task = self.task_manager.create_data_collection_task()
            task_input = json.dumps({
                'query': self.state.search_criteria,
                'search_query_id': self.state.search_query_id
            })
            # Use o executor centralizado do TaskManager para executar a task e normalizar saída
            try:
                self.state.raw_data_json = self.task_manager.execute_task(collection_task, task_input, retries=2)
            except Exception as e:
                raise RuntimeError(f'Falha ao executar task de coleta: {e}')

            try:
                raw_list = json.loads(self.state.raw_data_json) if self.state.raw_data_json else []
                num_results = len(raw_list) if isinstance(raw_list, list) else 0
            except Exception:
                raw_list, num_results = [], 0

            log_msg = f"Coleta concluída. {num_results} resultados brutos obtidos e persistidos."
            print(f"✅ {log_msg}")
            self.db.insert_search_log(self.state.search_query_id, log_msg)
            return "Coleta de dados finalizada."
        except Exception as e:
            return self._handle_error("coletar_dados", e)
    
    @listen(coletar_dados)
    def classificar_dados(self, previous_output: str) -> str:
        if not self.state.raw_data_json:
            return previous_output
        try:
            # Executa classificação usando a task/agent definida no TaskManager
            classification_task = self.task_manager.create_data_classification_task()
            # Executa via executor centralizado
            try:
                self.state.classified_data_json = self.task_manager.execute_task(classification_task, self.state.raw_data_json, retries=2)
            except Exception as e:
                if self.db and self.state.search_query_id:
                    self.db.insert_search_log(self.state.search_query_id, f"Erro na classificação: {str(e)}")
                raise
            try:
                classified_count = len(json.loads(self.state.classified_data_json)) if self.state.classified_data_json else 0
            except Exception:
                classified_count = 0

            if self.db and self.state.search_query_id:
                self.db.insert_search_log(self.state.search_query_id, f"{classified_count} resultados classificados (persistência feita pela ferramenta).")

            print(f"✅ Classificação concluída: {classified_count} registros (persistidos pela ferramenta)")
            return f"Classificação concluída: {classified_count} registros válidos"

        except Exception as e:
            if self.db and self.state.search_query_id:
                self.db.insert_search_log(self.state.search_query_id, f"Erro na classificação: {str(e)}")
            print(f"❌ Erro na classificação: {str(e)}")
            return f"Erro na classificação: {str(e)}"

    @listen(classificar_dados)
    def analisar_dados(self, previous_output: str) -> str:
        """Analisa os dados classificados para extrair insights."""
        
        if not self.state.classified_data_json:
            return previous_output

        print("\n📈 Analisando dados...")
        try:
            # Executa a análise via TaskManager executor (normalize saída)
            analysis_task = self.task_manager.create_analysis_task()
            try:
                self.state.analysis_results_json = self.task_manager.execute_task(
                    analysis_task,
                    self.state.classified_data_json,
                    preferred_tool_cls=DataAnalysisTool,
                    retries=2
                )
            except Exception as e:
                raise RuntimeError(f'Falha ao executar análise de dados: {e}')

            log_msg = "Analise de dados conlcuida com Sucesso"
            print(f"✅ {log_msg}")
            self.db.insert_search_log(self.state.search_query_id, log_msg)
            print ("Analise de dados conlcuida com Sucesso em ip_flow")
            return "Análise de dados finalizada."
        except Exception as e:
            return self._handle_error("analisar_dados", e)

    @listen(analisar_dados)
    def gerar_visualizacoes(self, previous_output: str) -> str:
        if not self.state.analysis_results_json:
            return previous_output
        try:
            # Executa geração de visualizações via task/agent
            visualization_task = self.task_manager.create_visualization_task()
            # Mantemos o JSON string no state e passamos a string adiante para as ferramentas
            try:
                self.state.visualizations_json = self.task_manager.execute_task(
                    visualization_task,
                    self.state.analysis_results_json,
                    preferred_tool_cls=VisualizationTool,
                    retries=1
                )
            except Exception as e:
                if self.db and self.state.search_query_id:
                    self.db.insert_search_log(self.state.search_query_id, f"Erro na execução da visualização: {e}")
                raise

            print("📊 Visualizações geradas com sucesso")
            return "Visualizações geradas"
        except Exception as e:
            if self.db and self.state.search_query_id:
                self.db.insert_search_log(self.state.search_query_id, f"Erro na geração de visualizações: {str(e)}")
            return self._handle_error("gerar_visualizacoes", e)

    def _generate_final_report(self):
        try:
            # Helper interno para carregar JSONs com segurança
            def _safe_json_load(json_str, default_value):
                try:
                    return json.loads(json_str) if json_str else default_value
                except (json.JSONDecodeError, TypeError):
                    return default_value

            classified_data = _safe_json_load(self.state.classified_data_json, [])
            analysis_results = _safe_json_load(self.state.analysis_results_json, {})
            visualizations = _safe_json_load(self.state.visualizations_json, {})
            raw_data = _safe_json_load(self.state.raw_data_json, [])

            self.state.final_report = {
                "success": True,
                "flow_id": self.state.search_query_id,
                "search_criteria": self.state.search_criteria,
                "data_collected": len(raw_data),
                "classified_data": classified_data,
                "analysis_results": analysis_results,
                "visualizations": visualizations,
                # O campo 'llm_model' será preenchido pelo agente que invocou a LLM (se disponível).
                "llm_model": getattr(self.agents, 'last_used_llm_model', None),
                "insights": analysis_results.get('insights', 'Nenhum insight gerado.')
            }

            # Marca o registro como concluído e adiciona log
            if self.db and self.state.search_query_id:
                try:
                    self.db.update_search_query_status(self.state.search_query_id, 'completed')
                    self.db.insert_search_log(self.state.search_query_id, "Fluxo concluído e relatório final gerado.")
                except Exception as db_e:
                    print(f"Aviso: falha ao atualizar status no DB: {db_e}")

            # Enfileira geração de PDF em background para não bloquear a conclusão do fluxo
            try:
                pdf_job_meta = enqueue_pdf_job(
                    results=self.state.final_report,
                    search_query_id=self.state.search_query_id
                )
                # Anexa referência ao job no relatório final
                self.state.final_report['pdf_job'] = {
                    'job_id': pdf_job_meta.get('job_id'),
                    'status': pdf_job_meta.get('status'),
                    'output_path': pdf_job_meta.get('output_path')
                }
                if self.db and self.state.search_query_id:
                    self.db.insert_search_log(self.state.search_query_id, f"PDF generation enqueued: job_id={pdf_job_meta.get('job_id')}")
            # Observação sobre diferenças de design nas visualizações:
            # Ao incluir gráficos gerados por Plotly em relatórios PDF, o fluxo converte
            # figuras interativas em imagens (PNG). Isso pode alterar detalhes do visual,
            # como interatividade, tooltips, animações e algumas estilizações CSS/JS
            # que só estão disponíveis em ambientes web. Também dependemos de um
            # renderizador headless (kaleido/orca) para produzir as imagens; diferenças
            # de versão ou de back-end podem gerar variações visuais entre os testes
            # interativos e o PDF final.
            except Exception as pj_e:
                print(f"Aviso: falha ao enfileirar geração de PDF: {pj_e}")
                if self.db and self.state.search_query_id:
                    self.db.insert_search_log(self.state.search_query_id, f"Falha ao enfileirar PDF: {pj_e}")

            print("📑 Relatório final gerado com sucesso (PDF enfileirado)")
            return self.state.final_report
        except Exception as e:
            if self.db and self.state.search_query_id:
                self.db.insert_search_log(self.state.search_query_id, f"Erro ao gerar relatório final: {str(e)}")
            return self._handle_error("generate_final_report", e)

    def kickoff(self, state: PropriedadeIntelectualState = None) -> Dict[str, Any]:
        """Sobrescreve o kickoff para definir o estado inicial e gerar o relatório final."""
        # Converte o objeto de estado Pydantic em um dicionário,
        # que é o formato esperado pelo método `kickoff` da classe pai.
        initial_inputs = state.model_dump() if state else None

        # Chama o kickoff da superclasse, passando o dicionário de inputs.
        # A superclasse cuidará de inicializar o estado interno corretamente.
        super().kickoff(inputs=initial_inputs)

        # Após a execução do fluxo, gera o relatório final
        self._generate_final_report()

        self.db.close()

        return self.state.final_report


# 3. Definir o Serviço Orquestrador
class IPAnalysisService:
    """
    Serviço que orquestra o PropriedadeIntelectualFlow para análise de PI.
    """
    
    def __init__(self):
        """Inicializa o serviço."""
        pass

    def start_analysis(self, search_criteria: str) -> str:
        """
        Cria o registro inicial da busca no banco de dados e retorna o ID.
        """
        db = BuscapiDB()
        try:
            search_query_id = db.insert_search_query(criteria=search_criteria, status='pending')
            db.insert_search_log(search_query_id, "Registro de busca criado. Aguardando execução do Flow.")
            return search_query_id
        finally:
            db.close()

    def execute_analysis(self, search_query_id: int) -> Dict[str, Any]:
        """
        Executa o fluxo completo do crewai-flow usando o ID da busca.
        """
        db = BuscapiDB()
        try:
            query_info = db.get_search_query_by_id(search_query_id)
            if not query_info:
                return {"error": f"ID de busca {search_query_id} não encontrado."}
            
            search_criteria = query_info['criteria']
            db.update_search_query_status(search_query_id, 'processing')
            
            # 1. Criar a instância do fluxo
            ip_flow = PropriedadeIntelectualFlow()
            
            # 2. Definir o estado inicial
            initial_state = PropriedadeIntelectualState(
                search_query_id=search_query_id,
                search_criteria=search_criteria
            )
            
            # 3. Executar o fluxo com o estado inicial
            final_report = ip_flow.kickoff(state=initial_state)            
            return final_report
        except Exception as e:
            error_msg = f"Erro fatal ao orquestrar o fluxo: {e}"
            print(f"❌ {error_msg}\n{traceback.format_exc()}")
            db.update_search_query_status(search_query_id, 'error')
            db.insert_search_log(search_query_id, error_msg)
            return {"error": error_msg}
        finally:
            db.close()
