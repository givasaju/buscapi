import streamlit as st
import pandas as pd
import os
import sys
from typing import Dict, Any
from datetime import datetime
from database.persist_dados import BuscapiDB
import plotly.express as px
import traceback

# Adiciona o diretório raiz do projeto ao path para garantir que as importações funcionem
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tools_processor import CustomToolsProcessor
from tools.pdf_generator import PDFGenerator

class StreamlitIPApp:
    """
    Aplicação Streamlit (UI) que consome dados do CustomToolsProcessor
    e orquestra a geração de relatórios com PDFGenerator.
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
        st.markdown("""<style>/* ... CSS ... */</style>""", unsafe_allow_html=True)

    def initialize_services(self):
        """A UI agora gerencia o processador de dados e o gerador de PDF."""
        try:
            self.processor = CustomToolsProcessor()
            self.pdf_generator = PDFGenerator()
        except Exception as e:
            st.error(f"Erro ao inicializar serviços: {e}")
            st.stop()
    
    def initialize_session_state(self):
        """Inicializa o estado da sessão."""
        if 'analysis_results' not in st.session_state:
            st.session_state.analysis_results = None
        if 'is_processing' not in st.session_state:
            st.session_state.is_processing = False
        if 'search_history' not in st.session_state:
            st.session_state.search_history = []
        if 'current_search' not in st.session_state:
            st.session_state.current_search = "Tecnologia de IA na Agricultura"
        if 'selected_query_id' not in st.session_state:
            st.session_state.selected_query_id = None
        if 'page' not in st.session_state:
            st.session_state.page = "Análise Principal"
    
    def render_header(self):
        """Renderiza o cabeçalho da aplicação."""
        st.markdown('<h1 style="text-align: center;">🔍 Sistema de Análise de Propriedade Intelectual</h1>', unsafe_allow_html=True)

    def render_sidebar(self):
        """Renderiza a barra lateral com os controles."""
        st.sidebar.header("🔧 Controles de Pesquisa")
        with st.sidebar.form("search_form"):
            search_criteria = st.text_area("Critérios de Busca:", value=st.session_state.current_search)
            submitted = st.form_submit_button("🚀 Iniciar Análise")
            if submitted and search_criteria.strip():
                self.run_analysis(search_criteria.strip())

    def run_analysis(self, search_criteria: str):
        """Dispara a análise e atualiza a tela."""
        st.session_state.is_processing = True
        st.session_state.analysis_results = None
        with st.spinner("🔄 Executando análise completa..."):
            results = self.processor.run_analysis_for_ui(search_criteria)
        st.session_state.analysis_results = results
        if results.get('success') and search_criteria not in st.session_state.search_history:
            st.session_state.search_history.append(search_criteria)
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
        self.render_category_analysis(results)
        self.render_insights(results)
        self.render_visualizations(results)
        self.render_export_options(results)

    def render_metrics(self, results: Dict[str, Any]):
        st.subheader("📈 Métricas Principais")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Dados Coletados", results.get('data_collected', 0))
        col2.metric("Dados Classificados", results.get('data_classified', 0))
        col3.metric("Categorias", results.get('total_categories', 0))
        col4.metric("Visualizações", len(results.get('visualizations', {})))
    
    def render_category_analysis(self, results: Dict[str, Any]):
        st.subheader("🏷️ Análise por Categorias")
        category_summary = results.get('category_summary', {})
        if category_summary:
            df = pd.DataFrame(list(category_summary.items()), columns=['Categoria', 'Quantidade'])
            fig = px.pie(df, values='Quantidade', names='Categoria', title='Distribuição por Categorias')
            st.plotly_chart(fig, use_container_width=True)

    def render_insights(self, results: Dict[str, Any]):
        st.subheader("💡 Insights e Conclusões")
        st.markdown(results.get('formatted_insights', 'Nenhum insight gerado.'))

    def render_visualizations(self, results: Dict[str, Any]):
        st.subheader("📊 Visualizações")
        visualizations = results.get('visualizations', {})
        if visualizations:
            for viz_name, viz_path in visualizations.items():
                if os.path.exists(viz_path):
                    st.image(viz_path, use_column_width=True)
        else:
            st.info("Nenhuma visualização foi gerada para esta análise.")

    def render_export_options(self, results: Dict[str, Any]):
        """Renderiza o botão de exportação e chama o método de geração de PDF."""
        st.subheader("📄 Opções de Exportação")
        if st.button("📄 Gerar Relatório PDF", type="primary"):
            self.generate_pdf_and_download(results)

    def generate_pdf_and_download(self, results: Dict[str, Any]):
        """Gera o PDF e fornece o botão de download."""
        try:
            with st.spinner("📄 Gerando relatório PDF..."):
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                pdf_filename = f"relatorio_{timestamp}.pdf"
                output_path = os.path.join("static", pdf_filename)
                os.makedirs("static", exist_ok=True)
                
                self.pdf_generator.generate_report(results, output_path)
            
            with open(output_path, "rb") as pdf_file:
                st.download_button(
                    label="Clique para baixar o PDF",
                    data=pdf_file.read(),
                    file_name=os.path.basename(output_path),
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
        """Renderiza a página com o histórico de buscas."""
        st.header("📜 Histórico de Buscas Registradas")
        
        try:
            db = BuscapiDB()
            history_data = db.get_all_search_queries()
            db.close()
            
            if not history_data:
                st.info("Nenhum registro de busca encontrado.")
                return

            df = pd.DataFrame(history_data)

            # Lógica de filtro aplicada aqui
            if 'date_filter' in st.session_state and st.session_state.date_filter is not None:
                df = df[pd.to_datetime(df['created_at']).dt.date == st.session_state.date_filter]

            if 'status_filter' in st.session_state and st.session_state.status_filter != "Todos":
                df = df[df['status'] == st.session_state.status_filter]
            
            if df.empty:
                st.warning("Nenhum registro encontrado com os filtros aplicados.")
                return

            col1, col2, col3 = st.columns(3)
            col1.metric("Total de Buscas", len(df))
            
            if 'status' in df.columns:
                success_count = len(df[df['status'] == 'Concluído'])
                col2.metric("Buscas Concluídas", success_count)
                success_rate = f"{(success_count/len(df)*100):.1f}%" if len(df) > 0 else "0%"
                col3.metric("Taxa de Sucesso", success_rate)
            
            st.subheader("📋 Lista de Buscas")
            column_config = {
                "id": st.column_config.NumberColumn("ID", width="small"),
                "criteria": st.column_config.TextColumn("Critério de Busca", width="large"),
                "created_at": st.column_config.DatetimeColumn("Data", format="DD/MM/YYYY HH:mm"),
                "status": st.column_config.TextColumn("Status", width="medium")
            }
            
            display_df = df.head(20) if len(df) > 20 else df
            st.dataframe(display_df, column_config=column_config, use_container_width=True, hide_index=True)
            
            st.markdown("---")
            st.subheader("🔍 Ver Detalhes de uma Busca")
            
            if not df.empty:
                options = [f"ID {row['id']} - {row['criteria'][:50]}... ({pd.to_datetime(row['created_at']).strftime('%d/%m')})" for _, row in df.iterrows()]
                selected_option = st.selectbox("Selecione uma busca:", options=["Selecione uma busca..."] + options, key="history_selector")
                
                if selected_option != "Selecione uma busca...":
                    selected_id = int(selected_option.split(" - ")[0].replace("ID ", ""))
                    
                    col1, col2, col3, col4 = st.columns([1, 1, 1, 2])
                    if col1.button("👁️ Ver Detalhes", type="primary"):
                        st.session_state.selected_query_id = selected_id
                        st.rerun()
                    
                    if col2.button("🔄 Executar Novamente", type="primary"):
                        selected_row = df[df['id'] == selected_id].iloc[0]
                        st.session_state.current_search = selected_row['criteria']
                        st.session_state.page = "Análise Principal"
                        st.rerun()

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
            api_responses = db.get_structured_results_by_query_id(query_id)
            db.close()

            if query_info:
                st.info(f"**Critério de Busca:** {query_info.get('criteria', 'N/A')}")

            if not api_responses:
                st.info("Nenhum resultado estruturado encontrado para esta busca.")
                return

            # Aplaina a lista de resultados de todas as respostas da API
            all_results = []
            for response in api_responses:
                if not isinstance(response, dict):
                    continue
                
                # Lógica para desempacotar resultados do Serper
                if 'organic' in response and isinstance(response['organic'], list):
                    for item in response['organic']:
                        item['source'] = response.get('searchParameters', {}).get('engine', 'Serper')
                        item['category'] = response.get('category', 'Outros')
                        all_results.append(item)
                    continue

                # Lógica para desempacotar resultados da EPO
                epo_docs = response.get('ops:world-patent-data', {}).get('ops:register-search', {}).get('reg:register-documents', {}).get('reg:register-document', [])
                if epo_docs:
                    if isinstance(epo_docs, dict):
                        epo_docs = [epo_docs]
                    
                    for doc in epo_docs:
                        bib_data = doc.get('reg:bibliographic-data', {})
                        if not bib_data: continue

                        flat_item = {
                            'source': 'EPO',
                            'category': response.get('category', 'Outros')
                        }

                        titles = bib_data.get('reg:invention-title', [])
                        if isinstance(titles, dict): titles = [titles]
                        eng_title = next((t.get('$') for t in titles if t.get('@lang') == 'en'), None)
                        flat_item['title'] = eng_title or (titles[0].get('$') if titles else 'N/A')

                        try:
                            applicants = bib_data.get('reg:parties', {}).get('reg:applicants', {}).get('reg:applicant', [])
                            if isinstance(applicants, dict): applicants = [applicants]
                            flat_item['applicantName'] = applicants[0].get('reg:addressbook', {}).get('reg:name', {}).get('$')
                        except (IndexError, KeyError, TypeError):
                            flat_item['applicantName'] = 'Não informado'

                        try:
                            flat_item['publicationDate'] = bib_data.get('reg:publication-reference', {}).get('reg:document-id', {}).get('reg:date', {}).get('$')
                        except KeyError:
                            pass
                        
                        try:
                            flat_item['applicationDate'] = bib_data.get('reg:application-reference', {}).get('reg:document-id', {}).get('reg:date', {}).get('$')
                        except KeyError:
                            pass

                        try:
                            flat_item['applicationNumber'] = bib_data.get('reg:application-reference', {}).get('reg:document-id', {}).get('reg:doc-number', {}).get('$')
                        except KeyError:
                            pass

                        try:
                            flat_item['publicationNumber'] = bib_data.get('reg:publication-reference', {}).get('reg:document-id', {}).get('reg:doc-number', {}).get('$')
                        except KeyError:
                            pass

                        try:
                            flat_item['ipcCode'] = bib_data.get('reg:classifications-ipcr', {}).get('reg:classification-ipcr', {}).get('reg:text', {}).get('$')
                        except KeyError:
                            pass

                        abstracts = bib_data.get('reg:abstract', [])
                        if isinstance(abstracts, dict): abstracts = [abstracts]
                        eng_abstract = next((a.get('$') for a in abstracts if a.get('@lang') == 'en'), None)
                        flat_item['abstract'] = eng_abstract or (abstracts[0].get('$') if abstracts else None)
                        
                        all_results.append(flat_item)
                    continue

                if 'title' in response:
                    all_results.append(response)

            st.write(f"**Resultados encontrados:** {len(all_results)}")

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
                            # --- Extração e Renderização Unificada ---
                            title = result.get('title', 'Título não disponível')
                            applicant = result.get('applicantName', 'Não informado')
                            pub_date = result.get('publicationDate') or result.get('date')
                            app_date = result.get('applicationDate')
                            summary = result.get('snippet') or result.get('abstract', 'Não disponível')
                            app_number = result.get('applicationNumber')
                            pub_number = result.get('publicationNumber')
                            source = result.get('source', 'Desconhecida')
                            url = result.get('link') or result.get('url')
                            ipc_code = result.get('ipcCode')

                            def format_date(date_val):
                                if not date_val: return 'N/A'
                                try:
                                    return pd.to_datetime(date_val).strftime('%d/%m/%Y')
                                except (ValueError, TypeError):
                                    return str(date_val)

                            st.markdown(f"**{i+1}. {title}**")
                            st.markdown(f"**Fonte:** {source}")

                            col1, col2 = st.columns(2)
                            with col1:
                                st.markdown(f"**Requerente:** {applicant}")
                                if app_number: st.markdown(f"**Nº do Pedido:** {app_number}")
                                if pub_number: st.markdown(f"**Nº do Documento:** {pub_number}")
                            with col2:
                                st.markdown(f"**Data de Publicação:** {format_date(pub_date)}")
                                if app_date: st.markdown(f"**Data do Pedido:** {format_date(app_date)}")
                                if ipc_code: st.markdown(f"**Código IPC:** {ipc_code}")
                            
                            if summary:
                                st.markdown("**Resumo:**")
                                st.markdown(f"> {summary}")
                            
                            if url:
                                st.markdown(f"🔗 [Ver documento original]({url})")
                            
                            st.divider()

        except Exception as e:
            st.error(f"❌ Erro ao buscar detalhes da busca: {e}")
            st.code(traceback.format_exc())

    def run(self):
        """Executa a renderização da UI."""
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
