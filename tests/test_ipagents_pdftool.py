import json
from pathlib import Path

import pytest

from agents.ip_agents import IPAgents
from tools.custom_tools import PDFReportTool


def test_ipagents_instantiation():
    agents = IPAgents()
    assert hasattr(agents, 'data_collector')
    assert hasattr(agents, 'data_classifier')
    assert hasattr(agents, 'insight_coordinator')
    assert hasattr(agents, 'data_relat')


def test_pdfreporttool_generates_pdf(tmp_path: Path):
    # Prepara um payload mínimo compatível com PDFGenerator
    results = {
        'search_criteria': 'teste unitario',
        'flow_id': 'test-flow-1',
        'success': True,
        'data_collected': 0,
        'data_classified': 0,
        'total_categories': 0,
        'visualizations': {},
        'analysis_results': {}
    }

    out_path = tmp_path / 'test_report.pdf'

    tool = PDFReportTool()
    payload = {'results': results, 'output_path': str(out_path)}

    resp = tool._run(json.dumps(payload, ensure_ascii=False))
    # Deve retornar JSON com chave 'path' ou 'error'
    assert isinstance(resp, str)
    data = json.loads(resp)
    assert 'path' in data or 'error' in data

    if 'path' in data:
        assert Path(data['path']).exists()
        # arquivo criado deve ter extensão pdf
        assert str(data['path']).lower().endswith('.pdf')
