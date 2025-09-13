import json
import time
from pathlib import Path

from flows.ip_flow import PropriedadeIntelectualFlow, PropriedadeIntelectualState


def main():
    # Cria um estado mínimo e evita operações no DB definindo flow.db = None
    state = PropriedadeIntelectualState(
        search_query_id=999999,
        search_criteria="smoke test",
        raw_data_json=json.dumps([]),
        classified_data_json=json.dumps([]),
        analysis_results_json=json.dumps({"insights": "smoke_insight"}),
        visualizations_json=json.dumps({})
    )

    flow = PropriedadeIntelectualFlow()
    # Evita operações de DB durante o smoke test
    try:
        flow.db.close()
    except Exception:
        pass
    flow.db = None

    # Executa kickoff com estado inicial — kickoff internamente chama _generate_final_report
    try:
        final_report = flow.kickoff(state=state)
    except Exception as e:
        # kickoff pode tentar executar o fluxo; queremos pelo menos a geração do relatório final.
        print(f'kickoff raised: {e}')
        # Tenta chamar _generate_final_report diretamente se possível
        try:
            final_report = flow._generate_final_report()
        except Exception as e2:
            print(f'Falha ao gerar relatório via fallback: {e2}')
            return

    report = final_report
    print("FINAL_REPORT:")
    print(json.dumps(report, ensure_ascii=False, indent=2))

    pdf_job = report.get('pdf_job')
    if not pdf_job:
        print('Nenhum pdf_job retornado pelo relatório final.')
        return

    job_id = pdf_job.get('job_id')
    path = Path('static/pdf_jobs') / f"{job_id}.json"

    # Aguarda por até 10 segundos o job ser processado
    waited = 0
    while waited < 10:
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                meta = json.load(f)
            print('\nJOB_META:')
            print(json.dumps(meta, ensure_ascii=False, indent=2))
            return
        time.sleep(1)
        waited += 1

    print(f'Arquivo de meta do job nao encontrado apos {waited} segundos: {path}')


if __name__ == '__main__':
    main()
