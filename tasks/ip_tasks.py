from crewai import Task
from agents.ip_agents import IPAgents
from typing import Dict, Any
import json
import time

class IPTaskFactory:
    """Factory para criar tarefas de propriedade intelectual."""
    
    def __init__(self, agents: IPAgents):
        self.agents = agents
    
    def create_data_collection_task(self) -> Task:
        """
        Cria uma tarefa de coleta de dados que aceita um input dinâmico via placeholder.
        O input esperado é uma string JSON contendo 'query' e 'search_query_id'.
        """
        return Task(
            description='''Coletar dados de propriedade intelectual usando a ferramenta IP Data Collector Tool.
                           A entrada para a ferramenta deve ser a string JSON fornecida em '{task_input}'.
                           Passe o conteúdo de '{task_input}' diretamente para a ferramenta sem modificação.''',
            agent=self.agents.data_collector,
            expected_output='''Uma lista de resultados em formato JSON. Cada item na lista deve ser um dicionário
                               contendo os dados brutos coletados e uma chave 'db_raw_id' adicionada pela ferramenta
                               após a persistência no banco de dados.'''
        )
    
    def create_data_classification_task(self, raw_data_context: str = "") -> Task:
        """Cria uma tarefa de classificação de dados."""
        return Task(
            description=f'''Classificar e organizar os dados brutos de propriedade intelectual coletados.
                           Extrair informações chave como: tipo de PI (patente, marca, direito autoral),
                           categoria tecnológica, status legal, e outras características relevantes.
                           {raw_data_context}''',
            agent=self.agents.data_classifier,
            expected_output='''Dados de propriedade intelectual estruturados e classificados em formato JSON,
                              com campos padronizados e categorias bem definidas.'''
        )
    
    def create_analysis_task(self) -> Task:
        """Cria uma tarefa de análise de dados."""
        return Task(
            description='''Sua missão é analisar os dados classificados de propriedade intelectual fornecidos no contexto.
                           Primeiro, utilize a 'Data Analysis Tool' para extrair estatísticas numéricas, como contagens por categoria e por ano.
                           Depois, com base nesses números, interprete os resultados e escreva um parágrafo conciso com os 'insights' mais importantes.
                           Foque em identificar a categoria mais proeminente e a tendência temporal (crescente, decrescente ou estável).''',
            agent=self.agents.insight_coordinator,
            expected_output='''Um relatório em formato JSON. O JSON deve conter duas chaves principais:
                               1. 'statistics': Um dicionário com os dados numéricos brutos da ferramenta de análise (ex: 'count_by_category', 'count_by_year').
                               2. 'insights': Uma string de texto contendo o resumo interpretativo dos principais achados.
                               Exemplo: {"statistics": {"count_by_category": {"Patente": 10}}, "insights": "A categoria mais comum é Patente..."}'''
        )
    
    def create_visualization_task(self, visualization_type: str = "dashboard completo") -> Task:
        """Cria uma tarefa de visualização de dados."""
        return Task(
            description=f'''Gerar {visualization_type} baseado nos insights e análises realizadas.
                           Criar gráficos informativos, dashboards interativos e visualizações que comuniquem
                           claramente os principais achados sobre propriedade intelectual.''',
            agent=self.agents.insight_coordinator,
            expected_output='''Conjunto de visualizações geradas (gráficos, dashboards) com caminhos dos arquivos
                              e descrições das principais descobertas visuais.'''
        )
    def create_relat_task(self, relat_type: str = "dashboard completo") -> Task:
        """Cria uma tarefa de visualização de dados."""
        return Task(
            description=f'''Gerar um {relat_type} baseado nos insights e análises realizadas.
                           Criar relatórios informativos com inormações gerais explicando com
                           linguagem técnica os principais achados sobre propriedade intelectual.''',
            agent=self.agents.insight_coordinator,
            expected_output='''Escrever um Relatório seguindo padrões empresariais contendo informações das
                               tecnologias pesquisadas com os insights no fluxo das peqsuisas.'''
        )
        
