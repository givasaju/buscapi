import sys
import os
import json
import uuid
from datetime import datetime

# Garante que a raiz do projeto esteja no sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tools.custom_tools import IPDataCollectorTool, NLPClassificationTool, DataAnalysisTool, VisualizationTool
from database.persist_dados import BuscapiDB


def main():
    db = BuscapiDB()
    try:
        criteria = f"smoke e2e {uuid.uuid4().hex[:8]}"
        search_query_id = db.insert_search_query(criteria)
        print(f"Inserted search_query id={search_query_id} criteria={criteria}")

        # 1) Coleta
        task_input = json.dumps({
            "query": "machine learning patent",
            "search_query_id": search_query_id
        })
        collector = IPDataCollectorTool()
        collected_str = collector._run(task_input)
        print("Collected:", collected_str[:200])
        collected_file = f"e2e_collected_{search_query_id}.json"
        with open(collected_file, 'w', encoding='utf-8') as f:
            f.write(collected_str)
        print(f"Collected saved to {collected_file}")

        # 2) Classificação
        classifier = NLPClassificationTool()
        classified_str = classifier._run(collected_str)
        print("Classified (preview):", classified_str[:200])
        classified_file = f"e2e_classified_{search_query_id}.json"
        with open(classified_file, 'w', encoding='utf-8') as f:
            f.write(classified_str)
        print(f"Classified saved to {classified_file}")

        # 3) Análise
        analyzer = DataAnalysisTool()
        analysis_str = analyzer._run(classified_str)
        print("Analysis:", analysis_str)
        analysis_file = f"e2e_analysis_{search_query_id}.json"
        with open(analysis_file, 'w', encoding='utf-8') as f:
            f.write(analysis_str)
        print(f"Analysis saved to {analysis_file}")

        # 4) Visualização (gerar gráfico bar por categoria)
        visualizer = VisualizationTool()
        viz_json = visualizer._run(analysis_str, plot_type='bar')
        # Se retornar erro, salva como JSON; se retornar figura plotly JSON, também salva
        viz_file = f"e2e_viz_{search_query_id}.json"
        with open(viz_file, 'w', encoding='utf-8') as f:
            f.write(viz_json)
        print(f"Visualization saved to {viz_file}")

        # Resumo das tabelas
        try:
            structured_count = len(db.get_structured_results_by_query_id(search_query_id))
        except Exception:
            structured_count = 'n/a'
        print(f"Summary: structured_count={structured_count}")

    except Exception as e:
        print("E2E error:", e)
    finally:
        db.close()

if __name__ == '__main__':
    main()
