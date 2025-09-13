import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from uuid import uuid4
from pathlib import Path
from typing import Dict, Any

import plotly.io as pio
import plotly.graph_objects as go

from tools.custom_tools import PDFReportTool
from database.persist_dados import BuscapiDB


# Diretório para armazenar metadados dos jobs
JOBS_DIR = Path("static/pdf_jobs")
JOBS_DIR.mkdir(parents=True, exist_ok=True)

# Executor global simples
_executor = ThreadPoolExecutor(max_workers=2)

# Estado em memória (pode ser usado para consultas rápidas)
_jobs: Dict[str, Dict[str, Any]] = {}


def _persist_job_meta(job_id: str, meta: Dict[str, Any]):
    path = JOBS_DIR / f"{job_id}.json"
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2, default=str)


def _run_pdf_job(job_id: str, results: Dict[str, Any], output_path: str, extra_meta: Dict[str, Any] = None):
    meta = _jobs.get(job_id, {})
    meta.update({"status": "processing", "started_at": datetime.utcnow().isoformat()})
    _jobs[job_id] = meta
    _persist_job_meta(job_id, meta)

    try:
        # Preparar visualizações: se forem representações Plotly (JSON/dict/list),
        # converte para imagens PNG e atualiza results['visualizations'] para paths.
        try:
            viz = results.get('visualizations') if isinstance(results, dict) else None
            if isinstance(viz, dict):
                temp_dir = Path('static') / 'temp_images'
                temp_dir.mkdir(parents=True, exist_ok=True)
                img_paths = {}
                for name, v in viz.items():
                    fig = None
                    try:
                        # string JSON do Plotly
                        if isinstance(v, str):
                            try:
                                fig = pio.from_json(v)
                            except Exception:
                                parsed = json.loads(v)
                                if isinstance(parsed, dict):
                                    fig = go.Figure(parsed)
                                elif isinstance(parsed, list):
                                    fig = go.Figure(data=parsed)

                        elif isinstance(v, dict):
                            try:
                                fig = go.Figure(v)
                            except Exception:
                                fig = go.Figure(data=v.get('data', []), layout=v.get('layout', {}))

                        elif isinstance(v, list):
                            fig = go.Figure(data=v)

                        if fig is not None:
                            img_path = str(temp_dir / f"{name}_{job_id}.png")
                            try:
                                fig.write_image(img_path, scale=2)
                                img_paths[name] = img_path
                            except Exception as e:
                                # falha ao escrever imagem: registra e pula
                                print(f"Aviso: falha ao escrever imagem da visualização {name}: {e}")
                    except Exception as _:
                        continue

                if img_paths:
                    results = dict(results)
                    results['visualizations'] = img_paths
        except Exception as vv:
            print(f"Aviso: não foi possível converter visualizações para imagens: {vv}")

        tool = PDFReportTool()
        payload = {"results": results, "output_path": output_path}
        resp = tool._run(json.dumps(payload, ensure_ascii=False))
        try:
            parsed = json.loads(resp)
        except Exception:
            parsed = {"error": "invalid_response", "raw": resp}

        if parsed.get('path'):
            meta.update({"status": "completed", "output_path": parsed['path'], "completed_at": datetime.utcnow().isoformat()})
            # Tenta registrar no DB que o PDF foi gerado
            try:
                sqid = extra_meta.get('search_query_id') if extra_meta else None
                if sqid:
                    db = BuscapiDB()
                    db.insert_search_log(sqid, f"✅ Relatório PDF gerado com sucesso: {parsed['path']}")
                    db.close()
            except Exception:
                # Não falhar o job se inserção no DB der errado
                pass
        else:
            meta.update({"status": "failed", "error": parsed.get('error') or parsed, "completed_at": datetime.utcnow().isoformat()})
            try:
                sqid = extra_meta.get('search_query_id') if extra_meta else None
                if sqid:
                    db = BuscapiDB()
                    db.insert_search_log(sqid, f"❌ Falha ao gerar PDF: {parsed.get('error')}")
                    db.close()
            except Exception:
                pass

    except Exception as e:
        meta.update({"status": "failed", "error": str(e), "completed_at": datetime.utcnow().isoformat()})
    finally:
        if extra_meta:
            meta.update(extra_meta)
        _jobs[job_id] = meta
        _persist_job_meta(job_id, meta)


def enqueue_pdf_job(results: Dict[str, Any], output_path: str = None, search_query_id: int = None, title_prefix: str = "relatorio_buscapi") -> Dict[str, Any]:
    """Enfileira um job de geração de PDF e retorna metadados iniciais do job.

    Retorna: {job_id, status, output_path}
    """
    job_id = str(uuid4())
    ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    if output_path is None:
        filename = f"{title_prefix}_{ts}.pdf"
        output_path = str(Path('static') / filename)

    # Se o dicionário 'results' conter informação do modelo LLM usado, inclua-a
    llm_model = None
    try:
        if isinstance(results, dict):
            llm_model = results.get('llm_model')
    except Exception:
        llm_model = None

    meta = {
        "job_id": job_id,
        "status": "pending",
        "output_path": output_path,
        "queued_at": datetime.utcnow().isoformat(),
        "search_query_id": search_query_id,
        "llm_model": llm_model,
    }

    _jobs[job_id] = meta
    _persist_job_meta(job_id, meta)

    # Submit to executor, incluindo meta extra (ex: search_query_id e llm_model)
    extra = {"search_query_id": search_query_id, "llm_model": llm_model}
    _executor.submit(_run_pdf_job, job_id, results, output_path, extra)

    return meta


def get_job_meta(job_id: str) -> Dict[str, Any]:
    if job_id in _jobs:
        return _jobs[job_id]
    path = JOBS_DIR / f"{job_id}.json"
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"error": "not_found"}
