# CORREÇÃO FINAL COMPLETA

from crewai.flow.flow import Flow, listen, start
from pydantic import BaseModel
from typing import Dict, List, Any, Optional
import json
#import traceback

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

    def __init__(self, *args, **kwargs):
        """
        CRÍTICO: CrewAI Flow.__init__() NÃO ACEITA ARGUMENTOS!
        
        Este método foi modificado para capturar e corrigir automaticamente
        chamadas incorretas que passam argumentos.
        """
        
        # Se argumentos foram passados, extrair e armazenar para uso posterior
        search_criteria = None
        
        if args:
            print(f"⚠️  AVISO: PropriedadeIntelectualFlow recebeu argumentos: {args}")
            # Assumir que o primeiro argumento é search_criteria
            if len(args) >= 1 and isinstance(args[0], str):
                search_criteria = args[0]
                print(f"✅ Extraído search_criteria: {search_criteria}")
            
        if 'search_criteria' in kwargs:
            search_criteria = kwargs.pop('search_criteria')
            print(f"✅ Extraído search_criteria dos kwargs: {search_criteria}")
        
        # Chamar super().__init__() SEM argumentos (exigência do CrewAI)
        try:
            super().__init__()
        except Exception as e:
            print(f"❌ Erro ao inicializar Flow: {e}")
            # Se ainda der erro, tentar sem nenhum parâmetro
            Flow.__init__(self)
        
        # Inicializar componentes básicos
        self.agents = None
        self.task_manager = None
        self.db = None
        self.search_query_id = None
        self.raw_result_ids = []
        
        # Se search_criteria foi extraído dos argumentos, configurar automaticamente
        if search_criteria:
            self._auto_setup(search_criteria)

    def _auto_setup(self, search_criteria: str):
        """Configuração automática quando search_criteria é passado no __init__."""
        try:
            print(f"🔧 Configuração automática para: {search_criteria}")
            self.setup_flow(search_criteria)
        except Exception as e:
            print(f"⚠️  Erro na configuração automática: {e}")
            # Armazenar para configurar depois
            self._pending_search_criteria = search_criteria

    def setup_flow(self, search_criteria: str):
        """Configura o fluxo com critérios de busca e inicializa banco."""
        try:
            # Configurar estado
            self.state.search_criteria = search_criteria
            
            # Inicializar componentes
            if not self.agents:
                self.agents = IPAgents()
            if not self.task_manager:
                self.task_manager = IPTaskManager(self.agents)
            
            # Inicializar conexão ao banco
            if not self.db:
                self.db = BuscapiDB(
                    dbname="buscapi_bd",
                    user="postgres",
                    password="givas2025",
                    host="localhost",
                    port=5432
                )
                
            # Registrar busca e armazenar search_query_id
            if not self.search_query_id:
                self.search_query_id = self.db.insert_search_query(
                    criteria=search_criteria, 
                    status='pending'
                )
            
            print(f"✅ Fluxo configurado com sucesso para: {search_criteria}")
            
        except Exception as e:
            print(f"❌ Erro ao configurar fluxo: {e}")
            self.db = None
            self.search_query_id = None

    @start()
    def iniciar_pesquisa(self) -> str:
        """Inicia a pesquisa - configuração automática se necessário."""
        
        # Configuração tardia se necessário
        if hasattr(self, '_pending_search_criteria'):
            self.setup_flow(self._pending_search_criteria)
            delattr(self, '_pending_search_criteria')
        
        # Verificar se está configurado
        if not self.state.search_criteria:
            return "Erro: Critérios de busca não configurados"
        
        print(f"\n🚀 Iniciando fluxo de análise de propriedade intelectual")
        print(f"📋 Critérios de busca: {self.state.search_criteria}")
        print(f"🆔 ID do fluxo: {self.state.id}")
        
        self.state.flow_id = str(self.state.id)
        
        if self.db and self.search_query_id:
            try:
                self.db.insert_search_log(self.search_query_id, "Fluxo iniciado.")
            except Exception as e:
                print(f"⚠️  Erro ao registrar log: {e}")
        
        return f"Fluxo iniciado para: {self.state.search_criteria}"

    @listen(iniciar_pesquisa)
    def coletar_dados(self, mensagem_inicial: str) -> str:
        """Coleta dados brutos."""
        print(f"\n📊 Coletando dados: {mensagem_inicial}")

        # Verificar se task_manager está disponível
        if not self.task_manager:
            try:
                if not self.agents:
                    self.agents = IPAgents()
                self.task_manager = IPTaskManager(self.agents)
            except Exception as e:
                print(f"❌ Erro ao inicializar task_manager: {e}")
                return f"Erro na inicialização: {str(e)}"

        try:
            # Buscar explicitamente pelo tipo da ferramenta
            collection_task = self.task_manager.task_factory.create_data_collection_task(self.state.search_criteria)
            data_tool = next(t for t in collection_task.agent.tools if t.__class__.__name__ == "IPDataCollectorTool")
            raw_data_json = data_tool._run(self.state.search_criteria)

            try:
                raw_data = json.loads(raw_data_json)
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
                
            # Persistência no banco (se disponível)
            if self.db and self.search_query_id:
                for item in valid_raw_data:
                    try:
                        raw_id = self.db.insert_search_result_raw(
                            search_query_id=self.search_query_id,
                            source=item.get('source', 'unknown'),
                            raw_json=item
                        )
                        valid_raw_result_ids.append(raw_id)
                    except Exception as e:
                        print(f"⚠️  Erro ao salvar resultado bruto: {e}")

            if not valid_raw_data:
                print("❌ Nenhum dado bruto válido coletado!")
                return "Erro: Nenhum dado bruto válido coletado"

            self.state.raw_data = valid_raw_data
            self.raw_result_ids = valid_raw_result_ids

            if self.db and self.search_query_id:
                try:
                    self.db.insert_search_log(self.search_query_id, f"{len(valid_raw_data)} resultados brutos persistidos.")
                except Exception as e:
                    print(f"⚠️  Erro ao registrar log: {e}")

            print(f"✅ Coletados {len(valid_raw_data)} registros válidos")
            return f"Dados coletados: {len(valid_raw_data)} registros válidos"
            
        except Exception as e:
            error_msg = f"Erro na coleta de dados: {str(e)}"
            print(f"❌ {error_msg}")
            if self.db and self.search_query_id:
                try:
                    self.db.insert_search_log(self.search_query_id, f"Erro na coleta: {str(e)}")
                except:
                    pass
            return error_msg

    @listen(coletar_dados)
    def classificar_dados(self, resultado_coleta: str) -> str:
        """Classifica os dados coletados."""
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
                    print(f"[WARN] Ignorando resultado classificado inválido")
                    continue
                    
                raw_id = self.raw_result_ids[idx] if idx < len(self.raw_result_ids) else None
                if raw_id is None:
                    print(f"[WARN] Sem raw_result_id correspondente")
                    continue

                # Salvar no banco se disponível
                if self.db:
                    try:
                        self.db.insert_search_result_structured(
                            search_result_raw_id=raw_id,
                            category=item.get("category", "Outros"),
                            title=item.get("title", ""),
                            date_found=item.get("filingDate") or item.get("publicationDate"),
                            applicant=item.get("applicantName") or item.get("applicant", ""),
                            summary=item.get("abstract") or item.get("summary", ""),
                            structured_json=item
                        )
                    except Exception as e:
                        print(f"⚠️  Erro ao salvar classificado: {e}")
                        
                valid_classified_data.append(item)
                count_saved += 1

            self.state.classified_data = valid_classified_data
            
            if self.db and self.search_query_id:
                try:
                    self.db.insert_search_log(self.search_query_id, f"{count_saved} resultados classificados persistidos.")
                except Exception as e:
                    print(f"⚠️  Erro ao registrar log: {e}")

            print(f"✅ Classificação concluída: {count_saved} registros válidos")
            return f"Classificação concluída: {count_saved} registros válidos"
            
        except Exception as e:
            error_msg = f"Erro na classificação: {str(e)}"
            print(f"❌ {error_msg}")
            if self.db and self.search_query_id:
                try:
                    self.db.insert_search_log(self.search_query_id, error_msg)
                except:
                    pass
            return error_msg

    @listen(classificar_dados)
    def analisar_dados(self, resultado_classificacao: str) -> str:
        """Analisa os dados classificados."""
        print(f"\n📈 Analisando dados: {resultado_classificacao}")
        
        if not self.state.classified_data:
            return "Nenhum dado classificado para analisar"
            
        try:
            analysis_task = self.task_manager.task_factory.create_analysis_task()
            analysis_results_json = analysis_task.agent.tools[0]._run(json.dumps(self.state.classified_data))
            self.state.analysis_results = json.loads(analysis_results_json)

            # Gerar insights
            insights = self._generate_insights_from_analysis()
            self.state.insights = insights

            if self.db and self.search_query_id:
                try:
                    self.db.insert_search_log(self.search_query_id, "Análise concluída com sucesso.")
                except Exception as e:
                    print(f"⚠️  Erro ao registrar log: {e}")

            print(f"✅ Análise concluída com {len(self.state.analysis_results)} métricas")
            return f"Análise concluída: {insights[:100]}..."
            
        except Exception as e:
            error_msg = f"Erro na análise: {str(e)}"
            print(f"❌ {error_msg}")
            if self.db and self.search_query_id:
                try:
                    self.db.insert_search_log(self.search_query_id, error_msg)
                except:
                    pass
            return error_msg

    @listen(analisar_dados)
    def gerar_visualizacoes(self, resultado_analise: str) -> str:
        """Gera visualizações dos dados."""
        print(f"\n📊 Gerando visualizações: {resultado_analise}")
        
        if not self.state.analysis_results:
            return "Nenhum resultado de análise para visualizar"
            
        try:
            visualization_task = self.task_manager.task_factory.create_visualization_task()
            visualizations = {}

            if "count_by_category" in self.state.analysis_results:
                try:
                    bar_chart = visualization_task.agent.tools[1]._run(
                        json.dumps(self.state.analysis_results),
                        "bar",
                        "category_distribution.png",
                    )
                    visualizations["category_chart"] = bar_chart
                except Exception as e:
                    print(f"⚠️  Erro ao gerar gráfico de categorias: {e}")

            if "count_by_year" in self.state.analysis_results:
                try:
                    line_chart = visualization_task.agent.tools[1]._run(
                        json.dumps(self.state.analysis_results),
                        "line",
                        "yearly_trends.png",
                    )
                    visualizations["trend_chart"] = line_chart
                except Exception as e:
                    print(f"⚠️  Erro ao gerar gráfico de tendências: {e}")

            self.state.visualizations = visualizations
            
            if self.db and self.search_query_id:
                try:
                    self.db.insert_search_log(self.search_query_id, f"{len(visualizations)} visualizações geradas.")
                except Exception as e:
                    print(f"⚠️  Erro ao registrar log: {e}")

            print(f"✅ Visualizações geradas: {len(visualizations)} gráficos")
            return f"Visualizações prontas: {list(visualizations.keys())}"
            
        except Exception as e:
            error_msg = f"Erro nas visualizações: {str(e)}"
            print(f"❌ {error_msg}")
            if self.db and self.search_query_id:
                try:
                    self.db.insert_search_log(self.search_query_id, error_msg)
                except:
                    pass
            return error_msg

    def _generate_insights_from_analysis(self) -> str:
        """Gera insights baseados na análise."""
        insights = []
        
        try:
            if "count_by_category" in self.state.analysis_results:
                categories = self.state.analysis_results["count_by_category"]
                if categories:
                    total = sum(categories.values())
                    most_common = max(categories, key=categories.get)
                    insights.append(
                        f"A categoria mais comum é '{most_common}' com {categories[most_common]} registros"
                        f" ({categories[most_common] / total * 100:.1f}% do total)."
                    )
                    
            if "count_by_year" in self.state.analysis_results:
                years = self.state.analysis_results["count_by_year"]
                if years and len(years) > 1:
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
        except Exception as e:
            print(f"⚠️  Erro ao gerar insights: {e}")
            
        return " ".join(insights) if insights else "Análise concluída com dados básicos."

    def get_final_report(self) -> Dict[str, Any]:
        """Gera relatório final."""
        # Atualizar status no banco
        if self.db and self.search_query_id:
            try:
                self.db.update_search_query_status(self.search_query_id, "completed")
                self.db.insert_search_log(self.search_query_id, "Busca marcada como concluída.")
            except Exception as e:
                print(f"⚠️  Erro ao atualizar status: {e}")

        return {
            "flow_id": self.state.flow_id,
            "search_criteria": self.state.search_criteria,
            "data_collected": len(self.state.raw_data),
            "classified_data": self.state.classified_data, # <-- ADICIONADO: A lista de dados
            "analysis_results": self.state.analysis_results,
            "insights": self.state.insights,
            "visualizations": self.state.visualizations,
            "status": "completed",
        }


