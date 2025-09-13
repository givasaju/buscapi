import json
from tools.custom_tools import NLPClassificationTool
from tools.custom_tools import IPDataCollectorTool

def test_collector_output_contract(monkeypatch):
    # Simula respostas mínimas por fonte
    class DummyTool:
        def __init__(self, payload): self.payload = payload
        def _run(self, q): return json.dumps(self.payload)

    # Monkeypatch das fontes internas
    from tools import custom_tools as ct
    monkeypatch.setattr(ct, "SerperDevTool", lambda: DummyTool({"organic":[{"title":"t1"}]}))
    monkeypatch.setattr(ct, "USPTO_PatentSearchTool", lambda: DummyTool([{"a":1}]))
    monkeypatch.setattr(ct, "EPO_PatentSearchTool", lambda: DummyTool({"x":2}))
    monkeypatch.setattr(ct, "INPI_PatentSearchTool", lambda: DummyTool([{"y":3}]))
    monkeypatch.setattr(ct, "GooglePatentsSearchTool", lambda: DummyTool([{"z":4}]))

    # Monkeypatch da persistência para não bater no BD
    class FakeDB:
        def insert_search_result_raw(self, *args, **kwargs): return 99
        def insert_search_log(self, *a, **k): pass
        def close(self): pass
    monkeypatch.setattr(ct, "BuscapiDB", lambda: FakeDB())

    out = IPDataCollectorTool()._run(json.dumps({"query":"q", "search_query_id":1}))
    items = json.loads(out)
    assert isinstance(items, list) and len(items) >= 5
    assert all("db_raw_id" in it for it in items)
    assert set(it["source"] for it in items) >= {"SERPER","USPTO","EPO","INPI","GOOGLE_P"}

def test_classifier_accepts_flat_items(monkeypatch):
    # Dados já normalizados (como saem do coletor)
    data = [{"source":"USPTO","title":"A","db_raw_id":1},{"source":"EPO","title":"B","db_raw_id":2}]
    out = NLPClassificationTool()._run(json.dumps(data))
    classified = json.loads(out)
    assert isinstance(classified, list)
    assert len(classified) == len(data)
