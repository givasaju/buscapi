
import hashlib
import json
import psycopg2
from psycopg2.extras import Json
from datetime import datetime


class BuscapiDB:
    def __init__(self, dbname="buscapi_bd", user="postgres", password="givas2025", host='localhost', port=5432):
        self.conn = psycopg2.connect(
            dbname=dbname,
            user=user,
            password=password,
            host=host,
            port=port
        )
        self.conn.autocommit = True
        self.cur = self.conn.cursor()

    def close(self):
        self.cur.close()
        self.conn.close()

    def insert_search_query(self, criteria: str, status: str='pending', user_id: int = None) -> int:
        """Insere um registro na tabela search_query e retorna o id criado."""
        query = """
            INSERT INTO search_query (criteria, created_at, status, user_id)
            VALUES (%s, %s, %s, %s) RETURNING id;
        """
        created_at = datetime.now()
        self.cur.execute(query, (criteria, created_at, status, user_id))
        search_query_id = self.cur.fetchone()[0]
        return search_query_id

    def insert_search_result_raw(self, search_query_id: int, source: str, raw_data: dict) -> int:
        try:
            # 1. Calcular hash único do item
            item_hash = hashlib.sha256(
                json.dumps(raw_data, sort_keys=True, ensure_ascii=False).encode("utf-8")
            ).hexdigest()

            # 2. Incluir hash dentro do raw_data
            raw_data["_hash"] = item_hash
            raw_json = json.dumps(raw_data, ensure_ascii=False)

            cursor = self.conn.cursor()

            # 3. Checar se já existe (search_query_id + hash)
            cursor.execute("""
                SELECT id FROM search_result_raw
                WHERE search_query_id = %s
                AND raw_json::jsonb @> %s::jsonb
            """, (search_query_id, json.dumps({"_hash": item_hash})))

            existing = cursor.fetchone()
            if existing:
                return existing[0]  # retorna id existente

            # 4. Inserir novo se não houver duplicado
            cursor.execute("""
                INSERT INTO search_result_raw (search_query_id, source, raw_json)
                VALUES (%s, %s, %s)
                RETURNING id
            """, (search_query_id, source, raw_json))
            self.conn.commit()
            return cursor.fetchone()[0]

        except Exception as e:
            print(f"Erro ao inserir resultado bruto: {e}")
            self.conn.rollback()
            return -1

    def insert_search_result_structured(self, search_result_raw_id: int, category: str, title: str,
                                        date_found: datetime.date = None, applicant: str = None,
                                        summary: str = None, structured_json: dict = None) -> int:
        """Insere resultado estruturado/classificado."""
        query = """
            INSERT INTO search_result_structured
            (search_result_raw_id, category, title, date_found, applicant, summary, structured_json)
            VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id;
        """
        self.cur.execute(query, (
            search_result_raw_id, category, title, date_found, applicant, summary,
            Json(structured_json) if structured_json else None))
        result_structured_id = self.cur.fetchone()[0]
        return result_structured_id

    def insert_search_log(self, search_query_id: int, log_msg: str) -> int:
        """Insere uma mensagem de log associada à uma busca."""
        query = """
            INSERT INTO search_log (search_query_id, log_msg, log_time)
            VALUES (%s, %s, %s) RETURNING id;
        """
        log_time = datetime.now()
        self.cur.execute(query, (search_query_id, log_msg, log_time))
        log_id = self.cur.fetchone()[0]
        return log_id

    def update_search_query_status(self, search_query_id: int, new_status: str):
        """Atualiza o status da busca."""
        query = "UPDATE search_query SET status=%s WHERE id=%s;"
        self.cur.execute(query, (new_status, search_query_id))

    # --- MÉTODOS DE BUSCA ADICIONADOS ---
    def get_query_id_by_criteria(self, criteria: str) -> int:
        """Encontra o ID da busca mais recente para um critério."""
        query = "SELECT id FROM search_query WHERE criteria = %s ORDER BY created_at DESC LIMIT 1;"
        self.cur.execute(query, (criteria,))
        result = self.cur.fetchone()
        return result[0] if result else None

    def get_structured_results_by_query_id(self, search_query_id: int) -> list:
        """Busca todos os resultados estruturados para um search_query_id, retornando apenas o JSON."""
        query = """
            SELECT s.structured_json
            FROM search_result_structured s
            JOIN search_result_raw r ON s.search_result_raw_id = r.id
            WHERE r.search_query_id = %s;
        """
        self.cur.execute(query, (search_query_id,))
        results = [row[0] for row in self.cur.fetchall() if row and row[0]]
        return results

    def get_search_query_by_id(self, query_id: int) -> dict:
        """Busca uma search query pelo seu ID."""
        query = "SELECT id, criteria, created_at, status FROM search_query WHERE id = %s;"
        self.cur.execute(query, (query_id,))
        result = self.cur.fetchone()
        if result:
            columns = [desc[0] for desc in self.cur.description]
            return dict(zip(columns, result))
        return None
    
    def get_all_search_queries(self) -> list:
        """Busca todos os registros da tabela search_query."""
        query = "SELECT id, criteria, created_at, status FROM search_query ORDER BY created_at DESC;"
        self.cur.execute(query)
        # Retorna uma lista de dicionários para fácil conversão em DataFrame
        columns = [desc[0] for desc in self.cur.description]
        return [dict(zip(columns, row)) for row in self.cur.fetchall()]