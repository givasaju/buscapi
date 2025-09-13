#!/usr/bin/env python3

"""
Sistema de Análise de Propriedade Intelectual com CrewAI
Autor: Givasaju
Versão: 1.0.0
"""

import json
import sys
import os
import certifi
from collections import Counter
from dotenv import load_dotenv
from typing import Dict, Any
# IMPORTS customizados e suas dependências
from flows.ip_flow import IPFlowManager
from agents.ip_agents import IPAgents
from tasks.ip_tasks import IPTaskManager
# Adicionar função para carregar regras para possíveis futuras integrações
from tools.custom_tools import load_category_rules

load_dotenv()
# Carrega as variáveis de ambiente do arquivo .env

# Configurar certificados SSL
os.environ['SSL_CERT_FILE'] = certifi.where()
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
os.environ['CURL_CA_BUNDLE'] = certifi.where()

class IPAnalysisSystem:
    """Sistema principal para análise de propriedade intelectual."""

    def __init__(self, category_rules_file: str = "category_rules.json"):
        """Inicializa o sistema com gerenciadores de fluxo, agentes e tarefas."""
        self.flow_manager = IPFlowManager()
        self.agents = IPAgents()
        self.task_manager = IPTaskManager(self.agents)
        self.category_rules_file = category_rules_file
        self.category_rules = load_category_rules(self.category_rules_file)

    def run_analysis(self, search_criteria: str, flow_id: str = None) -> Dict[str, Any]:
        """Executa uma análise completa de propriedade intelectual."""
        print(f"Executando análise para o critério: {search_criteria}")
        if not flow_id:
            flow_id = f"ip_flow_{len(self.flow_manager.active_flows) + 1}"

        print(f"\n🔍 Iniciando análise de propriedade intelectual")
        print(f"📋 Critérios: {search_criteria}")
        print(f"🆔 ID do fluxo: {flow_id}")
        print("=" * 60)

        # Cria e executa o fluxo
        flow = self.flow_manager.create_flow(flow_id, search_criteria)
        result = self.flow_manager.execute_flow(flow_id)

        # Extrai categorias classificadas e gera resumo
        try:
            classified_json = result.get('classified_data', '[]')
            classified_data = json.loads(classified_json)
            categories = [item.get('category', 'Outros') for item in classified_data if isinstance(item, dict)]
            category_counts = dict(Counter(categories))
            result['category_summary'] = category_counts
        except Exception as e:
            result['category_summary_error'] = str(e)

        return result

    def _display_results(self, result: Dict[str, Any]):
        """Exibe os resultados da análise."""
        print("\n" + "=" * 60)
        print("📊 RESULTADOS DA ANÁLISE")
        print("=" * 60)
        if "error" in result:
            print(f"❌ Erro: {result['error']}")
            return

        print(f"🆔 ID do Fluxo: {result.get('flow_id', 'N/A')}")
        print(f"📋 Critérios: {result.get('search_criteria', 'N/A')}")
        print(f"📊 Dados Coletados: {result.get('data_collected', 0)}")
        print(f"🏷️ Dados Classificados: {result.get('data_classified', 0)}")

        # Exibir resumo por categorias
        if result.get('category_summary'):
            print("\n🏷️ Resumo por Categoria:")
            for cat, count in result['category_summary'].items():
                print(f" - {cat}: {count}")

        if result.get('insights'):
            print(f"\n💡 Insights:")
            print(f" {result['insights']}")

        if result.get('analysis_results'):
            print(f"\n📈 Resultados da Análise:")
            for key, value in result['analysis_results'].items():
                print(f" {key}: {value}")

        if result.get('visualizations'):
            print(f"\n📊 Visualizações Geradas:")
            for viz_name, viz_path in result['visualizations'].items():
                print(f" {viz_name}: {viz_path}")

        print("=" * 60)

    def run_batch_mode(self, config_file: str):
        """Executa o sistema em modo batch usando arquivo de configuração."""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)

            results = []
            for i, search_config in enumerate(config.get('searches', [])):
                flow_id = f"batch_flow_{i+1}"
                search_criteria = search_config.get('criteria', '')
                print(f"\n🔄 Processando busca {i+1}/{len(config['searches'])}")
                result = self.run_analysis(search_criteria, flow_id)
                results.append(result)

            output_file = config.get('output_file', 'batch_results.json')
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)

            print(f"\n✅ Resultados salvos em: {output_file}")

        except FileNotFoundError:
            print(f"❌ Arquivo de configuração não encontrado: {config_file}")
        except json.JSONDecodeError:
            print(f"❌ Erro ao ler arquivo JSON: {config_file}")
        except Exception as e:
            print(f"❌ Erro no modo batch: {str(e)}")

    def run_interactive_mode(self):
        """Executa o sistema em modo interativo."""
        print("\n🤖 Sistema de Análise de Propriedade Intelectual")
        print("=" * 50)
        print("Digite 'quit' para sair")

        while True:
            try:
                search_criteria = input("\n📝 Digite os critérios de busca: ").strip()
                if search_criteria.lower() in ['quit', 'exit', 'sair']:
                    print("👋 Encerrando sistema...")
                    break
                if not search_criteria:
                    print("⚠️ Por favor, digite critérios de busca válidos.")
                    continue

                result = self.run_analysis(search_criteria) # Executa análise com critérios fornecidos
                self._display_results(result)

            except KeyboardInterrupt:
                print("\n\n👋 Sistema interrompido pelo usuário.")
                break
            except Exception as e:
                print(f"\n❌ Erro inesperado: {str(e)}")

def main():
    system = IPAnalysisSystem()
    if len(sys.argv) > 1:
        if sys.argv[1] == '--batch' and len(sys.argv) > 2:
            system.run_batch_mode(sys.argv[2])
        elif sys.argv[1] == '--single' and len(sys.argv) > 2:
            search_criteria = ' '.join(sys.argv[2:])
            result = system.run_analysis(search_criteria)
            system._display_results(result)
        else:
            print("Uso:")
            print(" python main.py           # Modo interativo")
            print(" python main.py --single \"<critério>\"  # Busca única")
            print(" python main.py --batch <arquivo_config.json>  # Modo batch")
    else:
        system.run_interactive_mode()

if __name__ == "__main__":
    main()
