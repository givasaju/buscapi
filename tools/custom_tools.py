import pandas as pd
import plotly.express as px
import json
import requests
import os
import copy
import time
import re
from bs4 import BeautifulSoup
from crewai.tools import BaseTool
from datetime import datetime
from functools import lru_cache
try:
    import spacy
except Exception:
    spacy = None
from database.persist_dados import BuscapiDB
from typing import ClassVar, Optional, Tuple
from models.patent_record import PatentRecord


from dotenv import load_dotenv

load_dotenv()

# Função utilitária que padroniza a saída para lista intermitente
from typing import Any, List, Optional

def normalize_to_list(data: Optional[Any]) -> List[Any]:
    """
    Garante que o dado retornado será sempre uma lista homogênea,
    mesmo que o dado de entrada seja None, dict, tuple ou lista aninhada.
    """
    if data is None:
        return []
    elif isinstance(data, list):
        # Evita listas aninhadas por engano, retorna lista achatada de primeiro nível
        if len(data) == 1 and isinstance(data[0], list):
            return data[0]
        return data
    elif isinstance(data, tuple):
        return list(data)
    elif isinstance(data, dict):
        return [data]
    else:
        return []
    
# --- Função para carregar regras dinâmicas de categorias ---
def load_category_rules(file_path="category_rules.json"):
    if not os.path.exists(file_path):
        return []
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

category_rules = load_category_rules()

class SerperDevTool(BaseTool):
    name: str = "Serper Dev Tool"
    description: str = "Ferramenta para realizar buscas na web usando a API SerperDev."

    def _run(self, query: str) -> str:
        api_key = os.getenv("serper_api_key")
        if not api_key:
            return "Erro: SERPER_API_KEY não configurada."
        headers = {
            "X-API-KEY": api_key,
            "Content-Type": "application/json"
        }
        url = "https://google.serper.dev/search"
        payload = json.dumps({"q": query})
        try:
            response = requests.request("POST", url, headers=headers, data=payload)
            response.raise_for_status()
            serper_results = json.dumps(response.json())
            return serper_results
        except requests.exceptions.RequestException as e:
            return f"Erro ao chamar SerperDev API: {e}"