# GERENCIADOR CORRIGIDO
class IPFlowManager:
    """Gerenciador para múltiplos fluxos de propriedade intelectual."""
    
    def __init__(self):
        self.active_flows = {}
    
    def create_flow(self, flow_id: str, search_criteria: str) -> PropriedadeIntelectualFlow:
        """
        Cria um novo fluxo.
        ✅ SUPORTA AMBAS AS FORMAS: com e sem argumentos
        """
        try:
            # Tentar criar sem argumentos (modo correto CrewAI)
            flow = PropriedadeIntelectualFlow()
            flow.setup_flow(search_criteria)
        except Exception as e:
            print(f"⚠️  Modo sem argumentos falhou: {e}")
            try:
                # Fallback: usar o __init__ modificado que aceita argumentos
                flow = PropriedadeIntelectualFlow(search_criteria)
            except Exception as e2:
                print(f"❌ Ambos os modos falharam: {e2}")
                raise e2
        
        self.active_flows[flow_id] = flow
        return flow
    
    def get_flow(self, flow_id: str) -> Optional[PropriedadeIntelectualFlow]:
        """Retorna um fluxo específico."""
        return self.active_flows.get(flow_id)
    
    def execute_flow(self, flow_id: str) -> Dict[str, Any]:
        """Executa um fluxo completo."""
        flow = self.get_flow(flow_id)
        if not flow:
            return {"error": "Fluxo não encontrado"}

        try:
            result = flow.kickoff()
            return flow.get_final_report()
        except Exception as e:
            print(f"❌ Erro na execução do fluxo: {e}")
            return {"error": f"Erro na execução do fluxo: {str(e)}"}
    
    def list_flows(self) -> List[str]:
        """Lista todos os fluxos ativos."""
        return list(self.active_flows.keys())


