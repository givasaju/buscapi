import sys
import os
import json
import uuid

# Garante que a raiz do projeto (pasta acima de tests) esteja no sys.path para imports relativos
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tools.custom_tools import IPDataCollectorTool
from database.persist_dados import BuscapiDB


def main():
    db = BuscapiDB()
    try:
        criteria = f"smoke test coleta {uuid.uuid4().hex[:8]}"
        search_query_id = db.insert_search_query(criteria)
        print(f"Inserted search_query id={search_query_id} criteria={criteria}")

        task_input = json.dumps({
            "query": "machine learning patent",
            "search_query_id": search_query_id
        })

        collector = IPDataCollectorTool()
        print("Running IPDataCollectorTool...")
        result = collector._run(task_input)

        print("Collector returned (first 2000 chars):")
        print(result[:2000])

        out_filename = f"smoke_result_{search_query_id}.json"
        with open(out_filename, "w", encoding="utf-8") as f:
            f.write(result)
        print(f"Result saved to {out_filename}")

        # Tenta buscar resultados estruturados (pode estar vazio)
        try:
            structured = db.get_structured_results_by_query_id(search_query_id)
            print(f"Structured results count: {len(structured)}")
        except Exception as e:
            print("Não foi possível recuperar structured results:", e)

    except Exception as e:
        print("Erro durante smoke test:", e)
    finally:
        db.close()


if __name__ == "__main__":
    main()