class USPTO_PatentSearchTool(BaseTool):
    name: str = "USPTO Patent Search Tool"
    description: str = "Ferramenta para buscar patentes no USPTO Open Data Portal."

    def _run(self, query: str) -> str:
        api_key = os.getenv("USPTO_API_KEY")
        if not api_key:
            return "Erro: USPTO_API_KEY não configurada. Por favor, obtenha uma chave em developer.uspto.gov."
        base_url = "https://api.uspto.gov/api/v1/patent/applications/search"
        params = {
            "_query": query,
            "_size": 20
        }
        headers = {
            "X-API-KEY": api_key,
            "Accept": "application/json"
        }
        try:
            response = requests.get(base_url, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()
            extracted_data = []
            if isinstance(data, dict) and 'patentFileWrapperDataBag' in data:
                for item in data["patentFileWrapperDataBag"]:
                    app_meta = item.get("applicationMetaData", {})
                    extracted_data.append({
                        "source": "USPTO",
                        "applicationNumber": app_meta.get("applicationNumberText"),
                        "title": app_meta.get("inventionTitle"),
                        "filingDate": app_meta.get("filingDate"),
                        "applicantName": app_meta.get("applicantName"),
                        "abstract": app_meta.get("abstractText")
                    })
            return json.dumps(extracted_data)
        except requests.exceptions.RequestException as e:
            return f"Erro ao chamar USPTO Patent Search API: {e}"
        except json.JSONDecodeError:
            return "Erro ao decodificar resposta JSON da USPTO API."

class EPO_PatentSearchTool(BaseTool):
    name: str = "EPO Patent Search Tool"
    description: str = ("Busca patentes na base de dados da EPO (European Patent Office) usando a API OPS. "
                      "A busca é realizada nos campos de título (ti) e resumo (ab). "
                      "A query pode conter curingas como '*' e '?'.")
    # ===== Métodos auxiliares =====
    def validate_epo_query(self, query: str) -> str:
        """Valida e retorna a query limpa."""
        if not query or not query.strip():
            return None
        return query.strip()

    def safe_epo_request(self, url, headers, params, retries=3, timeout=30):
        """Executa GET seguro com retries e timeout."""
        last_error_message = "Causa desconhecida"
        for attempt in range(retries):
            try:
                resp = requests.get(url, headers=headers, params=params, timeout=timeout)
                resp.raise_for_status()
                # Retorna a resposta bem-sucedida e nenhuma mensagem de erro
                return resp, None
            except requests.exceptions.Timeout as e:
                print(f"[WARN] Timeout na tentativa {attempt+1}/{retries}.")
                last_error_message = f"A requisição excedeu o tempo limite de {timeout} segundos."
            except requests.exceptions.RequestException as e:
                print(f"[ERRO] Falha na requisição EPO: {e}")
                last_error_message = f"Erro de requisição: {e}"
            break
        time.sleep(2)
        return None, last_error_message

    def get_epo_access_token(self):
        """Obtém token OAuth2 de acesso ao EPO OPS API."""
        consumer_key = os.getenv("EPO_CONSUMER_KEY")
        consumer_secret = os.getenv("EPO_CONSUMER_SECRET")
        if not consumer_key or not consumer_secret:
            raise RuntimeError("Credenciais EPO_CONSUMER_KEY/SECRET não configuradas no .env")

        token_url = "https://ops.epo.org/3.2/auth/accesstoken"
        try:
            resp = requests.post(
                token_url,
                data={"grant_type": "client_credentials"},
                auth=(consumer_key, consumer_secret),
                timeout=15
            )
            resp.raise_for_status()
            token_data = resp.json()
            return token_data.get("access_token")
        except Exception as e:
            raise RuntimeError(f"Erro ao obter token EPO: {e}")

    # ===== Método principal exigido pelo BaseTool =====
    def _run(self,  query: str= 'ab OR ti any "all"') -> str:
        
        clean_query = self.validate_epo_query(query)
        if not clean_query:
            return json.dumps({"error": "Query inválida"})

        # Remove aspas da query do usuário para evitar quebras na sintaxe CQL.
        query_content = clean_query.replace('"', '')
        
        # A busca mais eficaz para termos de tecnologia é combinar o título ('ti') e o resumo ('ab').
        # Isso garante que a busca seja ampla e relevante para o que o usuário digitou.
        formatted_query = f'ab OR ti any "{query_content}"'
        try:
            access_token = self.get_epo_access_token()
            print("[INFO] Token OAuth2 obtido com sucesso.")
        except Exception as e:
           return json.dumps({"error": str(e)})

                
        # Endpoint correto para busca bibliográfica (título, resumo).
        # O endpoint 'register/search' é para status legal e não suporta buscas de texto livre.
        base_url = "https://ops.epo.org/3.2/rest-services/published-data/search"
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/json',
            'User-Agent': 'BuscapiPI/1.0'
        }
        params = {'q': formatted_query, 'Range': '1-25'}
        print(f"[DEBUG] Buscando EPO com query: {formatted_query}")
        
        response, error_message = self.safe_epo_request(base_url, headers, params, timeout=30)
        
        if response:
            try:
                data = response.json()
                # A API da EPO pode retornar um erro 200 OK com uma mensagem de falha no corpo.
                # Verificamos a presença da chave 'fault'.
                if "fault" in data:
                    fault_string = data.get("fault", {}).get("faultstring", "Erro desconhecido da API da EPO")
                    print(f"[ERRO] API da EPO retornou uma falha: {fault_string}")
                    return json.dumps({"error": fault_string})
                
                # Se tudo estiver OK, retorna a string JSON dos dados válidos.
                return json.dumps(data)
            except json.JSONDecodeError:
                print(f"[ERRO] Resposta da EPO não é um JSON válido.")
                return json.dumps({"error": "Resposta da EPO não é JSON válido", "conteudo": response.text})
        else:
            # Usa a mensagem de erro específica retornada por safe_epo_request
            return json.dumps({"error": f"Falha ao conectar com a API da EPO: {error_message}"})

class GooglePatentsSearchTool(BaseTool):
    name: str = "Google Patents Search Tool"
    description: str = "Ferramenta para buscar patentes no Google Patents via web scraping."

    def _run(self, query: str) -> str:
        """
        Executa uma busca no Google Patents e extrai os resultados.
        A query é formatada para buscar no título e resumo.
        """
        # Formata a query para o formato de URL do Google Patents
        formatted_query = query.replace(" ", "+")
        # Busca por título (ti) e resumo (ab)
        url = f"https://patents.google.com/?q=ti%3d({formatted_query})+OR+ab%3d({formatted_query})&num=20"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()            
            soup = BeautifulSoup(response.text, 'html.parser')            
            # Encontra todos os resultados de pesquisa na página
            search_results = soup.find_all('article', class_='search-result')            
            extracted_data = []
            for result in search_results:
                title_tag = result.find('h4', itemprop='title')
                title = title_tag.text.strip() if title_tag else "N/A"                
                abstract_tag = result.find('div', class_='abstract')
                abstract = abstract_tag.text.strip() if abstract_tag else "N/A"                
                publication_number_tag = result.find('dd', itemprop='publicationNumber')
                publication_number = publication_number_tag.text.strip() if publication_number_tag else None
                assignee_tag = result.find('dd', itemprop='assigneeOriginal')
                assignee = assignee_tag.text.strip() if assignee_tag else "Não informado"
                filing_date_tag = result.find('dd', itemprop='filingDate')
                filing_date = filing_date_tag.text.strip() if filing_date_tag else None
                link = "https://patents.google.com" + result.find('a', class_='result-link')['href'] if result.find('a', class_='result-link') else None
                extracted_data.append({
                    "source": "GooglePatents",
                    "applicationNumber": publication_number,
                    "publicationNumber": publication_number,
                    "title": title,
                    "filingDate": filing_date,
                    "applicantName": assignee,
                    "abstract": abstract,
                    "link": link
                })            
            return json.dumps(extracted_data)
        except requests.exceptions.RequestException as e:
            return json.dumps({"error": f"Erro ao acessar o Google Patents: {e}"})
        except Exception as e:
            return json.dumps({"error": f"Erro ao processar a página do Google Patents: {e}"})