# CLASSE DE SERVIÇO CORRIGIDA
class IPAnalysisService:
    """Serviço principal de análise de PI."""
    
    def __init__(self, category_rules_file: str = "data/category_rules.json"):
        """
        Inicializa o serviço de análise de PI.
        
        Args:
            category_rules_file: Caminho para o arquivo de regras de categorização
        """
        # Inicializar o gerenciador de fluxos
        self.flow_manager = IPFlowManager()
        
        # Carregar regras de categorização
        self.category_rules_file = category_rules_file
        self.category_rules = self._load_category_rules()
        
        # Contador para IDs únicos de fluxo
        self._flow_counter = 0

    def _load_category_rules(self) -> Dict[str, Any]:
        """Carrega regras de categorização."""
        try:
            with open(self.category_rules_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"⚠️  Arquivo de regras não encontrado: {self.category_rules_file}")
            return {}
        except Exception as e:
            print(f"⚠️  Erro ao carregar regras: {e}")
            return {}

    def start_analysis(self, search_criteria: str) -> str:
        """Inicia uma nova análise."""
        self._flow_counter += 1
        flow_id = f"flow_{self._flow_counter:03d}"
        
        try:
            flow = self.flow_manager.create_flow(flow_id, search_criteria)
            print(f"✅ Fluxo {flow_id} criado com sucesso")
            return flow_id
        except Exception as e:
            print(f"❌ Erro ao criar fluxo: {e}")
            return f"error_{flow_id}"

    def execute_analysis(self, flow_id: str) -> Dict[str, Any]:
        """Executa uma análise completa."""
        return self.flow_manager.execute_flow(flow_id)

    def get_flow_status(self, flow_id: str) -> Dict[str, Any]:
        """Obtém status de um fluxo."""
        flow = self.flow_manager.get_flow(flow_id)
        if not flow:
            return {"error": "Fluxo não encontrado"}
        
        return {
            "flow_id": flow_id,
            "search_criteria": flow.state.search_criteria,
            "raw_data_count": len(flow.state.raw_data),
            "classified_data_count": len(flow.state.classified_data),
            "has_analysis": bool(flow.state.analysis_results),
            "has_visualizations": bool(flow.state.visualizations)
        }