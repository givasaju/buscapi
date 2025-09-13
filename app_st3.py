# Buscapi v.1.0
# Aplicação Streamlit que consome o fluxo de análise com persistência de dados.

import streamlit as st
import pandas as pd
import os
import sys
from typing import Dict, Any
import json
from datetime import datetime
from database.persist_dados import BuscapiDB
import plotly.express as px
import plotly.io as pio
import plotly.graph_objects as go
import traceback

# Adiciona o diretório raiz do projeto ao path para garantir que as importações funcionem
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Importa o serviço de análise que usa o fluxo com persistência
from flows.ip_flow import IPAnalysisService
from tasks.pdf_worker import enqueue_pdf_job, get_job_meta

from agents.ip_agents import IPAgents

# Refatoração GPT5
def safe_json_loads(data, fallback):
    """Carrega JSON com segurança, aceita dict/list ou string JSON."""
    if isinstance(data, str):
        try:
            return json.loads(data)
        except Exception:
            return fallback
    return data if data else fallback

class StreamlitIPApp:
    """
    Aplicação Streamlit (UI) que consome o fluxo de análise com persistência de dados.
    """
    
    def __init__(self):
        """Inicializa a aplicação Streamlit."""
        self.setup_page_config()
        self.initialize_services()
        self.initialize_session_state()
    
    def setup_page_config(self):
        """Configura as propriedades básicas da página Streamlit."""
        st.set_page_config(
            page_title="Análise de Propriedade Intelectual",
            page_icon="🔍",
            layout="wide",
            initial_sidebar_state="expanded"
        )

    def inject_custom_css(self):
        """Injeta o CSS customizado para a aplicação."""
        st.markdown("""
        <style>
            /* Botões com largura total dentro das colunas */
            div.stButton > button {
                width: 100%;
                height: 100%;
            }
            /* Card para o histórico */
            .card {
                background-color: #e6f3ff; /* Azul suave */
                border: 1px solid #b8d8f5;
                border-radius: 7px;
                padding: 15px;
                margin-bottom: 10px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.24);
            }
            /* Divisor customizado */
            hr.styled-divider {
                border-top: 20px solid yellow;
                border-radius: 5px;
            }
        </style>
        """, unsafe_allow_html=True)

    def initialize_services(self):
        """Inicializa o serviço de análise e o gerador de PDF."""
        try:
            self.analysis_service = IPAnalysisService()
            # Importa o gerador de PDF de forma segura (evita falha de import quando dependências não estão instaladas)
            try:
                from tools.pdf_generator import PDFGenerator
                self.pdf_generator = PDFGenerator()
            except Exception:
                self.pdf_generator = None
            # Gerenciador de agentes (inclui o agente coordenador com LLMTool)
            try:
                self.ip_agents = IPAgents()
            except Exception:
                # Se não for possível instanciar agentes, prossegue sem LLM
                self.ip_agents = None
        except Exception as e:
            st.error(f"Erro ao inicializar serviços: {e}")
            st.code(traceback.format_exc())
            st.stop()
    
    def initialize_session_state(self):
        """Inicializa o estado da sessão."""
        if 'analysis_results' not in st.session_state:
            st.session_state.analysis_results = None
        if 'is_processing' not in st.session_state:
            st.session_state.is_processing = False
        if 'current_search' not in st.session_state:
            st.session_state.current_search = "Tecnologia de IA na Agricultura"
        if 'selected_query_id' not in st.session_state:
            st.session_state.selected_query_id = None
        if 'page' not in st.session_state:
            st.session_state.page = "Análise Principal"
        # Modelo LLM selecionado pelo usuário (override por execução). Se 'Env default', usa LLM_MODEL do .env
        if 'selected_llm_model' not in st.session_state:
            env_model = os.getenv('LLM_MODEL') or 'Env default'
            st.session_state.selected_llm_model = env_model
    
    def render_header(self):
        """Renderiza o cabeçalho da aplicação."""
        st.markdown('<h1 style="text-align: center;">🔍 Sistema de Análise de Propriedade Intelectual</h1>', unsafe_allow_html=True)
        # Indicadores rápidos de disponibilidade de funcionalidades
        try:
            if not getattr(self, 'ip_agents', None):
                st.warning("LLM indisponível: Recursos de geração de insights via LLM serão ocultos.")
            if not getattr(self, 'pdf_generator', None):
                st.info("Gerador de PDF indisponível: a exportação para PDF estará desabilitada até instalar dependências.")
        except Exception:
            pass

    def render_sidebar(self):
        """Renderiza a barra lateral com os controles."""
        st.sidebar.header("🔧 Controles de Pesquisa")
        # Seletor de modelo LLM (override por execução). 'Env default' usa o LLM_MODEL do .env
        llm_options = [
            'Env default',
            'gpt-5-nano',
            'gpt-4o-mini',
            'gpt-4o',
            'gpt-4o-realtime-preview',
            'gpt-4',
            'gpt-3.5-turbo'
        ]
        # Insere o valor atual no topo se não fizer parte das opções
        current = st.session_state.get('selected_llm_model') or 'Env default'
        if current not in llm_options:
            llm_options.insert(0, current)
        chosen = st.sidebar.selectbox('Modelo LLM (override)', options=llm_options, index=llm_options.index(current))
        st.session_state.selected_llm_model = chosen

        with st.sidebar.form("search_form"):
            search_criteria = st.text_area("Critérios de Busca:", value=st.session_state.current_search)
            submitted = st.form_submit_button("🚀 Iniciar Análise")
            if submitted and search_criteria.strip():
                self.run_analysis(search_criteria.strip())

    def run_analysis(self, search_criteria: str):
        """Dispara a análise usando o IPAnalysisService e atualiza a tela."""
        st.session_state.is_processing = True
        st.session_state.analysis_results = None
        
        with st.spinner("🔄 Executando fluxo de análise completo (com persistência no banco de dados)..."):
            try:
                # PASSO 1: REGISTRO - Cria a busca no DB e obtém o ID.
                # O método start_analysis retorna um ID inteiro ou levanta uma exceção em caso de falha.
                flow_id = self.analysis_service.start_analysis(search_criteria)

                # PASSO 2: EXECUÇÃO - Executa o crewai-flow usando o ID.
                results = self.analysis_service.execute_analysis(flow_id)
                if "error" in results:
                    st.error(f"Falha ao executar a análise: {results['error']}")
                    st.session_state.is_processing = False
                    return

                # PASSO 3: APRESENTAÇÃO (Tradução dos resultados)
                # O fluxo retorna os resultados das ferramentas como strings JSON.
                # Precisamos decodificá-los para objetos Python antes de usar na UI.
                
                # 3.1. Decodificar 'analysis_results' de string para dicionário         
                analysis_data = safe_json_loads(results.get('analysis_results'), {})
                classified_data = safe_json_loads(results.get('classified_data'), [])
                visualizations = safe_json_loads(results.get('visualizations'), {})

                
                # 3.3. Montar o dicionário final para a UI
                category_summary = analysis_data.get('count_by_category', {})
                insights = results.get('insights', 'Nenhum insight gerado.')
                
                ui_results = {
                    'search_criteria': search_criteria,
                    'data_collected': results.get('data_collected', 0),
                    'data_classified': len(classified_data),
                    'category_summary': category_summary,
                    'total_categories': len(category_summary),
                    'insights': insights,
                    'formatted_insights': insights.replace('. ', '.\n\n'),
                    'visualizations': results.get('visualizations', {}),
                    'success': True,
                    'flow_id': flow_id,
                    # Adiciona os dados já decodificados para uso em outras partes (PDF, detalhes)
                    'analysis_results': analysis_data,
                    'classified_data': classified_data
                }
                st.session_state.analysis_results = ui_results

            except Exception as e:
                st.error(f"Ocorreu um erro grave durante a execução do fluxo: {e}")
                st.code(traceback.format_exc())

        st.session_state.is_processing = False
        st.rerun()

    def render_results(self):
        """Renderiza o corpo principal da página com os resultados."""
        results = st.session_state.analysis_results
        if not results:
            st.info("👋 Bem-vindo! Use a barra lateral para iniciar uma nova análise.")
            return
        if not results.get('success', False):
            st.error(f"❌ Erro na análise: {results.get('error', 'Erro desconhecido')}")
            return
        
        st.header("📊 Resultados da Análise")
        self.render_metrics(results)
        self.render_insights(results)
        self.render_visualizations(results)
        self.render_export_options(results)

    def render_metrics(self, results: Dict[str, Any]):
        st.subheader("📈 Métricas Principais")
        col1, col2, col3, col4 = st.columns(4)

        # Dados coletados podem vir como inteiro (contagem) ou lista de itens
        data_collected = results.get('data_collected', 0)
        if isinstance(data_collected, int):
            collected_count = data_collected
        else:
            try:
                collected_count = len(data_collected)
            except Exception:
                collected_count = 0

        # Classified data pode estar sob 'classified_data' (lista) ou 'data_classified' (contagem)
        classified = results.get('classified_data', results.get('data_classified', []))
        if isinstance(classified, int):
            classified_count = classified
        else:
            try:
                classified_count = len(classified)
            except Exception:
                classified_count = 0

        # Visualizações e análises: contar chaves ou entradas
        viz = results.get('visualizations', {})
        try:
            viz_count = len(viz) if viz else 0
        except Exception:
            viz_count = 0

        analysis = results.get('analysis_results', {})
        try:
            analysis_count = len(analysis) if analysis else 0
        except Exception:
            analysis_count = 0

        col1.metric("Dados Coletados", collected_count)
        col2.metric("Classificados", classified_count)
        col3.metric("Visualizações", viz_count)
        col4.metric("Análises", analysis_count)
    
    def render_insights(self, results: Dict[str, Any]):
        st.subheader("💡 Insights e Conclusões")
        st.markdown(results.get('formatted_insights', 'Nenhum insight gerado.'))
        
        # Botão para geração de insights via LLM (somente disponível se o agente coordenador estiver disponível)
        try:
            if hasattr(self, 'ip_agents') and self.ip_agents:
                if st.button("🤖 Gerar insights (LLM)"):
                    # Dados para enviar à LLM
                    analysis = results.get('analysis_results', {}) or {}
                    classified = results.get('classified_data', []) or []
                    flow_id = results.get('flow_id')

                    with st.spinner("Gerando insights via LLM..."):
                        try:
                            # Recupera seleção de modelo (se 'Env default', passa None para usar LLM_MODEL do .env)
                            sel_model = st.session_state.get('selected_llm_model')
                            model_param = None if not sel_model or sel_model == 'Env default' else sel_model
                            insights = self.ip_agents.generate_insights_via_llm(analysis=analysis, classified=classified, model=model_param)
                            if insights:
                                # Atualiza sessão e exibe
                                formatted = insights.replace('. ', '.\n\n')
                                st.success("Insights gerados com sucesso.")
                                st.markdown(formatted)
                                # Atualiza o estado para permitir exportação
                                st.session_state.analysis_results = st.session_state.analysis_results or {}
                                st.session_state.analysis_results['insights'] = insights
                                st.session_state.analysis_results['formatted_insights'] = formatted

                                # Persiste um log curto no banco de dados
                                try:
                                    if flow_id:
                                        db = BuscapiDB()
                                        db.insert_search_log(flow_id, f"LLM insights: {insights[:3000]}")
                                        db.close()
                                except Exception as e:
                                    st.warning(f"Não foi possível persistir os insights no banco: {e}")
                            else:
                                st.info("Nenhum insight gerado ou LLM indisponível.")
                        except Exception as e:
                            st.error(f"Erro ao gerar insights via LLM: {e}")
        except Exception:
            # Segurança: não impedirá a renderização caso algo falhe
            pass

    def render_visualizations(self, results: Dict[str, Any]):
        st.subheader("📊 Visualizações")
        # A chave 'visualizations' agora contém um dicionário com os JSONs dos gráficos
        viz_data = results.get('visualizations', {})
        # <#> if viz_data:
        # <#>     for viz_name, viz_json in viz_data.items():
        # <#>         # Garante dict para uso
        # <#>         if isinstance(viz_json, str):
        # <#>             viz_data = json.loads(viz_json)
        # <#>         else:
        # <#>             viz_data = viz_json
        # <#> try:
        # <#>     fig = pio.from_json(viz_json if isinstance(viz_json, str) else json.dumps(viz_json))
        # <#>     st.plotly_chart(fig, use_container_width=True)
        # <#> except Exception as e:
        # <#>     st.error(f"Erro ao renderizar visualização {viz_name}: {e}")
        if not viz_data:
            st.info("Nenhuma visualização disponível.")
            return

        for viz_name, viz_json in viz_data.items():
            try:
                fig = None

                # Caso: string JSON que representa uma figura Plotly
                if isinstance(viz_json, str):
                    try:
                        fig = pio.from_json(viz_json)
                    except Exception:
                        # tentar carregar como dict
                        parsed = json.loads(viz_json)
                        if isinstance(parsed, dict):
                            fig = go.Figure(parsed)
                        elif isinstance(parsed, list):
                            fig = go.Figure(data=parsed)

                # Caso: já é um dict (pode ser figura completa ou dict de traces)
                elif isinstance(viz_json, dict):
                    try:
                        fig = go.Figure(viz_json)
                    except Exception:
                        # fallback: se dict contém 'data'/'layout'
                        fig = go.Figure(data=viz_json.get('data', []), layout=viz_json.get('layout', {}))

                # Caso: lista de traces
                elif isinstance(viz_json, list):
                    fig = go.Figure(data=viz_json)

                # Se por algum motivo ainda não temos figura, falha explicitamente
                if fig is None:
                    raise ValueError('Formato de visualização desconhecido')

                st.plotly_chart(fig, use_container_width=True, key=f"viz_{viz_name}")
            except Exception as e:
                viz_label = viz_name if 'viz_name' in locals() else '<unknown>'
                st.error(f"Erro ao renderizar visualização {viz_label}: {e}")

    def render_export_options(self, results: Dict[str, Any]):
        """Renderiza o botão de exportação e chama o método de geração de PDF."""
        st.subheader("📄 Opções de Exportação")
        # Ao invés de bloquear a UI gerando o PDF na hora, enfileiramos um job e retornamos job_id
        if st.button("📄 Gerar Relatório PDF (background)", type="primary"):
            try:
                # Gera um arquivo temporário com imagens localmente antes de enfileirar
                # Reusa a lógica de criação de imagens (mesma que estava em generate_pdf_and_download)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                temp_image_dir = os.path.join("static", "temp_images")
                os.makedirs(temp_image_dir, exist_ok=True)

                image_paths = {}
                viz_data = results.get('visualizations', {}) or {}
                for viz_name, viz_json in viz_data.items():
                    try:
                        fig = None
                        if isinstance(viz_json, str):
                            try:
                                fig = pio.from_json(viz_json)
                            except Exception:
                                parsed = json.loads(viz_json)
                                if isinstance(parsed, dict):
                                    fig = go.Figure(parsed)
                                elif isinstance(parsed, list):
                                    fig = go.Figure(data=parsed)
                        elif isinstance(viz_json, dict):
                            try:
                                fig = go.Figure(viz_json)
                            except Exception:
                                fig = go.Figure(data=viz_json.get('data', []), layout=viz_json.get('layout', {}))
                        elif isinstance(viz_json, list):
                            fig = go.Figure(data=viz_json)

                        if fig is None:
                            continue

                        img_path = os.path.join(temp_image_dir, f"{viz_name}_{timestamp}.png")
                        try:
                            fig.write_image(img_path, scale=2)
                            image_paths[viz_name] = img_path
                        except Exception as e:
                            print(f"Erro ao gerar imagem para PDF '{viz_name}': {e}")
                    except Exception as e:
                        print(f"Erro ao processar visualização '{viz_name}' para PDF: {e}")

                # Prepara o payload de results para o gerador de PDF
                results_for_pdf = results.copy()
                results_for_pdf['visualizations'] = image_paths

                job_meta = enqueue_pdf_job(results_for_pdf, search_query_id=results.get('flow_id'))
                st.success(f"PDF enfileirado. Job ID: {job_meta.get('job_id')}")
                st.info("Use a seção 'Histórico / Detalhes' para checar o status e baixar quando pronto.")
            except Exception as e:
                st.error(f"Erro ao enfileirar PDF: {e}")

        # Pequena UI para checar um job_id diretamente
        with st.expander("🔎 Checar status do job PDF"):
            jid = st.text_input("Job ID:", value="", key='check_pdf_job_id')
            if st.button("Checar status", key='check_pdf_job_btn'):
                if not jid:
                    st.warning("Informe um Job ID válido.")
                else:
                    meta = get_job_meta(jid)
                    st.json(meta)
                    if meta.get('status') == 'completed' and meta.get('output_path'):
                        try:
                            with open(meta.get('output_path'), 'rb') as f:
                                st.download_button(label='Baixar PDF gerado', data=f.read(), file_name=os.path.basename(meta.get('output_path')))
                        except Exception as e:
                            st.error(f"Falha ao abrir arquivo para download: {e}")

    def generate_pdf_and_download(self, results: Dict[str, Any]):
        """Gera o PDF e fornece o botão de download."""
        try:
            with st.spinner("📄 Gerando relatório PDF..."):
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                pdf_filename = f"relatorio_buscapi_{timestamp}.pdf"
                pdf_output_path = os.path.join("static", pdf_filename)
                
                # --- Lógica para recriar imagens para o PDF ---
                image_paths = {}
                viz_data = results.get('visualizations', {})
                temp_image_dir = os.path.join("static", "temp_images")
                os.makedirs(temp_image_dir, exist_ok=True)

                for viz_name, viz_json in viz_data.items():
                    try:
                        # Reusar a mesma lógica de renderização para criar a figura
                        fig = None
                        if isinstance(viz_json, str):
                            try:
                                fig = pio.from_json(viz_json)
                            except Exception:
                                parsed = json.loads(viz_json)
                                if isinstance(parsed, dict):
                                    fig = go.Figure(parsed)
                                elif isinstance(parsed, list):
                                    fig = go.Figure(data=parsed)
                        elif isinstance(viz_json, dict):
                            try:
                                fig = go.Figure(viz_json)
                            except Exception:
                                fig = go.Figure(data=viz_json.get('data', []), layout=viz_json.get('layout', {}))
                        elif isinstance(viz_json, list):
                            fig = go.Figure(data=viz_json)

                        if fig is None:
                            st.warning(f"Visualização {viz_name} não pôde ser convertida para Plotly.")
                            continue

                        # Exibe no Streamlit como pré-visualização no processo de geração do PDF
                        st.plotly_chart(fig, use_container_width=True, key=f"pdf_viz_{viz_name}_{timestamp}")

                        try:
                            img_path = os.path.join(temp_image_dir, f"{viz_name}_{timestamp}.png")
                            fig.write_image(img_path, scale=2)
                            image_paths[viz_name] = img_path
                        except Exception as e:
                            print(f"Erro ao gerar imagem para PDF '{viz_name}': {e}")
                            # não interrompe o loop: continua com próximas visualizações
                    except Exception as e:
                        print(f"Erro ao processar visualização '{viz_name}' para PDF: {e}")
                
                # Atualiza o dicionário de resultados com os caminhos das imagens para o gerador de PDF
                results_for_pdf = results.copy()
                results_for_pdf['visualizations'] = image_paths
                self.pdf_generator.generate_report(results_for_pdf, pdf_output_path)
            
            with open(pdf_output_path, "rb") as pdf_file:
                st.download_button(
                    label="Clique para baixar o PDF",
                    data=pdf_file.read(),
                    file_name=os.path.basename(pdf_output_path),
                    mime="application/pdf"
                )
        except Exception as e:
            st.error(f"❌ Erro ao gerar relatório PDF: {e}")

    def render_history_sidebar(self):
        """Renderiza controles específicos para a página de histórico."""
        st.sidebar.header("📋 Controles do Histórico")
        
        with st.sidebar.expander("🔍 Filtros", expanded=True):
            st.date_input("Filtrar por data:", key='date_filter', help="Deixe em branco para ver todos os registros")
            st.selectbox("Filtrar por status:", options=["Todos", "Concluído", "Em andamento", "Erro"], key='status_filter')
        
        st.sidebar.markdown("### ⚡ Ações Rápidas")
        if st.sidebar.button("🔄 Atualizar Lista", help="Recarrega os dados do histórico"):
            st.rerun()
        
        if st.sidebar.button("🗑️ Limpar Seleção", help="Remove a seleção atual"):
            if 'selected_query_id' in st.session_state:
                del st.session_state.selected_query_id
            if 'history_selector' in st.session_state:
                del st.session_state.history_selector
            st.rerun()
        
        try:
            db = BuscapiDB()
            all_queries = db.get_all_search_queries()
            total_searches = len(all_queries) if all_queries else 0
            try:
                recent_searches = db.count_recent_searches(days=7) if hasattr(db, 'count_recent_searches') else 0
            except:
                recent_searches = 0
            db.close()
            
            st.sidebar.markdown("### 📊 Estatísticas")
            st.sidebar.metric("Total de Buscas", total_searches)
            st.sidebar.metric("Últimos 7 dias", recent_searches)
            
        except Exception as e:
            st.sidebar.error(f"Erro ao carregar estatísticas: {e}")
        
        st.sidebar.markdown("---")
        st.sidebar.markdown("**💡 Dicas:**")
        st.sidebar.markdown("• Clique em uma busca para ver detalhes")
        st.sidebar.markdown("• Use 'Executar Novamente' para repetir uma análise")
        st.sidebar.markdown("• Os resultados são salvos automaticamente")

    def render_history_page(self):
        """Renderiza a página com o histórico de buscas em formato de cards."""
        st.header("📜 Histórico de Buscas Registradas")
        st.info(f"Última atualização: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")

        try:
            db = BuscapiDB()
            history_data = db.get_all_search_queries()
            db.close()
            
            if not history_data:
                st.info("Nenhum registro de busca encontrado.")
                return

            df = pd.DataFrame(history_data)

            if 'date_filter' in st.session_state and st.session_state.date_filter is not None:
                df['created_at_date'] = pd.to_datetime(df['created_at']).dt.date
                if st.session_state.date_filter:
                    df = df[df['created_at_date'] == st.session_state.date_filter]

            if 'status_filter' in st.session_state and st.session_state.status_filter != "Todos":
                df = df[df['status'] == st.session_state.status_filter]
            
            if df.empty:
                st.warning("Nenhum registro encontrado com os filtros aplicados.")
                return

            for index, row in df.iloc[::-1].iterrows():
                with st.container():
                    st.markdown('<div class="card" >' , unsafe_allow_html=True)
                    
                    main_col, btn_col = st.columns([3, 1])
                    
                    with main_col:
                        st.markdown(f"**Critério:** `{row['criteria']}`")
                        st.caption(f"ID: {row['id']} | Data: {pd.to_datetime(row['created_at']).strftime('%d/%m/%Y %H:%M')} | Status: {row['status']}")
                    
                    with btn_col:
                        btn1, btn2 = st.columns(2)
                        with btn1:
                            if st.button("👁️", key=f"details_{row['id']}", help="Ver Detalhes"):
                                st.session_state.selected_query_id = row['id']
                                st.rerun()
                        with btn2:
                            if st.button("🔄", key=f"rerun_{row['id']}", help="Executar Novamente"):
                                st.session_state.current_search = row['criteria']
                                st.session_state.page = "Análise Principal"
                                st.rerun()
                    
                    st.markdown('</div>', unsafe_allow_html=True)

        except Exception as e:
            st.error(f"❌ Erro ao buscar histórico: {e}")
            st.code(traceback.format_exc())

    def render_details_page(self):
        """Renderiza a página de detalhes para uma busca específica."""
        query_id = st.session_state.selected_query_id
        
        if not query_id:
            st.warning("Selecione uma busca no Histórico para ver os detalhes.")
            if st.button("⬅️ Voltar para o Histórico"):
                st.session_state.selected_query_id = None
                st.rerun()
            return

        st.header(f"📄 Detalhes da Busca ID: {query_id}")
        if st.button("⬅️ Voltar para o Histórico"):
            st.session_state.selected_query_id = None
            st.rerun()
            return

        try:
            db = BuscapiDB()
            query_info = db.get_search_query_by_id(query_id)
            # NOTA: Este método agora deve buscar os dados da tabela 'search_result_structured'
            # e retornar a coluna 'structured_json' como uma lista de dicionários.
            structured_results = db.get_structured_results_by_query_id(query_id)
            db.close()

            if query_info:
                st.info(f"**Critério de Busca:** {query_info.get('criteria', 'N/A')}")

            if not structured_results:
                st.info("Nenhum resultado estruturado encontrado para esta busca.")
                return

            # Os dados já vêm processados do banco. Não é necessário reprocessar.
            all_results = structured_results
            if not all_results:
                st.warning("Nenhum item de resultado pôde ser extraído dos dados brutos.")
                return

            st.write(f"**Resultados encontrados e classificados:** {len(all_results)}")

            results_by_category = {}
            for result in all_results:
                category = result.get('category', 'Sem Categoria')
                if category not in results_by_category:
                    results_by_category[category] = []
                results_by_category[category].append(result)

            for category, results in results_by_category.items():
                with st.expander(f"📂 {category} ({len(results)} resultados)", expanded=True):
                    for i, result in enumerate(results):
                        with st.container():
                            title = result.get('title', 'Título não disponível')
                            applicant = result.get('applicantName', 'Não informado')
                            summary = result.get('snippet') or result.get('abstract', 'Não disponível')
                            app_number = result.get('applicationNumber')
                            pub_number = result.get('publicationNumber')
                            source = result.get('source', 'Desconhecida')
                            url = result.get('link') or result.get('url')
                            ipc_code = result.get('ipcCode')
                            filing_date = result.get('filingDate')
                            pub_date = result.get('publicationDate') or result.get('date')

                            def format_date(date_val):
                                if not date_val: return 'N/A'
                                try:
                                    return pd.to_datetime(date_val).strftime('%d/%m/%Y')
                                except (ValueError, TypeError):
                                    return str(date_val)

                            # Exibe as novas entidades extraídas
                            organizations = result.get('extracted_organizations', [])
                            persons = result.get('extracted_persons', [])

                            if organizations:
                                st.markdown(f"**🏢 Organizações Identificadas:** ` {', '.join(organizations)} `")
                            if persons:
                                st.markdown(f"**👤 Pessoas/Inventores Identificados:** ` {', '.join(persons)} `")

                            st.markdown(f"**{i+1}. {title}**")
                            st.markdown(f"**Fonte:** {source}")

                            col1, col2 = st.columns(2)
                            with col1:
                                st.markdown(f"**Requerente:** {applicant}")
                                if app_number: st.markdown(f"**Nº do Pedido:** {app_number}")
                                if pub_number: st.markdown(f"**Nº do Documento:** {pub_number}")
                            with col2:
                                st.markdown(f"**Data de Publicação:** {format_date(pub_date)}")
                                if filing_date: st.markdown(f"**Data do Pedido:** {format_date(filing_date)}")
                                if ipc_code: st.markdown(f"**Código IPC:** {ipc_code}")
                            
                            if summary:
                                st.markdown("**Resumo:**")
                                st.markdown(f"> {summary}")
                            
                            if url:
                                st.markdown(f"🔗 [Ver documento original]({url})")
                            
                            st.divider()

            # --- Seção: Relatórios PDF gerados para esta busca ---
            try:
                st.subheader("📎 Relatórios PDF gerados")
                pdf_jobs_dir = os.path.join("static", "pdf_jobs")
                found = []
                if os.path.isdir(pdf_jobs_dir):
                    for fname in sorted(os.listdir(pdf_jobs_dir), reverse=True):
                        if not fname.lower().endswith('.json'):
                            continue
                        fpath = os.path.join(pdf_jobs_dir, fname)
                        try:
                            with open(fpath, 'r', encoding='utf-8') as f:
                                meta = json.load(f)
                            if meta.get('search_query_id') == query_id:
                                found.append(meta)
                        except Exception:
                            continue

                if not found:
                    st.info("Nenhum relatório PDF encontrado para esta busca.")
                else:
                    for meta in found:
                        st.markdown(f"**Job ID:** `{meta.get('job_id')}` — Status: **{meta.get('status')}**")
                        op = meta.get('output_path')
                        if meta.get('status') == 'completed' and op and os.path.exists(op):
                            try:
                                with open(op, 'rb') as f:
                                    st.download_button(label=f"Baixar {os.path.basename(op)}", data=f.read(), file_name=os.path.basename(op))
                            except Exception as e:
                                st.error(f"Falha ao abrir PDF para download: {e}")
                        else:
                            if op:
                                st.write(f"Caminho do arquivo: {op}")
                            st.write("Aguardando geração ou falha registrada.")
            except Exception as e:
                st.error(f"Erro ao recuperar relatórios PDF: {e}")

        except Exception as e:
            st.error(f"❌ Erro ao buscar detalhes da busca: {e}")
            st.code(traceback.format_exc())

    def run(self):
        """Executa a renderização da UI."""
        self.inject_custom_css()
        self.render_header()
        
        st.sidebar.markdown("---")
        page_options = ("Análise Principal", "Histórico de Buscas")
        if 'page' not in st.session_state or st.session_state.page not in page_options:
            st.session_state.page = "Análise Principal"            
        page = st.sidebar.radio("🧭 Navegação", page_options, index=page_options.index(st.session_state.page))
        st.session_state.page = page        
        if page == "Análise Principal":
            self.render_sidebar()
            self.render_results()
        elif page == "Histórico de Buscas":
            if st.session_state.get('selected_query_id'):
                self.render_details_page()
            else:
                self.render_history_sidebar()
                self.render_history_page()

def main():
    """Função principal."""
    app = StreamlitIPApp()
    app.run()

if __name__ == "__main__":
    main()
