from crewai import Agent
import os
import json
from typing import Optional
from tools.custom_tools import (
    IPDataCollectorTool,
    NLPClassificationTool,
    DataAnalysisTool,
    VisualizationTool,
    LLMTool,
    PDFReportTool,
)


class IPAgentFactory:
    """Factory para criar agentes de propriedade intelectual."""

    @staticmethod
    def create_data_collector_agent() -> Agent:
        """Cria o agente coletor de dados de propriedade intelectual."""
        return Agent(
            role='Coletor de Dados de Propriedade Intelectual',
            goal='Coletar informações abrangentes sobre ativos de propriedade intelectual com base em critérios fornecidos.',
            backstory='''Você é um especialista em vasculhar vastas quantidades de dados online
                        para encontrar informações relevantes sobre patentes, modelo de utilidade, desenho industrial, processos, marcas, cultivar e indicação geográfica.
                        Sua experiência inclui o uso de múltiplas bases de dados e APIs especializadas
                        em propriedade intelectual.''',
            verbose=True,
            allow_delegation=False,
            tools=[IPDataCollectorTool()],
            max_iter=5,
            memory=True,
        )

    @staticmethod
    def create_data_classifier_agent() -> Agent:
        """Cria o agente classificador e organizador de dados."""
        return Agent(
            role='Classificador e Organizador de Dados de Propriedade Intelectual',
            goal='Estruturar e categorizar dados brutos de PI para facilitar a análise posterior.',
            backstory='''Você é um especialista em transformar dados não estruturados em
                        informações organizadas e acessíveis, aplicando técnicas avançadas de
                        processamento de linguagem natural e classificação de dados.''',
            verbose=True,
            allow_delegation=False,
            tools=[NLPClassificationTool()],
            max_iter=5,
            memory=True,
        )

    @staticmethod
    def create_insight_coordinator_agent() -> Agent:
        """Cria o agente coordenador de insights."""
        return Agent(
            role='Coordenador de Insights de Propriedade Intelectual',
            goal='Analisar dados de PI, extrair insights acionáveis e apresentá-los visualmente através de gráficos e dashboards.',
            backstory='''Você é um analista de dados experiente com paixão por transformar
                        números complexos em narrativas visuais claras e impactantes. Sua
                        especialidade é identificar tendências e padrões em dados de propriedade
                        intelectual e comunicá-los de forma eficaz.''',
            verbose=True,
            allow_delegation=True,
            tools=[DataAnalysisTool(), VisualizationTool(), LLMTool()],
            max_iter=7,
            memory=True,
        )

    @staticmethod
    def create_data_relat_agent() -> Agent:
        """Cria o agente especialista na escrita de relatórios formais empresariais."""
        # Sempre expor a ferramenta adaptadora `PDFReportTool` (subclasse de BaseTool).
        # Não devemos instanciar `PDFGenerator` diretamente aqui porque ele não herda de BaseTool
        # e causa erro de validação ao construir o Agent (pydantic espera BaseTool/dict).
        tools_list = [PDFReportTool()]

        return Agent(
            role='Gerar relatórios estruturados de informações sobre artigos científicos e ativos de Propriedade Intelectual',
            goal='Escrever relatórios claros e concisos sobre das informações obtidas de PI para facilitar a análise posterior.',
            backstory='''Você é um especialista na escrita de relatórios estruturados e detalhados sobre artigos de tecnologia
                        e de propriedade intelectual. Sua experiência inclui a síntese de informações complexas em formatos
                        acessíveis aplicando ferramentas de geração de relatórios em formatos pdf, MD e HTML.''',
            verbose=True,
            allow_delegation=False,
            tools=tools_list,
            max_iter=3,
            memory=True,
        )


class IPAgents:
    """Classe para gerenciar todos os agentes de propriedade intelectual."""

    def __init__(self):
        self.data_collector = IPAgentFactory.create_data_collector_agent()
        self.data_classifier = IPAgentFactory.create_data_classifier_agent()
        self.insight_coordinator = IPAgentFactory.create_insight_coordinator_agent()
        # Agente responsável por gerar relatórios/PDFs (pode usar PDFGenerator ou PDFReportTool)
        self.data_relat = IPAgentFactory.create_data_relat_agent()

    def generate_insights_via_llm(self, analysis: dict = None, classified: list = None, model: Optional[str] = None) -> Optional[str]:
        """Invoca a LLMTool do agente coordenador sob demanda.

        Por padrão (quando `model` for None) a ferramenta LLM usará o valor definido
        na variável de ambiente `LLM_MODEL`. Se `model` for fornecido, ele é aplicado
        temporariamente na variável de ambiente para esta invocação (override).

        Retorna a string de 'insights' produzida pela LLM ou None se não estiver disponível.
        """
        analysis = analysis or {}
        classified = classified or []

        coord = getattr(self, "insight_coordinator", None)
        if not coord:
            return None

        # Localiza uma ferramenta do tipo LLMTool no agente coordenador
        llm_tool = None
        for t in getattr(coord, "tools", []) or []:
            if type(t).__name__ == "LLMTool" or hasattr(t, "_call_openai_chat"):
                llm_tool = t
                break

        if not llm_tool:
            return None

        payload = {"analysis": analysis, "classified": classified}
        # Se um override de modelo foi passado (pode ser string vazia), aplicamos temporariamente
        # na variável de ambiente; caso contrário, deixamos a variável de ambiente atual.
        prev_model = None
        try:
            if model is not None:
                prev_model = os.getenv('LLM_MODEL')
                # Se o usuário passou uma string vazia explicitamente, definimos-a tal como foi passada.
                os.environ['LLM_MODEL'] = model

            # Decide qual modelo será efetivamente usado para esta invocação
            effective_model = model if model is not None else os.getenv('LLM_MODEL')

            out = llm_tool._run(json.dumps(payload, ensure_ascii=False))
            # Registra o modelo efetivamente usado no objeto IPAgents para que outras
            # partes do sistema (ex: geração de relatório) possam consultá-lo.
            try:
                self.last_used_llm_model = effective_model
            except Exception:
                # Silencioso: não é crítico se não pudermos definir o atributo
                pass
            try:
                parsed = json.loads(out)
                return parsed.get("insights") if isinstance(parsed, dict) else out
            except Exception:
                return out
        except Exception:
            return None

        finally:
            # Restaura a variável de ambiente anterior
            if prev_model is None:
                if 'LLM_MODEL' in os.environ:
                    del os.environ['LLM_MODEL']
            else:
                os.environ['LLM_MODEL'] = prev_model

    def get_all_agents(self) -> list:
        """Retorna uma lista com todos os agentes."""
        return [
            self.data_collector,
            self.data_classifier,
            self.insight_coordinator,
            self.data_relat,
        ]

    def get_agent_by_role(self, role: str) -> Agent:
        """Retorna um agente específico baseado no seu papel."""
        agents_map = {
            "collector": self.data_collector,
            "classifier": self.data_classifier,
            "coordinator": self.insight_coordinator,
            "relat": self.data_relat,
        }
        print(agents_map)
        return agents_map.get(role.lower())

