# Definição de Modelo de Dados para Resultados

from typing import Optional
from pydantic import BaseModel
from datetime import date, datetime

class PatentRecord(BaseModel):
    source: str  # Único campo obrigatório
    db_raw_id: Optional[int] = None
    applicationNumber: Optional[str] = None  # ✅ Corrigido: adicionado = None
    title: Optional[str] = None              # ✅ Corrigido: adicionado = None  
    filingDate: Optional[date] = None        # ✅ Corrigido: adicionado = None
    applicantName: Optional[str] = None      # ✅ Corrigido: adicionado = None
    abstract: Optional[str] = None           # ✅ Corrigido: adicionado = None
    category: Optional[str] = "Outros"       # ✅ Já estava correto
    summary: Optional[str] = None            # ✅ Já estava correto

    @classmethod
    def from_dict(cls, data: dict):
        if data.get('filingDate') and not isinstance(data.get('filingDate'), date):
            try:
                data['filingDate'] = datetime.strptime(data['filingDate'], "%Y-%m-%d").date()
            except Exception:
                pass
        return cls(**data)