class IPTaskManager:
    """Gerenciador de tarefas para o fluxo de propriedade intelectual."""
    
    def __init__(self, agents: IPAgents):
        self.agents = agents
        self.task_factory = IPTaskFactory(agents)
        self.tasks = {}
    
    def create_standard_workflow_tasks(self) -> Dict[str, Task]:
        """Cria o conjunto padrão de tarefas para o workflow."""
        self.tasks = {
            'collection': self.task_factory.create_data_collection_task(),
            'classification': self.task_factory.create_data_classification_task(),
            'analysis': self.task_factory.create_analysis_task(),
            'visualization': self.task_factory.create_visualization_task()
        }
        return self.tasks
    
    def create_custom_workflow_tasks(self, task_configs: Dict[str, Dict[str, Any]]) -> Dict[str, Task]:
        """Cria tarefas customizadas baseadas em configurações específicas."""
        custom_tasks = {}
        
        for task_name, config in task_configs.items():
            if task_name == 'collection':
                custom_tasks[task_name] = self.task_factory.create_data_collection_task(
                    config.get('search_criteria', 'propriedade intelectual geral')
                )
            elif task_name == 'classification':
                custom_tasks[task_name] = self.task_factory.create_data_classification_task(
                    config.get('context', '')
                )
            elif task_name == 'analysis':
                custom_tasks[task_name] = self.task_factory.create_analysis_task(
                    config.get('focus', 'tendências gerais')
                )
            elif task_name == 'visualization':
                custom_tasks[task_name] = self.task_factory.create_visualization_task(
                    config.get('type', 'dashboard completo')
                )
            elif task_name == 'relatorio':
                custom_tasks[task_name] = self.task_factory.create_relat_task(
                    config.get('type', 'dashboard completo')
                )    
        
        self.tasks.update(custom_tasks)
        return custom_tasks
    
    def get_task(self, task_name: str) -> Task:
        """Retorna uma tarefa específica."""
        return self.tasks.get(task_name)
    
    def get_all_tasks(self) -> Dict[str, Task]:
        """Retorna todas as tarefas criadas."""
        return self.tasks

    # Wrappers convenientes para compatibilidade com o fluxo
    def create_data_collection_task(self) -> Task:
        return self.task_factory.create_data_collection_task()

    def create_data_classification_task(self, raw_data_context: str = "") -> Task:
        return self.task_factory.create_data_classification_task(raw_data_context)

    def create_analysis_task(self) -> Task:
        return self.task_factory.create_analysis_task()

    def create_visualization_task(self, visualization_type: str = "dashboard completo") -> Task:
        return self.task_factory.create_visualization_task(visualization_type)

    def execute_task(self, task: Task, input_str: str, preferred_tool_cls: type = None, preferred_tool_name: str = None, retries: int = 1) -> str:
        """Executa a Task escolhendo a ferramenta apropriada no Agent e normaliza a saída.

        - Seleciona a ferramenta por classe (`preferred_tool_cls`) ou por nome (`preferred_tool_name`) quando informado.
        - Faz até `retries` tentativas em caso de exceção.
        - Garante que o retorno seja uma string JSON (serializa listas/dicts quando necessário).
        """
        agent = getattr(task, 'agent', None)
        if not agent:
            raise RuntimeError('Task não possui agent associado')

        tools = getattr(agent, 'tools', []) or []
        chosen = None

        # 1) Procurar por classe
        if preferred_tool_cls:
            for t in tools:
                if isinstance(t, preferred_tool_cls):
                    chosen = t
                    break

        # 2) Procurar por nome
        if not chosen and preferred_tool_name:
            for t in tools:
                name = getattr(t, 'name', None)
                if name and name.lower() == preferred_tool_name.lower():
                    chosen = t
                    break
                if t.__class__.__name__.lower() == preferred_tool_name.lower():
                    chosen = t
                    break

        # 3) Fallback para a primeira ferramenta
        if not chosen and tools:
            chosen = tools[0]

        if not chosen:
            raise RuntimeError('Agent não possui ferramenta executável')

        last_exc = None
        for attempt in range(1, max(1, retries) + 1):
            try:
                out = chosen._run(input_str)
                # Normalizar saída: garantir string JSON
                if isinstance(out, str):
                    return out
                try:
                    return json.dumps(out, ensure_ascii=False)
                except Exception:
                    return str(out)
            except Exception as e:
                last_exc = e
                # pequeno backoff
                time.sleep(0.2)

        raise RuntimeError(f"Falha ao executar a task após {retries} tentativas: {last_exc}")
