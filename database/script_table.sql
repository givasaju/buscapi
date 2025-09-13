-- Tabela principal de buscas
CREATE TABLE search_query (
  id SERIAL PRIMARY KEY,
  criteria TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  status VARCHAR(30) DEFAULT 'pending',
  user_id INTEGER
);

-- Resultados brutos das buscas
CREATE TABLE search_result_raw (
  id SERIAL PRIMARY KEY,
  search_query_id INTEGER NOT NULL REFERENCES search_query(id) ON DELETE CASCADE,
  source VARCHAR(50) NOT NULL,
  raw_json JSONB,
  collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Resultados estruturados/processados
CREATE TABLE search_result_structured (
  id SERIAL PRIMARY KEY,
  search_result_raw_id INTEGER NOT NULL REFERENCES search_result_raw(id) ON DELETE CASCADE,
  category VARCHAR(50),
  title TEXT,
  date_found DATE,
  applicant TEXT,
  summary TEXT,
  structured_json JSONB
);

-- Log de operações (auditoria/tracking)
CREATE TABLE search_log (
  id SERIAL PRIMARY KEY,
  search_query_id INTEGER NOT NULL REFERENCES search_query(id) ON DELETE CASCADE,
  log_msg TEXT,
  log_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