class INPI_PatentSearchTool(BaseTool):
    name: str = "INPI Patent Search Tool"
    description: str = ("Busca patentes na interface web do INPI (Brasil) via web scraping. "
                      "A busca é realizada no campo de título da patente.")

    def _perform_search_request(self, query: str) -> Tuple[Optional[requests.Response], Optional[str]]:
        """
        Encapsula a requisição HTTP POST para o portal de busca do INPI.
        Retorna o objeto de resposta ou uma mensagem de erro.
        """
        base_url = "https://busca.inpi.gov.br/pePI/jsp/patentes/PatenteSearchAvancado.jsp"
        payload = {
            'Titulo': query,
            'Action': 'search',
            'TipoPesquisa': 'basica'
        }
        headers = {
          "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": "https://busca.inpi.gov.br/pePI/jsp/patentes/PatenteSearchAvancado.jsp"
        }
        try:
            response = requests.post(base_url, data=payload, headers=headers, timeout=45)
            response.raise_for_status()
            return response, None
        except requests.exceptions.RequestException as e:
            return None, f"Erro de rede ao acessar o portal de busca do INPI: {e}"

    def _parse_response_html(self, html_content: bytes) -> Tuple[Optional[list], Optional[str]]:
        """
        Encapsula o parsing do HTML de resposta para extrair os dados da patente.
        Esta versão é mais robusta, extraindo texto e processando-o em vez de usar regex frágeis.
        Retorna uma lista de dados extraídos ou uma mensagem de erro.
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            results_table = soup.find('table', id='resultado_patente')

            if not results_table:
                if "Nenhum resultado foi encontrado" in html_content.decode('utf-8', errors='ignore'):
                    return [], None
                return None, "Tabela de resultados não encontrada na página do INPI. O layout pode ter mudado."

            extracted_data = []
            for row in results_table.find_all('tr'):
                cells = row.find_all('td')
                if len(cells) < 2:
                    continue

                data_cell = cells[1]
                number_tag = data_cell.find('b')
                title_tag = data_cell.find('a')

                if not (number_tag and title_tag):
                    continue

                # Extração primária a partir de tags conhecidas
                numero_pedido = number_tag.text.strip()
                titulo = title_tag.text.strip()
                link_suffix = title_tag.get('href')
                link = f"https://busca.inpi.gov.br{link_suffix}" if link_suffix else None

                # Extração secundária a partir do conteúdo de texto da célula
                # Isso é mais robusto do que usar regex no HTML bruto
                cell_text_content = data_cell.get_text(separator='\n', strip=True)
                lines = [line.strip() for line in cell_text_content.split('\n') if line.strip()]
                
                data_deposito = next((line.replace("Data de Depósito:", "").strip() for line in lines if line.startswith("Data de Depósito:")), None)
                requerente = next((line.replace("Requerente(s):", "").strip() for line in lines if line.startswith("Requerente(s):")), "Não informado")

                extracted_data.append({
                    "source": "INPI",
                    "applicationNumber": numero_pedido,
                    "title": titulo,
                    "filingDate": data_deposito,
                    "applicantName": requerente,
                    "link": link,
                    "abstract": None, # A página de resultados básicos não mostra o resumo
                })
            return extracted_data, None
        except Exception as e:
            return None, f"Erro ao processar a página do INPI: {e}"
    def _run(self, query: str) -> str:
        response, error = self._perform_search_request(query)
        if error:
            return json.dumps({"error": error})
        extracted_data, error = self._parse_response_html(response.content)
        if error:
            return json.dumps({"error": error})        
        try:
            return json.dumps(extracted_data)
        except TypeError as e:
            return json.dumps({"error": f"Erro ao serializar os dados extraídos: {e}"})

# tools/custom_tools.py
class IPDataCollectorTool(BaseTool):
    name: str = "IP Data Collector Tool"
    description: str = (
        "Ferramenta para coletar dados brutos de PI de múltiplas fontes (Serper, USPTO, EPO, INPI, Google Patents) "
        "e persistir os resultados brutos no banco de dados. "
        "Entrada: JSON string com chaves 'query' e 'search_query_id'."
    )

    def _safe_loads(self, s: str):
        try:
            return json.loads(s)
        except Exception:
            return None

    def _ensure_source(self, item: dict, provider: str) -> dict:
        # preserva a fonte original, se já existir
        src_original = item.get('source')
        if src_original and src_original != provider:
            item['source_original'] = src_original
        # força a fonte padronizada para o pipeline
        item['source'] = provider
        return item

    def _persist_many(self, db: BuscapiDB, search_query_id: int, provider: str, data_any) -> list:
        """Normaliza, persiste e anexa db_raw_id em cada item; devolve lista de itens clonados."""
        results = []
        data_list = normalize_to_list(data_any)
        for it in data_list:
            if not isinstance(it, dict):
                continue
            cloned = copy.deepcopy(it)
            cloned = self._ensure_source(cloned, provider)
            raw_id = db.insert_search_result_raw(search_query_id, provider, cloned)
            cloned['db_raw_id'] = raw_id
            results.append(cloned)
        return results

    def _run(self, task_input: str) -> str:
        # 1) Validar entrada
        try:
            payload = json.loads(task_input)
            query = payload['query']
            search_query_id = payload['search_query_id']
        except (KeyError, json.JSONDecodeError):
            return json.dumps([{"error": "Entrada inválida. Esperado JSON com 'query' e 'search_query_id'."}])

        db = BuscapiDB()
        all_results = []

        try:
            # Helper para processar cada provedor: chama a ferramenta, tenta desserializar
            # e registra logs no DB caso a resposta contenha um campo 'error' ou seja inválida.
            def _call_provider_and_persist(tool_instance, provider_name: str):
                try:
                    resp_str = tool_instance._run(query)
                except Exception as ex:
                    db.insert_search_log(search_query_id, f"Erro {provider_name} (exception): {ex}")
                    return []

                # Se a ferramenta retornou já um texto simples de erro, loga e sai
                if isinstance(resp_str, str) and (resp_str.strip().lower().startswith('erro') or resp_str.strip().lower().startswith('error')):
                    db.insert_search_log(search_query_id, f"Erro {provider_name}: {resp_str}")
                    return []

                parsed = self._safe_loads(resp_str)
                # Se a resposta for um dict com chave 'error', persiste o log
                if isinstance(parsed, dict) and parsed.get('error'):
                    db.insert_search_log(search_query_id, f"Erro {provider_name}: {parsed.get('error')}")
                    return []

                # Caso especial: SERPER costuma embutir resultados em 'organic'
                if provider_name == 'SERPER' and isinstance(parsed, dict) and 'organic' in parsed:
                    return self._persist_many(db, search_query_id, provider_name, parsed['organic'])

                return self._persist_many(db, search_query_id, provider_name, parsed)

            # --- SERPER ---
            try:
                all_results += _call_provider_and_persist(SerperDevTool(), "SERPER")
            except Exception:
                # Segurança adicional; _call_provider_and_persist já loga a exceção
                pass

            # --- USPTO ---
            try:
                all_results += _call_provider_and_persist(USPTO_PatentSearchTool(), "USPTO")
            except Exception:
                pass

            # --- EPO ---
            try:
                all_results += _call_provider_and_persist(EPO_PatentSearchTool(), "EPO")
            except Exception:
                pass

            # --- INPI ---
            try:
                all_results += _call_provider_and_persist(INPI_PatentSearchTool(), "INPI")
            except Exception:
                pass

            # --- Google Patents ---
            try:
                all_results += _call_provider_and_persist(GooglePatentsSearchTool(), "GOOGLE_P")
            except Exception:
                pass

        finally:
            db.close()

        if not all_results:
            return json.dumps([{"message": "Nenhum resultado encontrado para a query."}])

        return json.dumps(all_results)

# dentro de NLPClassificationTool (tools/custom_tools.py)
class NLPClassificationTool(BaseTool):
    name: str = "NLP Classification Tool"
    description: str = (
        "Classifica resultados de PI em categorias estruturadas."
    )

    def _run(self, raw_data_json: str) -> str:
        try:
            # task_input é sempre uma string JSON
            raw_api_responses = json.loads(raw_data_json)
        except Exception:
            return json.dumps([{"error": "Entrada inválida em NLPClassificationTool"}])

        # usa a função auxiliar que ajustamos no passo 2
        flat_items = self._flatten_raw_data(raw_api_responses)

        # se não tiver nada útil, retorna vazio
        if not flat_items:
            return json.dumps([])

        classified_results = []
        db = BuscapiDB()
        try:
            for item in flat_items:
                # regra de classificação mínima (exemplo: sempre categoria 'Patent')
                classified = {
                    "db_raw_id": item.get("db_raw_id"),
                    "source": item.get("source"),
                    "category": "Patent",  # aqui você pode plugar seu modelo NLP
                    "title": item.get("title") or item.get("inventionTitle") or "",
                    "applicant": item.get("applicantName") or "",
                }
                db.insert_search_result_structured(item.get("db_raw_id"), classified)
                classified_results.append(classified)
        finally:
            db.close()

        return json.dumps(classified_results)
                
    # tools/custom_tools.py dentro de NLPClassificationTool
    def _flatten_raw_data(self, raw_api_responses: list) -> list:
        """Aceita tanto itens já normalizados (1 item = 1 registro) quanto respostas agregadas."""
        all_results = []

        for response in raw_api_responses:
            if not isinstance(response, dict):
                continue

            # Caso 1: já normalizado (vindo do coletor refatorado)
            if response.get('db_raw_id') and not any(k in response for k in ('organic', 'ops:world-patent-data')):
                all_results.append(response)
                continue

            # Caso 2: SERPER agregado
            if 'organic' in response and isinstance(response['organic'], list):
                db_raw_id = response.get('db_raw_id')
                for item in response['organic']:
                    if isinstance(item, dict):
                        item = copy.deepcopy(item)
                        item['source'] = response.get('searchParameters', {}).get('engine', 'SERPER')
                        if db_raw_id:
                            item['db_raw_id'] = db_raw_id
                        all_results.append(item)
                continue

            # Caso 3: EPO agregado (mantém a lógica existente)
            search_result = response.get('ops:world-patent-data', {}).get('ops:biblio-search', {}).get('ops:search-result', {})
            epo_docs = search_result.get('exchange-documents', {}).get('exchange-document', [])
            if isinstance(epo_docs, list) and epo_docs:
                db_raw_id = response.get('db_raw_id')
                for doc in epo_docs:
                    if isinstance(doc, dict):
                        item = {
                            "source": "EPO",
                            "exchange_document": doc
                        }
                        if db_raw_id:
                            item['db_raw_id'] = db_raw_id
                        all_results.append(item)
                continue

            # Caso 4: Fallback — se for um dict “plano”, mantemos
            all_results.append(response)

        return all_results

    @classmethod
    @lru_cache(maxsize=2048)
    def _extract_entities_cached(cls, text_to_analyze: str) -> dict:
        """
        Executa a extração de entidades em um texto e armazena o resultado em cache.
        O cache LRU evita reprocessar o mesmo texto várias vezes.
        """
        # tenta carregar modelo spacy se ainda não carregado
        try:
            cls._ensure_nlp_loaded()
        except Exception:
            # carregamento falhou; usaremos fallback simples
            pass

        nlp_model = getattr(cls, '_nlp', None)
        if not text_to_analyze or not isinstance(text_to_analyze, str) or not text_to_analyze.strip():
            return {"organizations": [], "persons": []}

        # Se houver modelo spacy, delega a ele
        if nlp_model:
            doc = nlp_model(text_to_analyze)
            organizations = list(set([ent.text for ent in doc.ents if ent.label_ == "ORG"]))
            persons = list(set([ent.text for ent in doc.ents if ent.label_ == "PERSON"]))
            return {"organizations": organizations, "persons": persons}

        # Fallback simples baseado em heurísticas/regex quando spacy não está disponível
        return cls._extract_entities_fallback(text_to_analyze)

    @classmethod
    def _ensure_nlp_loaded(cls):
        """Tenta carregar um modelo spacy clássico; se falhar, deixa _nlp como None."""
        if getattr(cls, '_nlp', None):
            return
        if not spacy:
            cls._nlp = None
            return
        # tenta alguns modelos comuns sem instalar nada adicional
        for model_name in ("pt_core_news_sm", "en_core_web_sm", "xx_ent_wiki_sm"):
            try:
                cls._nlp = spacy.load(model_name)
                return
            except Exception:
                continue
        cls._nlp = None

    @classmethod
    def _extract_entities_fallback(cls, text: str) -> dict:
        """Fallback muito simples: encontra possíveis pessoas (2+ palavras capitalizadas) e organizações (acronym/keywords).
        Não é preciso ser perfeito — serve para testes quando spacy não está presente."""
        # Pessoas: sequências de 2+ palavras que iniciam com letra maiúscula
        person_pattern = re.compile(r"\b([A-ZÀ-Ý][a-zà-ÿ]+(?:\s+[A-ZÀ-Ý][a-zà-ÿ]+)+)\b")
        persons = list({m.group(1).strip() for m in person_pattern.finditer(text)})

        # Organizações: busca por siglas (3+ letras maiúsculas) ou palavras seguidas de Ltda/SA/Inc/Corp
        orgs = set()
        for m in re.finditer(r"\b([A-Z]{3,})\b", text):
            orgs.add(m.group(1))

        suffix_pattern = re.compile(r"\b([A-ZÀ-Ý][\w\.&\- ]{2,}?)\s+(Ltda|LTDA|S\.A\.|SA|Inc|Corp|LLC)\b", re.IGNORECASE)
        for m in suffix_pattern.finditer(text):
            orgs.add(m.group(1).strip())

        # Se não encontrou nada, tentar palavras compostas em maiúscula título que possam ser organizações
        if not orgs:
            title_caps = re.compile(r"\b([A-ZÀ-Ý][a-zà-ÿ]+(?:\s+[A-ZÀ-Ý][a-zà-ÿ]+)+)\b")
            for m in title_caps.finditer(text):
                candidate = m.group(1).strip()
                # heurística simples: se tiver mais de uma palavra e não parecer uma pessoa (já capturada), pode ser org
                if candidate not in persons:
                    orgs.add(candidate)

        return {"organizations": list(orgs), "persons": persons}

    def _parse_date(self, date_string: str) -> Optional[datetime.date]:
        """
        Tenta converter uma string de data em um objeto datetime.date.
        Lida com múltiplos formatos comuns encontrados nas APIs.
        """
        if not date_string or not isinstance(date_string, str):
            return None
        
        # Lista de formatos a serem tentados em ordem de probabilidade
        formats_to_try = [
            '%Y-%m-%d',          # Formato '2023-12-25' (comum em APIs como INPI, USPTO)
            '%Y%m%d',            # Formato '20231225' (comum no Google Patents)
            '%d/%m/%Y',          # Formato '25/12/2023'
            '%Y-%m-%dT%H:%M:%SZ', # Formato ISO 8601 com Z (UTC)
        ]
        
        for fmt in formats_to_try:
            try:
                # Para formatos que incluem hora, .date() extrai apenas a parte da data
                return datetime.strptime(date_string, fmt).date()
            except ValueError:
                continue
        return None # Retorna None se nenhum formato corresponder

    def _run(self, text_data: str) -> str:
        try:
            # text_data é o JSON string da ferramenta anterior
            raw_results = json.loads(text_data)
        except json.JSONDecodeError:
            return json.dumps([{"error": "Dados de entrada inválidos para classificação"}])

        # Etapa 1: Achatamento dos dados brutos de diferentes fontes
        flattened_results = self._flatten_raw_data(raw_results)

        if not flattened_results:
            return json.dumps([{"message": "Nenhum item de resultado pôde ser extraído dos dados brutos."}])

        classified_data = []
        db = BuscapiDB()

        try:
            # Etapa 2: Classificação e persistência dos dados achatados
            for item in flattened_results:
                if not isinstance(item, dict) or 'db_raw_id' not in item:
                    continue

                # --- 1. Classificação por Categoria ---
                category = "Outros"
                title = (item.get("title", "") or "").lower()
                source = item.get("source", "")

                for rule in category_rules:
                    # Verifica se a fonte do item está na lista de fontes permitidas da regra
                    # Se a lista não existir na regra, a regra se aplica a todas as fontes
                    included_sources = rule.get("include_sources")
                    if included_sources is None or source in included_sources:
                        # Verifica se alguma palavra-chave da regra está no título
                        if any(keyword.lower() in title for keyword in rule.get("keywords", [])):
                            category = rule["category"]
                            break  # Para na primeira regra que corresponder

                item["category"] = category

                # --- 2. Extração de Entidades (NER) ---
                text_to_analyze = (item.get("title", "") or "") + ". " + (item.get("abstract", "") or item.get("snippet", "") or "")
                
                # Chama o método cacheado para obter as entidades
                entities = self.__class__._extract_entities_cached(text_to_analyze)
                item["extracted_organizations"] = entities["organizations"]
                item["extracted_persons"] = entities["persons"]
                
                # --- 3. Extração e Formatação da Data ---
                # Tenta obter a data de diferentes campos possíveis que as APIs retornam
                date_str = item.get('filingDate') or item.get('publicationDate') or item.get('date')
                parsed_date = self._parse_date(date_str)

                # --- 4. Persistência do Resultado Estruturado ---
                # Garante que o título não exceda o limite do banco de dados
                safe_title = (item.get("title", "N/A") or "N/A")[:255]

                db.insert_search_result_structured(
                    search_result_raw_id=item['db_raw_id'],
                    category=item.get('category', 'Outros'),
                    title=safe_title,
                    date_found=parsed_date,
                    applicant=item.get('applicantName'),
                    summary=item.get('abstract') or item.get('snippet'),
                    structured_json=item
                )
                classified_data.append(item)
        finally:
            db.close()
            
        return json.dumps(classified_data)

class DataAnalysisTool(BaseTool):
    name: str = "Data Analysis Tool"
    description: str = "Ferramenta para realizar análises de dados usando Pandas."

    def _run(self, structured_data_json: str) -> str:
        try:
            data = json.loads(structured_data_json)
            df = pd.DataFrame(data)
        except (json.JSONDecodeError, ValueError) as e:
            return json.dumps({"error": f"Erro ao processar dados para análise: {e}"})

        analysis_results = {}

        if not df.empty:
            if 'category' in df.columns:
                analysis_results['count_by_category'] = df['category'].value_counts().to_dict()

            date_column = None
            if 'filingDate' in df.columns:
                date_column = 'filingDate'
            elif 'publicationDate' in df.columns:
                date_column = 'publicationDate'

            if date_column:
                try:
                    df['year'] = pd.to_datetime(df[date_column], errors='coerce').dt.year
                    analysis_results['count_by_year'] = df['year'].value_counts().sort_index().to_dict()
                except Exception as e:
                    analysis_results['date_parsing_error'] = str(e)

            analysis_results['total_records'] = len(df)

        return json.dumps(analysis_results)

class VisualizationTool(BaseTool):
    name: str = "Visualization Tool"
    description: str = "Ferramenta para gerar gráficos interativos usando Plotly e salvá-los como imagens."

    def _run(self, analysis_results_json: str, plot_type: str = "bar") -> str:
        try:
            analysis_results = json.loads(analysis_results_json)
        except json.JSONDecodeError:
            # Retorna um JSON de erro para consistência
            return json.dumps({"error": "Dados de análise inválidos para visualização."})
        
        fig = None
        
        if plot_type == "bar" and 'count_by_category' in analysis_results:
            data = analysis_results['count_by_category']
            if data:
                df = pd.DataFrame(list(data.items()), columns=['Categoria', 'Contagem'])
                fig = px.bar(df, x='Categoria', y='Contagem', title="Contagem por Categoria de PI",
                             labels={'Contagem': 'Quantidade', 'Categoria': 'Categoria de PI'},
                             text_auto=True)
            else:
                fig = px.line(title="Dados de categoria insuficientes")
                fig.add_annotation(text="Dados de categoria insuficientes para gerar o gráfico.", xref="paper", yref="paper", showarrow=False)
        
        elif plot_type == "pie" and 'count_by_category' in analysis_results:
            data = analysis_results['count_by_category']
            if data:
                df = pd.DataFrame(list(data.items()), columns=['Categoria', 'Contagem'])
                fig = px.pie(df, values='Contagem', names='Categoria', title="Distribuição Percentual por Categoria", hole=.3)
                fig.update_traces(textposition='inside', textinfo='percent+label')
            else:
                fig = px.pie(title="Dados de categoria insuficientes")
                fig.add_annotation(text="Dados de categoria insuficientes para gerar o gráfico.", xref="paper", yref="paper", showarrow=False)

        elif plot_type == "line" and 'count_by_year' in analysis_results:
            data = analysis_results['count_by_year']
            if data:
                # Filtra chaves nulas e converte para inteiro para ordenação correta
                filtered_data = {int(k): v for k, v in data.items() if pd.notna(k) and str(k).isdigit()}
                if filtered_data:
                    df = pd.DataFrame(sorted(filtered_data.items()), columns=['Ano', 'Contagem'])
                    fig = px.line(df, x='Ano', y='Contagem', title="Tendência de Registros por Ano", markers=True,
                                  labels={'Contagem': 'Quantidade de Registros', 'Ano': 'Ano'})
                else:
                    fig = px.line(title="Dados de ano válidos insuficientes")
                    fig.add_annotation(text="Dados de ano válidos insuficientes para gerar o gráfico.", xref="paper", yref="paper", showarrow=False)

        if fig:
            fig.update_layout(
                title_x=0.5, 
                font=dict(family="Arial, sans-serif"),
                # Melhora a visibilidade da barra de ferramentas do gráfico
                modebar=dict(
                    bgcolor='rgba(240, 240, 240, 0.8)', # Fundo cinza claro semi-transparente
                    color='rgba(0, 0, 0, 0.9)',         # Ícones pretos para alto contraste
                    activecolor='rgba(0, 80, 255, 0.9)' # Cor azul para o ícone ativo
                )
            )
            # Retorna a representação JSON do gráfico em vez de salvar um arquivo
            return fig.to_json()
        else:
            return json.dumps({"error": "Tipo de plotagem ou dados de análise inválidos."})


class LLMTool(BaseTool):
    """Ferramenta LLM leve para gerar/otimizar insights a partir de análise/classificados.

    Usa OpenAI ChatCompletion quando disponível (variável OPENAI_API_KEY e package openai).
    Caso contrário, usa um fallback heurístico simples.
    """
    name: str = "LLM Assistant Tool"
    description: str = "Gera ou melhora insights a partir de análise e dados classificados (modelo configurável via LLM_MODEL no .env)."

    def _call_openai_chat(self, messages: list, model: str | None = None, max_tokens: int = 512) -> str:
        try:
            import openai
        except Exception:
            raise RuntimeError("Biblioteca openai não instalada")

        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise RuntimeError('OPENAI_API_KEY não configurada')

        openai.api_key = api_key
        # Determina o modelo a partir da variável de ambiente LLM_MODEL ou do parâmetro
        env_model = os.getenv('LLM_MODEL')
        model_to_use = env_model or model or "gpt-5-nano"
        # Tenta usar a API de chat padrão
        resp = openai.ChatCompletion.create(model=model_to_use, messages=messages, max_tokens=max_tokens)
        # Extrai conteúdo de forma defensiva
        try:
            return resp.choices[0].message.content
        except Exception:
            try:
                return resp.choices[0].text
            except Exception:
                raise RuntimeError('Resposta inesperada do LLM')

    def _heuristic_insights(self, analysis: dict, classified: list) -> str:
        if not analysis:
            return "Sem dados de análise para gerar insights."
        parts = []
        cbc = analysis.get('count_by_category') if isinstance(analysis, dict) else None
        if cbc:
            try:
                top = max(cbc.items(), key=lambda x: x[1])
                parts.append(f"Categoria mais proeminente: {top[0]} ({top[1]} registros).")
            except Exception:
                pass

        cby = analysis.get('count_by_year') if isinstance(analysis, dict) else None
        if cby:
            try:
                years = sorted(((int(k), v) for k, v in cby.items() if str(k).isdigit()), key=lambda x: x[0])
                if len(years) >= 2:
                    trend = 'crescente' if years[-1][1] > years[0][1] else ('decrescente' if years[-1][1] < years[0][1] else 'estável')
                    parts.append(f"Tendência temporal: {trend}.")
            except Exception:
                pass

        parts.append("Recomendação: revisar documentos da categoria principal para priorizar ações de proteção.")
        return " ".join(parts)

    def _run(self, input_data: str) -> str:
        # input_data é um JSON string ou dict com 'analysis' e/ou 'classified'
        try:
            payload = json.loads(input_data) if isinstance(input_data, str) else (input_data or {})
        except Exception:
            payload = {}

        analysis = payload.get('analysis') if isinstance(payload, dict) else None
        classified = payload.get('classified') if isinstance(payload, dict) else None

        # Monta prompt simples
        system_msg = (
            "Você é um assistente técnico que resume análises de propriedade intelectual em insights acionáveis."
        )
        user_parts = []
        if analysis:
            user_parts.append(f"Analysis:\n{json.dumps(analysis, ensure_ascii=False)}")
        if classified:
            try:
                sample = [c.get('title') for c in classified[:5] if isinstance(c, dict) and c.get('title')]
                user_parts.append(f"Sample titles:\n{json.dumps(sample, ensure_ascii=False)}")
            except Exception:
                pass

        user_msg = "\n\n".join(user_parts) or "Sem contexto"

        # Tenta chamar LLM; se falhar, usa heurística
        try:
            messages = [{"role": "system", "content": system_msg}, {"role": "user", "content": user_msg}]
            text = self._call_openai_chat(messages)
            insights = text.strip()
        except Exception:
            insights = self._heuristic_insights(analysis or {}, classified or [])

        return json.dumps({"insights": insights}, ensure_ascii=False)


class PDFReportTool(BaseTool):
    """Adapter tool que envolve o `PDFGenerator` existente e expõe um `_run` compatível.

    Entrada esperada: JSON string com chaves:
      - results: dict (os mesmos dados usados pelo PDFGenerator)
      - output_path: str (caminho do arquivo PDF de saída)

    Retorna: JSON string {"path": output_path} em caso de sucesso ou {"error": msg}.
    """
    name: str = "PDF Report Tool"
    description: str = "Gera um relatório PDF a partir dos resultados de análise usando o PDFGenerator interno."

    def _run(self, input_data: str) -> str:
        try:
            payload = json.loads(input_data) if isinstance(input_data, str) else (input_data or {})
        except Exception:
            return json.dumps({"error": "Entrada inválida para PDFReportTool"})

        results = payload.get('results')
        output_path = payload.get('output_path')
        if not results or not output_path:
            return json.dumps({"error": "Faltando 'results' ou 'output_path' na entrada"})

        try:
            # Importa o gerador real e delega
            from tools.pdf_generator import PDFGenerator
            gen = PDFGenerator()
            gen.generate_report(results, output_path)
            return json.dumps({"path": output_path})
        except Exception as e:
            return json.dumps({"error": f"Falha ao gerar PDF: {e}"})
