"""
Gerador de PDF para Relatórios de Propriedade Intelectual
Classe responsável por criar relatórios em PDF dos resultados de análise
"""

import os
from datetime import datetime
from typing import Dict, Any, List
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY


class PDFGenerator:
    """
    Gerador de relatórios PDF para análises de propriedade intelectual.
    
    Esta classe é responsável por:
    - Formatar dados de análise para PDF
    - Criar documentos PDF estruturados
    - Incluir visualizações e tabelas
    - Gerar relatórios profissionais
    """
    
    def __init__(self):
        """Inicializa o gerador de PDF com estilos padrão."""
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
    
    def _setup_custom_styles(self):
        """
        Configura estilos personalizados para o PDF.
        
        Define estilos customizados para diferentes elementos do relatório:
        - Título principal
        - Subtítulos
        - Texto normal
        - Cabeçalhos de seção
        """
        # Estilo para título principal
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Title'],
            fontSize=24,
            spaceAfter=30,
            alignment=TA_CENTER,
            textColor=colors.darkblue
        ))
        
        # Estilo para subtítulos
        self.styles.add(ParagraphStyle(
            name='CustomSubtitle',
            parent=self.styles['Heading1'],
            fontSize=16,
            spaceAfter=12,
            spaceBefore=20,
            textColor=colors.darkblue
        ))
        
        # Estilo para cabeçalhos de seção
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=14,
            spaceAfter=10,
            spaceBefore=15,
            textColor=colors.darkgreen
        ))
        
        # Estilo para texto justificado
        self.styles.add(ParagraphStyle(
            name='JustifiedText',
            parent=self.styles['Normal'],
            alignment=TA_JUSTIFY,
            spaceAfter=6
        ))
    
    def generate_report(self, analysis_results: Dict[str, Any], output_path: str) -> str:
        """
        Gera um relatório PDF completo com os resultados da análise.
        
        Este método é o ponto de entrada principal para geração de PDF. Ele:
        1. Cria a estrutura do documento
        2. Adiciona todas as seções do relatório
        3. Inclui visualizações se disponíveis
        4. Salva o arquivo PDF
        
        Args:
            analysis_results: Dicionário com todos os resultados da análise
            output_path: Caminho onde o PDF será salvo
            
        Returns:
            Caminho do arquivo PDF gerado
        """
        try:
            # Criar o documento PDF
            doc = SimpleDocTemplate(
                output_path,
                pagesize=A4,
                rightMargin=72,
                leftMargin=72,
                topMargin=72,
                bottomMargin=18
            )
            
            # Lista para armazenar todos os elementos do documento
            story = []
            
            # Adicionar seções do relatório
            self._add_title_section(story, analysis_results)
            self._add_summary_section(story, analysis_results)
            self._add_data_overview_section(story, analysis_results)
            self._add_category_analysis_section(story, analysis_results)
            self._add_insights_section(story, analysis_results)
            self._add_visualizations_section(story, analysis_results)
            self._add_detailed_results_section(story, analysis_results)
            
            # Construir o PDF
            doc.build(story)
            
            print(f"✅ Relatório PDF gerado com sucesso: {output_path}")
            return output_path
            
        except Exception as e:
            error_msg = f"Erro ao gerar relatório PDF: {str(e)}"
            print(f"❌ {error_msg}")
            raise Exception(error_msg)
    
    def _add_title_section(self, story: List, results: Dict[str, Any]):
        """
        Adiciona a seção de título do relatório.
        
        Args:
            story: Lista de elementos do documento
            results: Resultados da análise
        """
        # Título principal
        title = Paragraph("Relatório de Análise de Propriedade Intelectual", self.styles['CustomTitle'])
        story.append(title)
        story.append(Spacer(1, 12))
        
        # Informações básicas
        info_data = [
            ["Critérios de Busca:", results.get('search_criteria', 'N/A')],
            ["Data de Geração:", datetime.now().strftime("%d/%m/%Y %H:%M:%S")],
            ["ID do Fluxo:", results.get('flow_id', 'N/A')],
            ["Status:", "Concluído" if results.get('success', False) else "Com Erros"]
        ]
        
        info_table = Table(info_data, colWidths=[2*inch, 4*inch])
        info_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('BACKGROUND', (1, 0), (1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(info_table)
        story.append(Spacer(1, 20))
    
    def _add_summary_section(self, story: List, results: Dict[str, Any]):
        """
        Adiciona a seção de resumo executivo.
        
        Args:
            story: Lista de elementos do documento
            results: Resultados da análise
        """
        story.append(Paragraph("Resumo Executivo", self.styles['CustomSubtitle']))
        
        # Estatísticas principais
        data_collected = results.get('data_collected', 0)
        data_classified = results.get('data_classified', 0)
        total_categories = results.get('total_categories', 0)
        
        summary_text = f"""
        Esta análise de propriedade intelectual processou um total de {data_collected} registros brutos, 
        dos quais {data_classified} foram classificados com sucesso em {total_categories} categorias distintas. 
        O processo incluiu coleta de dados de múltiplas fontes, classificação automática usando processamento 
        de linguagem natural, análise estatística e geração de visualizações.
        """
        
        story.append(Paragraph(summary_text, self.styles['JustifiedText']))
        story.append(Spacer(1, 15))
    
    def _add_data_overview_section(self, story: List, results: Dict[str, Any]):
        """
        Adiciona a seção de visão geral dos dados.
        
        Args:
            story: Lista de elementos do documento
            results: Resultados da análise
        """
        story.append(Paragraph("Visão Geral dos Dados", self.styles['CustomSubtitle']))
        
        # Tabela com estatísticas
        stats_data = [
            ["Métrica", "Valor"],
            ["Registros Coletados", str(results.get('data_collected', 0))],
            ["Registros Classificados", str(results.get('data_classified', 0))],
            ["Total de Categorias", str(results.get('total_categories', 0))],
            ["Visualizações Geradas", str(len(results.get('visualizations', {})))]
        ]
        
        stats_table = Table(stats_data, colWidths=[3*inch, 2*inch])
        stats_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(stats_table)
        story.append(Spacer(1, 15))
    
    def _add_category_analysis_section(self, story: List, results: Dict[str, Any]):
        """
        Adiciona a seção de análise por categorias.
        
        Args:
            story: Lista de elementos do documento
            results: Resultados da análise
        """
        story.append(Paragraph("Análise por Categorias", self.styles['CustomSubtitle']))
        
        category_summary = results.get('category_summary', {})
        
        if category_summary:
            # Criar tabela com distribuição por categorias
            category_data = [["Categoria", "Quantidade", "Percentual"]]
            total = sum(category_summary.values())
            
            for category, count in sorted(category_summary.items(), key=lambda x: x[1], reverse=True):
                percentage = (count / total * 100) if total > 0 else 0
                category_data.append([category, str(count), f"{percentage:.1f}%"])
            
            category_table = Table(category_data, colWidths=[2.5*inch, 1.5*inch, 1.5*inch])
            category_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 11),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.lightblue),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            story.append(category_table)
        else:
            story.append(Paragraph("Nenhuma categoria foi identificada nos dados analisados.", 
                                 self.styles['Normal']))
        
        story.append(Spacer(1, 15))
    
    def _add_insights_section(self, story: List, results: Dict[str, Any]):
        """
        Adiciona a seção de insights e conclusões.
        
        Args:
            story: Lista de elementos do documento
            results: Resultados da análise
        """
        story.append(Paragraph("Insights e Conclusões", self.styles['CustomSubtitle']))
        
        insights = results.get('formatted_insights') or results.get('insights', '')
        
        if insights:
            story.append(Paragraph(insights, self.styles['JustifiedText']))
        else:
            story.append(Paragraph("Nenhum insight específico foi gerado para esta análise.", 
                                 self.styles['Normal']))
        
        story.append(Spacer(1, 15))
    
    def _add_visualizations_section(self, story: List, results: Dict[str, Any]):
        """
        Adiciona a seção de visualizações (gráficos).
        
        Args:
            story: Lista de elementos do documento
            results: Resultados da análise
        """
        visualizations = results.get('visualizations', {})
        
        if visualizations:
            story.append(Paragraph("Visualizações", self.styles['CustomSubtitle']))
            
            for viz_name, viz_path in visualizations.items():
                if os.path.exists(viz_path):
                    try:
                        # Adicionar título da visualização
                        viz_title = viz_name.replace('_', ' ').title()
                        story.append(Paragraph(viz_title, self.styles['SectionHeader']))
                        
                        # Adicionar imagem
                        img = Image(viz_path, width=6*inch, height=4*inch)
                        story.append(img)
                        story.append(Spacer(1, 15))
                    except Exception as e:
                        print(f"⚠️ Erro ao adicionar visualização {viz_name}: {e}")
                        story.append(Paragraph(f"Erro ao carregar visualização: {viz_name}", 
                                             self.styles['Normal']))
                        story.append(Spacer(1, 10))
        else:
            story.append(Paragraph("Visualizações", self.styles['CustomSubtitle']))
            story.append(Paragraph("Nenhuma visualização foi gerada para esta análise.", 
                                 self.styles['Normal']))
            story.append(Spacer(1, 15))
    
    def _add_detailed_results_section(self, story: List, results: Dict[str, Any]):
        """
        Adiciona a seção de resultados detalhados.
        
        Args:
            story: Lista de elementos do documento
            results: Resultados da análise
        """
        story.append(PageBreak())
        story.append(Paragraph("Resultados Detalhados", self.styles['CustomSubtitle']))
        
        # Adicionar resultados de análise se disponíveis
        analysis_results = results.get('analysis_results', {})
        
        if analysis_results:
            story.append(Paragraph("Métricas de Análise:", self.styles['SectionHeader']))
            
            for key, value in analysis_results.items():
                if isinstance(value, dict):
                    # Se o valor é um dicionário, criar uma tabela
                    story.append(Paragraph(f"{key.replace('_', ' ').title()}:", 
                                         self.styles['Normal']))
                    
                    table_data = [["Item", "Valor"]]
                    for item_key, item_value in value.items():
                        table_data.append([str(item_key), str(item_value)])
                    
                    detail_table = Table(table_data, colWidths=[3*inch, 2*inch])
                    detail_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, -1), 9),
                        ('GRID', (0, 0), (-1, -1), 1, colors.black)
                    ]))
                    
                    story.append(detail_table)
                    story.append(Spacer(1, 10))
                else:
                    # Se o valor é simples, adicionar como parágrafo
                    story.append(Paragraph(f"<b>{key.replace('_', ' ').title()}:</b> {value}", 
                                         self.styles['Normal']))
                    story.append(Spacer(1, 5))
        else:
            story.append(Paragraph("Nenhum resultado detalhado disponível.", 
                                 self.styles['Normal']))
        
        # Adicionar rodapé
        story.append(Spacer(1, 30))
        footer_text = f"Relatório gerado automaticamente pelo Sistema de Análise de Propriedade Intelectual em {datetime.now().strftime('%d/%m/%Y às %H:%M:%S')}"
        story.append(Paragraph(footer_text, self.styles['Normal']))
    
    def create_simple_report(self, title: str, content: str, output_path: str) -> str:
        """
        Cria um relatório PDF simples com título e conteúdo.
        
        Args:
            title: Título do relatório
            content: Conteúdo do relatório
            output_path: Caminho onde o PDF será salvo
            
        Returns:
            Caminho do arquivo PDF gerado
        """
        try:
            doc = SimpleDocTemplate(output_path, pagesize=letter)
            story = []
            
            # Adicionar título
            story.append(Paragraph(title, self.styles['CustomTitle']))
            story.append(Spacer(1, 20))
            
            # Adicionar conteúdo
            story.append(Paragraph(content, self.styles['JustifiedText']))
            
            # Construir PDF
            doc.build(story)
            
            return output_path
            
        except Exception as e:
            raise Exception(f"Erro ao criar relatório simples: {str(e)}")

