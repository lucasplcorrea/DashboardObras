import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import base64
from io import BytesIO
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib
matplotlib.use("Agg")  # Use non-interactive backend

# Imports para nova geração de PDF com ReportLab
try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image
    from reportlab.platypus.frames import Frame
    from reportlab.platypus.doctemplate import PageTemplate, BaseDocTemplate
    from reportlab.graphics.shapes import Drawing
    from reportlab.graphics.charts.barcharts import VerticalBarChart
    from reportlab.graphics.charts.piecharts import Pie
    from reportlab.graphics.charts.linecharts import HorizontalLineChart
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

# Imports para versão premium com Plotly
try:
    import kaleido
    KALEIDO_AVAILABLE = True
except ImportError:
    KALEIDO_AVAILABLE = False

st.set_page_config(page_title="Dashboard de Obras", layout="wide")

# Cores da identidade visual
COLORS = {
    "primary": "#00497A",
    "secondary": "#FFD700",
    "support1": "#008DDE",
    "support2": "#00609B",
    "support3": "#FFB81C",
    "support4": "#C99900",
    "support5": "#00BF6F",
    "support6": "#A9BE00",
    "support7": "#F2913D",
    "support8": "#EB634C",
    "support9": "#5B2D82",
    "support10": "#806EAF",
}

# Adicionando mais 10 cores para o gráfico de Gantt
ADDITIONAL_COLORS = [
    "#FF6347",
    "#4682B4",
    "#DAA520",
    "#8A2BE2",
    "#3CB371",
    "#FFDAB9",
    "#CD5C5C",
    "#40E0D0",
    "#EE82EE",
    "#7B68EE",
]

ALL_GANTT_COLORS = list(COLORS.values()) + ADDITIONAL_COLORS


# Função para formatar valores como moeda brasileira
def format_currency_br(value, show_cents=True):
    if pd.isna(value):
        return "R$ 0,00"

    if show_cents:
        return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    else:
        # Formatação simplificada para valores gerais (sem centavos)
        if value >= 1000000:
            return f"R$ {value/1000000:.1f}M".replace(".", ",")
        elif value >= 1000:
            return f"R$ {value/1000:.0f}K"
        else:
            return f"R$ {value:,.0f}".replace(",", ".")


# --- Carregamento dos dados ---
@st.cache_data
def load_data():
    df = pd.read_excel("./cadastro_obras_simplificado.xlsx", sheet_name="Sheet1")
    df_sheet2 = pd.read_excel("./cadastro_obras_simplificado.xlsx", sheet_name="Sheet2")

    # Preencher valores nulos para colunas numéricas e de data
    numeric_cols = [
        "Custo Raso Meta",
        "Custo Fluxo",
        "Percentual Incorrido do Fluxo%",
        "ago/25",
        "set/25",
        "out/25",
        "Média dos Próximos Meses",
        "Saldo",
        "Índice Ômega",
        "% Avanço Físico",
        "%Avanço Financeiro",
        "Tempo de Obra",
        "Lotes",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    date_cols = ["Início Obra", "Fim Obra"]
    for col in date_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    # Separar custos gerais (IDs 900 e 901) - Manter para compatibilidade, mas usaremos valores fixos
    df_custos_gerais_from_excel = df[df["ID"].isin([900, 901])].copy()
    df_projetos = df[~df["ID"].isin([900, 901])].copy()

    return df_projetos, df_custos_gerais_from_excel, df_sheet2


df_projetos, df_custos_gerais_from_excel, df_sheet2 = load_data()

# Despesas fixas hardcoded
despesas_fixas = pd.DataFrame(
    {
        "ID": [900, 901],
        "Projeto": ["Diesel dos Equipamentos", "Custo de Operação da Mecanica"],
        "Custo Fluxo": [779000 * 12 / 13, 641891 * 12 / 13],  # Valores diluídos por 13 meses
    }
)

# Concatenar despesas fixas com os custos gerais lidos do excel, se houver
df_custos_gerais = pd.concat([df_custos_gerais_from_excel, despesas_fixas], ignore_index=True)

st.title("📊 Dashboard de Obras - Abecker Loteamentos")

# --- Observações Fixas e Filtros (na sidebar para serem mais discretos) ---
with st.sidebar:
    st.header("📝 Observações")
    st.markdown(
        """
    **Considerações do fluxo financeiro:**
    1. Pedras com permuta;
    2. Tubos com permutas;
    3. Asfalto com permutas;
    4. Parcelamentos dos terceiros de acordo com os contratos;
    5. O Percentual incorrido é do fluxo, e não do orçamento meta.
    6. Incluído o Diesel no fluxo. (Rateado)
    7. Incluída a operação da Mecânica no fluxo. (Rateado)
    
    **Não considerado no fluxo:**
                
    8. Mão de obra da Abecker;
    9. Equipamentos.
    10. A diferença entre o custo meta e o custo do fluxo corresponde ao BDI e Permutas da Abecker.
    """
    )

# --- Melhoria 3: Filtros com prioridade para obras ---
st.header("⚙️ Filtros")
col1, col2 = st.columns(2)

with col1:
    # Filtro principal: Obras
    obras_options = df_projetos["Projeto"].dropna().unique().tolist()
    selected_obras = st.multiselect(
        "🏗️ Filtrar por Obra",
        options=obras_options,
        default=obras_options,
        help="Selecione uma ou mais obras específicas - Filtro Principal",
    )

with col2:
    # Filtrar cidades com base nas obras selecionadas
    if selected_obras:
        cidades_options_filtered_by_obra = df_projetos[
            df_projetos["Projeto"].isin(selected_obras)
        ]["Cidade"].dropna().unique().tolist()
    else:
        cidades_options_filtered_by_obra = df_projetos["Cidade"].dropna().unique().tolist()

    selected_cidades = st.multiselect(
        "🏙️ Cidade das Obras (Preenchido Automaticamente)",
        options=cidades_options_filtered_by_obra,
        default=cidades_options_filtered_by_obra,
        help="Selecione uma ou mais cidades",
    )

# Aplicar filtros
df_filtered_projetos = df_projetos[
    df_projetos["Projeto"].isin(selected_obras)
    & df_projetos["Cidade"].isin(selected_cidades)
]

# Determinar se deve mostrar centavos (quando obra específica é selecionada)
show_cents = len(selected_obras) == 1

# --- Cálculo proporcional do custo geral executado por lote ---
total_lotes_geral = df_projetos["Lotes"].sum()  # Total de lotes de todas as obras
total_lotes_filtrado = df_filtered_projetos["Lotes"].sum()  # Total de lotes das obras filtradas

# Custo geral executado total
custo_geral_exec_total = df_custos_gerais["Custo Fluxo"].sum()

# Custo geral executado proporcional baseado nos lotes
if total_lotes_geral > 0:
    proporcao_lotes = total_lotes_filtrado / total_lotes_geral
    custo_geral_exec_proporcional = custo_geral_exec_total * proporcao_lotes
else:
    custo_geral_exec_proporcional = 0

# --- KPIs de Projetos ---
total_obras = len(df_filtered_projetos)
investimento_exec_projetos = df_filtered_projetos["Custo Fluxo"].sum()
media_proximos_meses_projetos = df_filtered_projetos["Média dos Próximos Meses"].sum()
saldo_projetos = df_filtered_projetos["Saldo"].sum()
total_lotes = df_filtered_projetos["Lotes"].sum()

# --- Novos Indicadores Solicitados ---
custo_total_fluxo_obras = investimento_exec_projetos + custo_geral_exec_proporcional
custo_ago_25 = df_filtered_projetos["ago/25"].sum()
custo_set_25 = df_filtered_projetos["set/25"].sum()
custo_out_25 = df_filtered_projetos["out/25"].sum()
valor_restante_pagar_media = media_proximos_meses_projetos
saldo_total_acumulado = saldo_projetos

# --- Funcionalidade de Exportação para PDF (Movida para o topo) ---
st.markdown("---")

# Função para criar PDF completo - "Print da tela" - VERSÃO MELHORADA
def create_complete_dashboard_pdf():
    """Cria um PDF completo que replica exatamente o dashboard na tela - versão melhorada"""
    
    if not REPORTLAB_AVAILABLE:
        st.error("ReportLab não está instalado.")
    
    buffer = BytesIO()
    
    # Configurar documento
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=0.5*inch,
        leftMargin=0.5*inch,
        topMargin=0.5*inch,
        bottomMargin=0.5*inch
    )
    
    # Estilos sem emojis
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=18, spaceAfter=20, 
                                textColor=colors.HexColor('#00497A'), alignment=1, fontName='Helvetica-Bold')
    
    section_style = ParagraphStyle('Section', parent=styles['Heading2'], fontSize=14, spaceBefore=15, 
                                  spaceAfter=10, textColor=colors.HexColor('#00497A'), fontName='Helvetica-Bold')
    
    subsection_style = ParagraphStyle('Subsection', parent=styles['Heading3'], fontSize=12, spaceBefore=10, 
                                     spaceAfter=8, textColor=colors.HexColor('#008DDE'), fontName='Helvetica-Bold')
    
    story = []
    
    # === TÍTULO PRINCIPAL ===
    story.append(Paragraph("Relatório de Obras", title_style))
    story.append(Spacer(1, 20))
    
    # === OBSERVAÇÕES NO TOPO ===
    story.append(Paragraph("Observações e Considerações", section_style))
    
    observacoes_text = """
    <b>Considerações do fluxo financeiro:</b><br/>
    1. Pedras com permuta<br/>
    2. Tubos com permutas<br/>
    3. Asfalto com permutas<br/>
    4. Parcelamentos dos terceiros de acordo com os contratos<br/>
    5. O Percentual incorrido é do fluxo, e não do orçamento meta<br/>
    6. Incluído o Diesel no fluxo (Rateado)<br/>
    7. Incluída a operação da Mecânica no fluxo (Rateado)<br/><br/>
    
    <b>Não considerado no fluxo:</b><br/>
    8. Mão de obra da Abecker<br/>
    9. Equipamentos<br/><br/>
    
    <b>Informações do Relatório:</b><br/>
    • Relatório gerado em: {data_geracao}<br/>
    • Filtros aplicados preservados<br/>
    • Todos os gráficos e dados do dashboard incluídos
    """.format(data_geracao=pd.Timestamp.now().strftime('%d/%m/%Y às %H:%M'))
    
    story.append(Paragraph(observacoes_text, styles['Normal']))
    story.append(Spacer(1, 20))
    
    # === FILTROS APLICADOS ===
    story.append(Paragraph("Filtros Aplicados", section_style))
    filtros_text = f"<b>Filtros Aplicados:</b><br/>"
    filtros_text += f"• <b>Obras Selecionadas:</b> {', '.join(selected_obras[:5])}{'...' if len(selected_obras) > 5 else ''}<br/>"
    filtros_text += f"• <b>Cidades Selecionadas:</b> {', '.join(selected_cidades[:5])}{'...' if len(selected_cidades) > 5 else ''}"
    story.append(Paragraph(filtros_text, styles['Normal']))
    story.append(Spacer(1, 20))
    
    # === KPIs PRINCIPAIS ===
    story.append(Paragraph("Principais Indicadores", section_style))
    
    # KPIs em formato de cards
    kpis_principais = [
        ['Total de Obras', str(total_obras)],
        ['Custo Fluxo Projetos', format_currency_br(investimento_exec_projetos, show_cents)],
        ['Média Próximos Meses (Projetos)', format_currency_br(media_proximos_meses_projetos, show_cents)],
        ['Saldo Projetos', format_currency_br(saldo_projetos, show_cents)],
        ['Total de Lotes', f"{total_lotes:,}".replace(",", ".")]
    ]
    
    kpis_table = Table(kpis_principais, colWidths=[4*inch, 3*inch])
    kpis_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.lightblue),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8)
    ]))
    story.append(kpis_table)
    story.append(Spacer(1, 20))
    
    # === CUSTOS GERAIS (DESPESAS FIXAS) ===
    story.append(Paragraph("Sumário de Custos Gerais (Despesas Fixas)", section_style))
    
    custos_gerais = [
        ['Custo Geral Exec. (Fixas - Proporcional)', format_currency_br(custo_geral_exec_proporcional, show_cents)]
    ]
    if show_cents:
        custos_gerais.append(['Proporção de Lotes', f"{proporcao_lotes:.1%}"])
    
    custos_table = Table(custos_gerais, colWidths=[4*inch, 3*inch])
    custos_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.lightgreen),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8)
    ]))
    story.append(custos_table)
    story.append(Spacer(1, 20))
    
    # === INDICADORES TOTAIS ===
    story.append(Paragraph("Indicadores de Custos Totais", section_style))
    
    indicadores_totais = [
        ['Custo Total do Fluxo (Geral)', format_currency_br(custo_total_fluxo_obras, show_cents)],
        ['Custo Ago/25', format_currency_br(custo_ago_25, show_cents)],
        ['Custo Set/25', format_currency_br(custo_set_25, show_cents)],
        ['Custo Out/25', format_currency_br(custo_out_25, show_cents)],
        ['Valor Restante a Pagar (Média)', format_currency_br(valor_restante_pagar_media, show_cents)]
    ]
    
    indicadores_table = Table(indicadores_totais, colWidths=[4*inch, 3*inch])
    indicadores_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.lightyellow),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8)
    ]))
    story.append(indicadores_table)
    story.append(PageBreak())
    
    # === GRÁFICOS PRINCIPAIS ===
    if not df_filtered_projetos.empty:
        
        # 1. OBRAS POR TIPOLOGIA
        story.append(Paragraph("Obras por Tipologia", section_style))
        tipologia_counts = df_filtered_projetos.groupby("Tipologia").agg({"Projeto": "count", "Lotes": "sum"}).reset_index()
        tipologia_counts.columns = ["Tipologia", "Número de Obras", "Total de Lotes"]
        
        if KALEIDO_AVAILABLE:
            fig_tipologia = px.pie(
                tipologia_counts,
                values="Número de Obras",
                names="Tipologia", 
                title="Distribuição por Tipologia",
                color_discrete_sequence=px.colors.sequential.Greens_r
            )
            fig_tipologia.update_layout(
                title_font_size=14,
                title_font_color=COLORS["primary"],
                font=dict(size=10),
                showlegend=True,
                height=400
            )
            
            img_bytes = fig_tipologia.to_image(format="png", width=700, height=400, scale=2)
            img_tipologia = Image(BytesIO(img_bytes), width=6*inch, height=3*inch)
            story.append(img_tipologia)
        
        story.append(Spacer(1, 20))
        
        # 2. CUSTO FLUXO POR PROJETO
        story.append(Paragraph("Custo Fluxo por Projeto", section_style))
        
        if KALEIDO_AVAILABLE:
            df_custo_fluxo = df_filtered_projetos[["Projeto", "Custo Fluxo", "Lotes"]].copy()
            grafico1 = px.bar(
                df_custo_fluxo,
                x="Projeto",
                y="Custo Fluxo",
                labels={"Custo Fluxo": "Custo (R$)"},
                color_discrete_sequence=[COLORS["primary"]],
                hover_data=["Lotes"]
            )
            grafico1.update_layout(
                title_font_size=14,
                title_font_color=COLORS["primary"],
                xaxis_tickangle=-45,
                font=dict(size=10),
                height=500
            )
            
            img_bytes = grafico1.to_image(format="png", width=800, height=500, scale=2)
            img_custo = Image(BytesIO(img_bytes), width=7*inch, height=4*inch)
            story.append(img_custo)
        
        story.append(PageBreak())
        
        # 3. CRONOGRAMA DAS OBRAS - CORRIGIDO
        gantt_data = df_filtered_projetos[["Projeto", "Início Obra", "Fim Obra"]].dropna()
        if not gantt_data.empty:
            story.append(Paragraph("Cronograma das Obras", section_style))
            
            if KALEIDO_AVAILABLE:
                # Preparar dados do Gantt de forma mais robusta
                gantt_list = []
                for _, row in gantt_data.iterrows():
                    if pd.notna(row["Início Obra"]) and pd.notna(row["Fim Obra"]):
                        inicio = pd.to_datetime(row["Início Obra"])
                        fim = pd.to_datetime(row["Fim Obra"])
                        
                        # Garantir que as datas estão em um range válido
                        if inicio < pd.to_datetime("2024-01-01"):
                            inicio = pd.to_datetime("2024-01-01")
                        
                        gantt_list.append({
                            'Task': row["Projeto"],
                            'Start': inicio,
                            'Finish': fim,
                            'Resource': row["Projeto"]
                        })
                
                if gantt_list:
                    df_gantt = pd.DataFrame(gantt_list)
                    
                    # Criar gráfico Gantt com plotly
                    fig_gantt = px.timeline(
                        df_gantt, 
                        x_start="Start", 
                        x_end="Finish",
                        y="Task",
                        color="Resource",
                        title="Cronograma das Obras"
                    )
                    
                    fig_gantt.update_yaxes(autorange="reversed", title="Projetos")
                    fig_gantt.update_xaxes(title="Período")
                    fig_gantt.update_layout(
                        title_font_size=14,
                        title_font_color=COLORS["primary"],
                        font=dict(size=9),
                        height=600,
                        showlegend=False
                    )
                    
                    img_bytes = fig_gantt.to_image(format="png", width=800, height=600, scale=2)
                    img_gantt = Image(BytesIO(img_bytes), width=7*inch, height=5*inch)
                    story.append(img_gantt)
            
            story.append(PageBreak())
    
    # === DESPESAS RECORRENTES ===
    if not df_sheet2.empty:
        story.append(Paragraph("Despesas Recorrentes Detalhadas (Diesel e Mecânica)", section_style))
        
        # Gráfico de Custos Mensais da Sheet2 
        if KALEIDO_AVAILABLE:
            monthly_data = []
            for _, row in df_sheet2.iterrows():
                projeto = row["Projeto"]
                tipologia = "Diesel" if "Diesel" in str(row.get("Tipologia", "")) else "Mecânica"
                monthly_data.extend([
                    {"Projeto": projeto, "Tipo": tipologia, "Mês": "Ago/25", "Valor": row.get("ago/25", 0)},
                    {"Projeto": projeto, "Tipo": tipologia, "Mês": "Set/25", "Valor": row.get("set/25", 0)},
                    {"Projeto": projeto, "Tipo": tipologia, "Mês": "Out/25", "Valor": row.get("out/25", 0)},
                    {"Projeto": projeto, "Tipo": tipologia, "Mês": "Média Próximos", "Valor": row.get("Média dos Próximos Meses", 0)}
                ])
            
            if monthly_data:
                df_monthly_costs = pd.DataFrame(monthly_data)
                fig_monthly_costs_sheet2 = px.line(
                    df_monthly_costs,
                    x="Mês", 
                    y="Valor",
                    color="Tipo",
                    markers=True,
                    labels={"Valor": "Valor (R$)", "Tipo": "Tipo de Custo"},
                    color_discrete_sequence=[COLORS["support7"], COLORS["support8"]],
                    title="Custos Mensais por Tipo de Despesa"
                )
                fig_monthly_costs_sheet2.update_traces(mode="lines+markers", line=dict(width=3), marker=dict(size=10))
                fig_monthly_costs_sheet2.update_layout(
                    title_font_size=14,
                    title_font_color=COLORS["primary"],
                    font=dict(size=10),
                    height=400
                )
                
                img_bytes = fig_monthly_costs_sheet2.to_image(format="png", width=800, height=400, scale=2)
                img_monthly = Image(BytesIO(img_bytes), width=7*inch, height=3*inch)
                story.append(img_monthly)
        
        story.append(PageBreak())
    
    # === OUTROS GRÁFICOS ===
    if not df_filtered_projetos.empty:
        
        # Valores a Pagar por Mês
        story.append(Paragraph("Valores a Pagar por Mês", section_style))
        if KALEIDO_AVAILABLE:
            monthly_costs = pd.DataFrame({
                "Mês": ["Agosto/25", "Setembro/25", "Outubro/25", "Média Próximos Meses"],
                "Valor": [custo_ago_25, custo_set_25, custo_out_25, valor_restante_pagar_media]
            })
            grafico_mensal = px.line(
                monthly_costs,
                x="Mês",
                y="Valor",
                labels={"Valor": "Valor (R$)"},
                markers=True,
                line_shape="linear",
                title="Evolução dos Valores Mensais"
            )
            grafico_mensal.update_traces(
                line=dict(color=COLORS["support7"], width=3),
                marker=dict(size=10, color=COLORS["support8"])
            )
            grafico_mensal.update_layout(
                title_font_size=14,
                title_font_color=COLORS["primary"],
                font=dict(size=10),
                height=400
            )
            
            img_bytes = grafico_mensal.to_image(format="png", width=800, height=400, scale=2)
            img_mensal = Image(BytesIO(img_bytes), width=7*inch, height=3*inch)
            story.append(img_mensal)
        
        # Obras por Cidade
        story.append(Paragraph("Obras por Cidade", section_style))
        if KALEIDO_AVAILABLE:
            obras_por_cidade = df_filtered_projetos["Cidade"].value_counts().reset_index()
            obras_por_cidade.columns = ["Cidade", "Número de Obras"]
            grafico_cidade = px.bar(
                obras_por_cidade,
                x="Cidade",
                y="Número de Obras", 
                labels={"Número de Obras": "Quantidade de Obras"},
                color_discrete_sequence=[COLORS["support6"]],
                title="Distribuição por Cidade"
            )
            grafico_cidade.update_layout(
                title_font_size=14,
                title_font_color=COLORS["primary"],
                xaxis_tickangle=-45,
                font=dict(size=10),
                height=400
            )
            
            img_bytes = grafico_cidade.to_image(format="png", width=800, height=400, scale=2)
            img_cidade = Image(BytesIO(img_bytes), width=7*inch, height=3*inch)
            story.append(img_cidade)
    
    # Construir PDF
    doc.build(story)
    
    buffer.seek(0)
    return buffer

# Função para criar PDF do dashboard usando ReportLab (versão profissional)
def create_professional_pdf_report():
    """Cria um relatório PDF profissional com ReportLab - melhor formatação e layout"""
    
    if not REPORTLAB_AVAILABLE:
        st.error("ReportLab não está instalada. Usando versão básica do matplotlib.")
    
    buffer = BytesIO()
    
    # Configurar documento
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=0.5*inch,
        leftMargin=0.5*inch,
        topMargin=0.5*inch,
        bottomMargin=0.5*inch
    )
    
    # Estilos
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=20,
        spaceAfter=30,
        textColor=colors.HexColor('#00497A'),
        alignment=1  # Center
    )
    
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Heading2'],
        fontSize=16,
        spaceAfter=20,
        textColor=colors.HexColor('#008DDE'),
        alignment=1
    )
    
    section_style = ParagraphStyle(
        'SectionHeader',
        parent=styles['Heading3'],
        fontSize=14,
        spaceBefore=20,
        spaceAfter=10,
        textColor=colors.HexColor('#00497A'),
        fontName='Helvetica-Bold'
    )
    
    # Lista de elementos do documento
    story = []
    
    # Título principal
    story.append(Paragraph("📊 Dashboard de Obras - Relatório Executivo", title_style))
    story.append(Spacer(1, 20))
    
    # Informações dos filtros
    filtros_text = f"<b>Filtros Aplicados:</b><br/>"
    filtros_text += f"• Obras: {', '.join(selected_obras[:5])}{'...' if len(selected_obras) > 5 else ''}<br/>"
    filtros_text += f"• Cidades: {', '.join(selected_cidades[:5])}{'...' if len(selected_cidades) > 5 else ''}"
    story.append(Paragraph(filtros_text, styles['Normal']))
    story.append(Spacer(1, 30))
    
    # KPIs Principais em tabela estilizada
    story.append(Paragraph("📊 Principais Indicadores", section_style))
    
    kpis_data = [
        ['Indicador', 'Valor'],
        ['🏗️ Total de Obras', str(total_obras)],
        ['💰 Custo Fluxo Projetos', format_currency_br(investimento_exec_projetos, show_cents)],
        ['🏘️ Total de Lotes', f"{total_lotes:,}".replace(",", ".")],
        ['💸 Saldo Projetos', format_currency_br(saldo_projetos, show_cents)],
        ['📈 Média Próximos Meses', format_currency_br(media_proximos_meses_projetos, show_cents)],
        ['⚙️ Custo Geral (Proporcional)', format_currency_br(custo_geral_exec_proporcional, show_cents)]
    ]
    
    kpis_table = Table(kpis_data, colWidths=[3*inch, 2.5*inch])
    kpis_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#00497A')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey])
    ]))
    
    story.append(kpis_table)
    story.append(Spacer(1, 30))
    
    # Indicadores de Custos Mensais
    story.append(Paragraph("💰 Valores Mensais", section_style))
    
    custos_mensais_data = [
        ['Mês', 'Valor'],
        ['Agosto/25', format_currency_br(custo_ago_25, show_cents)],
        ['Setembro/25', format_currency_br(custo_set_25, show_cents)],
        ['Outubro/25', format_currency_br(custo_out_25, show_cents)],
        ['Custo Total do Fluxo', format_currency_br(custo_total_fluxo_obras, show_cents)]
    ]
    
    custos_table = Table(custos_mensais_data, colWidths=[2.5*inch, 3*inch])
    custos_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#008DDE')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.lightblue),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightcyan])
    ]))
    
    story.append(custos_table)
    story.append(PageBreak())
    
    # Tabela detalhada das obras
    if not df_filtered_projetos.empty:
        story.append(Paragraph("📋 Tabela Detalhada das Obras", section_style))
        
        # Preparar dados da tabela
        table_columns = ['Projeto', 'Cidade', 'Tipologia', 'Custo Fluxo', 'Saldo', 'Lotes']
        existing_columns = [col for col in table_columns if col in df_filtered_projetos.columns]
        
        # Cabeçalho da tabela
        table_data = [existing_columns]
        
        # Dados das obras
        for _, row in df_filtered_projetos.iterrows():
            row_data = []
            for col in existing_columns:
                if col in ['Custo Fluxo', 'Saldo']:
                    row_data.append(format_currency_br(row[col], False))
                elif col == 'Lotes':
                    row_data.append(f"{row[col]:,.0f}".replace(",", "."))
                else:
                    row_data.append(str(row[col])[:20] + "..." if len(str(row[col])) > 20 else str(row[col]))
            table_data.append(row_data)
        
        # Dividir tabela em páginas se necessário
        rows_per_page = 20
        for page_num, start_idx in enumerate(range(0, len(table_data)-1, rows_per_page)):
            end_idx = min(start_idx + rows_per_page, len(table_data)-1)
            
            if page_num > 0:
                story.append(PageBreak())
                story.append(Paragraph(f"📋 Tabela Detalhada das Obras (Continuação - Página {page_num + 1})", section_style))
            
            page_data = [table_data[0]] + table_data[start_idx+1:end_idx+1]
            
            obras_table = Table(page_data, repeatRows=1)
            obras_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4472C4')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey])
            ]))
            
            story.append(obras_table)
            story.append(Spacer(1, 20))
    
    # Gráfico de Custo Fluxo usando ReportLab Charts
    if not df_filtered_projetos.empty and len(df_filtered_projetos) <= 10:
        story.append(PageBreak())
        story.append(Paragraph("📊 Custo Fluxo por Projeto", section_style))
        
        # Criar gráfico de barras com ReportLab
        drawing = Drawing(400, 300)
        
        chart = VerticalBarChart()
        chart.x = 50
        chart.y = 50
        chart.height = 200
        chart.width = 300
        
        # Dados do gráfico
        projetos_nomes = df_filtered_projetos['Projeto'].tolist()[:10]  # Máximo 10 projetos
        projetos_valores = df_filtered_projetos['Custo Fluxo'].tolist()[:10]
        
        chart.data = [projetos_valores]
        chart.categoryAxis.categoryNames = [nome[:15] + "..." if len(nome) > 15 else nome for nome in projetos_nomes]
        chart.categoryAxis.labels.angle = 45
        chart.categoryAxis.labels.fontSize = 8
        chart.valueAxis.valueMin = 0
        chart.valueAxis.valueMax = max(projetos_valores) * 1.1
        
        # Cores
        chart.bars[0].fillColor = colors.HexColor('#00497A')
        chart.bars[0].strokeColor = colors.HexColor('#00497A')
        
        drawing.add(chart)
        story.append(drawing)
        story.append(Spacer(1, 30))
    
    # Tabela da Sheet2 (Despesas Fixas)
    if not df_sheet2.empty:
        story.append(PageBreak())
        story.append(Paragraph("⛽ Despesas Fixas Detalhadas", section_style))
        
        sheet2_data = [['Projeto', 'Tipologia', 'Custo Fluxo', 'Ago/25', 'Set/25', 'Out/25']]
        
        for _, row in df_sheet2.iterrows():
            sheet2_data.append([
                str(row.get('Projeto', ''))[:20],
                str(row.get('Tipologia', ''))[:15],
                format_currency_br(row.get('Custo Fluxo', 0), False),
                format_currency_br(row.get('ago/25', 0), False),
                format_currency_br(row.get('set/25', 0), False),
                format_currency_br(row.get('out/25', 0), False)
            ])
        
        sheet2_table = Table(sheet2_data, repeatRows=1)
        sheet2_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#70AD47')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgreen])
        ]))
        
        story.append(sheet2_table)
    
    # Rodapé com informações adicionais
    story.append(PageBreak())
    story.append(Paragraph("📝 Observações e Considerações", section_style))
    
    observacoes_text = """
    <b>Considerações do fluxo financeiro:</b><br/>
    1. Pedras com permuta<br/>
    2. Tubos com permutas<br/>
    3. Asfalto com permutas<br/>
    4. Parcelamentos dos terceiros de acordo com os contratos<br/>
    5. O Percentual incorrido é do fluxo, e não do orçamento meta<br/>
    6. Incluído o Diesel no fluxo (Rateado)<br/>
    7. Incluída a operação da Mecânica no fluxo (Rateado)<br/><br/>
    
    <b>Não considerado no fluxo:</b><br/>
    8. Mão de obra da Abecker<br/>
    9. Equipamentos
    """
    
    story.append(Paragraph(observacoes_text, styles['Normal']))
    
    # Informações de geração do relatório
    story.append(Spacer(1, 30))
    footer_text = f"<i>Relatório gerado em {pd.Timestamp.now().strftime('%d/%m/%Y às %H:%M')}</i>"
    story.append(Paragraph(footer_text, styles['Italic']))
    
    # Construir PDF
    doc.build(story)
    
    buffer.seek(0)
    return buffer

# Interface para exportação de PDF - Dashboard Completo
st.markdown("### 📁 Exportar Relatório PDF")    

if REPORTLAB_AVAILABLE:
    col_pdf, col_info = st.columns([2, 1])
    
    with col_pdf:
        if st.button("📄 Gerar Relatório PDF", help="Relatório completo do dashboard", type="primary"):
            try:
                with st.spinner("Gerando relatório PDF..."):
                    pdf_buffer = create_complete_dashboard_pdf()
                    
                    st.download_button(
                        label="⬇️ Download Relatório PDF",
                        data=pdf_buffer.getvalue(),
                        file_name=f"dashboard_obras_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                        mime="application/pdf",
                        key="pdf_report"
                    )
                    st.success("✅ Relatório PDF gerado com sucesso!")
            except Exception as e:
                st.error(f"❌ Erro ao gerar PDF: {str(e)}")
    
    st.markdown("---")

# KPIs principais com formatação condicional
kpi1, kpi2, kpi3, kpi4 = st.columns(4)
kpi1.metric("🏗️ Total de Obras", total_obras)
kpi2.metric("🧾 Custo Fluxo Projetos", format_currency_br(investimento_exec_projetos, show_cents))
kpi3.metric("💰 Saldo dos Projetos", format_currency_br(saldo_projetos, show_cents))
kpi4.metric("🏘️ Total de Lotes Usinando", f"{total_lotes:,}".replace(",", "."))

st.markdown("---")

st.subheader("Despesas Fixas - Diesel e Mecânica (3 próximos meses)")
kpi_cg1, kpi_cg2, kpi_cg3, kpi_cg4, kpi_cg5 = st.columns(5)
kpi_cg1.metric("🧾 Custos Fixos - Diesel e Mecânica - 13 Meses", format_currency_br(custo_geral_exec_proporcional, show_cents))
kpi_cg2.metric("🧾 Custos Ago/25", format_currency_br(custo_geral_exec_proporcional, show_cents))
kpi_cg3.metric("🧾 Custos Set/25", format_currency_br(custo_geral_exec_proporcional, show_cents))
kpi_cg4.metric("🧾 Custos Out/25", format_currency_br(custo_geral_exec_proporcional, show_cents))
kpi_cg5.metric("💸 Valor Restante a Pagar (Média)", format_currency_br(custo_geral_exec_proporcional, show_cents))

st.subheader("Indicadores de Custos Totais")
kpi_ct1, kpi_ct2, kpi_ct3, kpi_ct4, kpi_ct5 = st.columns(5)
kpi_ct1.metric("💰 Custo Total", format_currency_br(custo_total_fluxo_obras, show_cents))
kpi_ct2.metric("🗓️ Custo Ago/25", format_currency_br(custo_ago_25, show_cents))
kpi_ct3.metric("🗓️ Custo Set/25", format_currency_br(custo_set_25, show_cents))
kpi_ct4.metric("🗓️ Custo Out/25", format_currency_br(custo_out_25, show_cents))
kpi_ct5.metric(
    "💸 Valor Restante a Pagar (Média)", format_currency_br(valor_restante_pagar_media, show_cents)
)

st.markdown("---")

# --- Novos Indicadores de Etapa e Tipologia ---
col_saldo, col_tipologia = st.columns(2)

with col_tipologia:
    st.subheader("📊 Obras por Tipologia")
    if not df_filtered_projetos.empty:
        tipologia_counts = (
            df_filtered_projetos.groupby("Tipologia")
            .agg({"Projeto": "count", "Lotes": "sum"})
            .reset_index()
        )
        tipologia_counts.columns = ["Tipologia", "Número de Obras", "Total de Lotes"]

        fig_tipologia = px.pie(
            tipologia_counts,
            values="Número de Obras",
            names="Tipologia",
            title="Distribuição por Tipologia",
            color_discrete_sequence=px.colors.sequential.Greens_r,
            hover_data=["Total de Lotes"],
        )
        fig_tipologia.update_traces(
            hovertemplate="<b>%{label}</b><br>Obras: %{value}<br>Lotes: %{customdata[0]}<extra></extra>"
        )
        st.plotly_chart(fig_tipologia, use_container_width=True)
    else:
        st.info("Nenhuma obra selecionada para exibir tipologia.")

with col_saldo:
    st.subheader("📊 Saldo por Projeto")
    if not df_filtered_projetos.empty:
        saldo_por_projeto = (
            df_filtered_projetos.groupby("Projeto")["Saldo"].sum().reset_index()
        )
        saldo_por_projeto = saldo_por_projeto[saldo_por_projeto["Saldo"] > 0]

        if not saldo_por_projeto.empty:
            grafico2 = px.pie(
                saldo_por_projeto,
                values="Saldo",
                names="Projeto",
                title="Saldo Total por Projeto",
                height=400,
                color_discrete_sequence=px.colors.sequential.RdBu,
            )
            st.plotly_chart(grafico2, use_container_width=True)
        else:
            st.info("Não há dados de Saldo para exibir no gráfico de pizza para os filtros selecionados.")
    else:
        st.info("Nenhuma obra selecionada para exibir saldo.")

st.markdown("---")

# --- Gráfico 1: Custo Fluxo por Projeto ---
st.subheader("💰 Custo Fluxo por Projeto")

if not df_filtered_projetos.empty:
    df_custo_fluxo = df_filtered_projetos[["Projeto", "Custo Fluxo", "Lotes"]].copy()

    grafico1 = px.bar(
        df_custo_fluxo,
        x="Projeto",
        y="Custo Fluxo",
        labels={"Custo Fluxo": "Custo (R$)"},
        height=400,
        color_discrete_sequence=[COLORS["primary"]],
        hover_data=["Lotes"],
    )
    grafico1.update_traces(
        hovertemplate="<b>%{x}</b><br>Custo: R$ %{y:,.2f}<br>Lotes: %{customdata[0]}<extra></extra>"
    )
    st.plotly_chart(grafico1, use_container_width=True)
else:
    st.info("Nenhuma obra selecionada para exibir custo fluxo.")

# --- Gráfico 3: Cronograma (Gantt simplificado) ---
st.subheader("📅 Cronograma das Obras")
if not df_filtered_projetos.empty:
    gantt_data = df_filtered_projetos[["Projeto", "Início Obra", "Fim Obra"]].dropna()

    if not gantt_data.empty:
        # Filtrar para começar a visualização em 2024
        gantt_data_filtered = gantt_data.copy()
        gantt_data_filtered.loc[
            gantt_data_filtered["Início Obra"] < "2024-01-01", "Início Obra"
        ] = pd.to_datetime("2024-01-01")

        grafico3 = px.timeline(
            gantt_data_filtered,
            x_start="Início Obra",
            x_end="Fim Obra",
            y="Projeto",
            color="Projeto",
            color_discrete_sequence=ALL_GANTT_COLORS,
        )
        grafico3.update_yaxes(autorange="reversed")
        grafico3.update_xaxes(range=["2024-01-01", gantt_data["Fim Obra"].max()])
        st.plotly_chart(grafico3, use_container_width=True)
    else:
        st.info("Não há dados de cronograma para as obras selecionadas.")
else:
    st.info("Nenhuma obra selecionada para exibir cronograma.")

st.markdown("---")

# --- Visualizações da Sheet 2 ---
st.subheader("📊 Despesas Recorrentes Detalhadas (Diesel e Mecânica)")

# Certificar-se de que as colunas numéricas estão no formato correto
numeric_cols_sheet2 = [
    "Custo Fluxo",
    "ago/25",
    "set/25",
    "out/25",
    "Média dos Próximos Meses",
]
for col in numeric_cols_sheet2:
    if col in df_sheet2.columns:
        df_sheet2[col] = pd.to_numeric(df_sheet2[col], errors="coerce").fillna(0)

# Gráfico de pizza para Custo Fluxo por Tipologia (Sheet 2) - Segmentado por lotes
st.write("**Custo Fluxo por Tipo de Despesa (Segmentado por Lotes):**")

# Verificar se existem dados na Sheet2 e se há empreendimentos filtrados
if not df_sheet2.empty and not df_filtered_projetos.empty:
    # Criar dados para o gráfico de pizza aninhado
    fig_nested_pie = make_subplots(
        rows=1,
        cols=2,
        specs=[[{"type": "pie"}, {"type": "pie"}]],
        subplot_titles=("Diesel por Empreendimento", "Mecânica por Empreendimento"),
    )

    # Dados dos empreendimentos para proporção
    empreendimentos_lotes = (
        df_filtered_projetos.groupby("Projeto")["Lotes"].sum().reset_index()
    )
    total_lotes_filtered = empreendimentos_lotes["Lotes"].sum()

    if total_lotes_filtered > 0:
        # Buscar dados de Diesel
        diesel_data = df_sheet2[df_sheet2["Tipologia"].str.contains("Diesel", na=False)]
        if not diesel_data.empty:
            diesel_total = diesel_data["Custo Fluxo"].iloc[0]
            diesel_por_empreendimento = []
            for _, emp in empreendimentos_lotes.iterrows():
                proporcao = emp["Lotes"] / total_lotes_filtered
                diesel_por_empreendimento.append(
                    {
                        "Empreendimento": emp["Projeto"],
                        "Valor": diesel_total * proporcao,
                        "Lotes": emp["Lotes"],
                    }
                )

            df_diesel_emp = pd.DataFrame(diesel_por_empreendimento)

            fig_nested_pie.add_trace(
                go.Pie(
                    labels=df_diesel_emp["Empreendimento"],
                    values=df_diesel_emp["Valor"],
                    name="Diesel",
                    hovertemplate="<b>%{label}</b><br>Valor: R$ %{value:,.2f}<br>Lotes: %{customdata}<extra></extra>",
                    customdata=df_diesel_emp["Lotes"],
                ),
                row=1,
                col=1,
            )

        # Buscar dados de Mecânica
        mecanica_data = df_sheet2[df_sheet2["Tipologia"].str.contains("Mecanica", na=False)]
        if not mecanica_data.empty:
            mecanica_total = mecanica_data["Custo Fluxo"].iloc[0]
            mecanica_por_empreendimento = []
            for _, emp in empreendimentos_lotes.iterrows():
                proporcao = emp["Lotes"] / total_lotes_filtered
                mecanica_por_empreendimento.append(
                    {
                        "Empreendimento": emp["Projeto"],
                        "Valor": mecanica_total * proporcao,
                        "Lotes": emp["Lotes"],
                    }
                )

            df_mecanica_emp = pd.DataFrame(mecanica_por_empreendimento)

            fig_nested_pie.add_trace(
                go.Pie(
                    labels=df_mecanica_emp["Empreendimento"],
                    values=df_mecanica_emp["Valor"],
                    name="Mecânica",
                    hovertemplate="<b>%{label}</b><br>Valor: R$ %{value:,.2f}<br>Lotes: %{customdata}<extra></extra>",
                    customdata=df_mecanica_emp["Lotes"],
                ),
                row=1,
                col=2,
            )

        fig_nested_pie.update_layout(height=500)
        st.plotly_chart(fig_nested_pie, use_container_width=True)
    else:
        st.info("Não há dados de lotes para segmentar as despesas por empreendimento.")
else:
    st.info("Não há dados de despesas ou empreendimentos para exibir.")

st.markdown("---")

# --- Gráfico 4: Custo Fluxo Médio por Empresa ---
st.subheader("🏢 Custo Fluxo Médio por Empresa Desenvolvedora")
if not df_filtered_projetos.empty:
    empresa_custo_fluxo = (
        df_filtered_projetos.groupby("Empresa desenvolvedora")["Custo Fluxo"]
        .mean()
        .reset_index()
    )
    grafico4 = px.bar(
        empresa_custo_fluxo,
        x="Empresa desenvolvedora",
        y="Custo Fluxo",
        color_discrete_sequence=[COLORS["support5"]],
    )
    st.plotly_chart(grafico4, use_container_width=True)
else:
    st.info("Nenhuma obra selecionada para exibir custo por empresa.")

# --- Novo Gráfico: Obras por Cidade ---
st.subheader("🏙️ Obras por Cidade")
if not df_filtered_projetos.empty:
    obras_por_cidade = df_filtered_projetos["Cidade"].value_counts().reset_index()
    obras_por_cidade.columns = ["Cidade", "Número de Obras"]
    grafico_cidade = px.bar(
        obras_por_cidade,
        x="Cidade",
        y="Número de Obras",
        labels={"Número de Obras": "Quantidade de Obras"},
        height=400,
        color_discrete_sequence=[COLORS["support6"]],
    )
    st.plotly_chart(grafico_cidade, use_container_width=True)
else:
    st.info("Nenhuma obra selecionada para exibir distribuição por cidade.")

st.subheader("💰 Valores a Pagar por Mês")
if not df_filtered_projetos.empty:
    # Criar DataFrame com valores a pagar por mês (sem total, pois empilhado mostra)
    df_pagar = df_filtered_projetos[["Projeto", "ago/25", "set/25", "out/25"]].copy()
    
    # Derreter para formato longo
    df_pagar = df_pagar.melt(id_vars=["Projeto"], var_name="Mês", value_name="Valor a Pagar")
    
    # Criar gráfico de área empilhada
    fig_pagar = px.area(
        df_pagar,
        x="Mês",
        y="Valor a Pagar",
        color="Projeto",
        title="Valores a Pagar por Mês",
        labels={"Valor a Pagar": "Valor (R$)", "Mês": "Mês"},
        color_discrete_sequence=ALL_GANTT_COLORS,
        category_orders={"Mês": ["ago/25", "set/25", "out/25"]},
    )
    
    # Atualizar layout e hover
    fig_pagar.update_layout(
        title_font_size=16,
        title_font_color=COLORS["primary"],
        height=500,
        hovermode="x unified",
    )
    
    # Formatar valores no hover como moeda
    fig_pagar.update_traces(
        hovertemplate="<b>%{fullData.name}</b><br>Mês: %{x}<br>Valor: R$ %{y:,.2f}<extra></extra>"
    )
    
    st.plotly_chart(fig_pagar, use_container_width=True)
else:
    st.warning("Nenhuma obra para exibir com os filtros selecionados.")

st.markdown("---")

# --- Tabela final ---
st.subheader("📋 Tabela Detalhada de Obras")

if not df_filtered_projetos.empty:
    # Selecionar todas as colunas relevantes para exibição na tabela final
    all_display_columns = [
        "ID",
        "Empresa desenvolvedora",
        "Sócia",
        "Projeto",
        "Tipologia",
        "Cidade",
        "UF",
        "Etapa",
        "Custo Raso Meta",
        "Custo Fluxo",
        "Percentual Incorrido do Fluxo%",
        "ago/25",
        "set/25",
        "out/25",
        "Média dos Próximos Meses",
        "Saldo",
        "Índice Ômega",
        "% Avanço Físico",
        "%Avanço Financeiro",
        "Tempo de Obra",
        "Início Obra",
        "Fim Obra",
        "Meses Restantes Pós Out/25",
        "Lotes",
    ]

    df_display = df_filtered_projetos[all_display_columns].copy()

    # Aplicar formatação de moeda às colunas financeiras
    currency_display_cols = [
        "Custo Raso Meta",
        "Custo Fluxo",
        "ago/25",
        "set/25",
        "out/25",
        "Média dos Próximos Meses",
        "Saldo",
    ]
    for col in currency_display_cols:
        if col in df_display.columns:
            df_display[col] = df_display[col].apply(lambda x: format_currency_br(x, show_cents))

    st.dataframe(df_display, use_container_width=True)
else:
    st.info("Nenhuma obra selecionada para exibir na tabela detalhada.")

# Tabela com os dados da Sheet 2
st.subheader("📋 Tabela Detalhada das Despesas Fixas (Diesel e Mecânica)")
if not df_sheet2.empty:
    df_display_sheet2 = df_sheet2.copy()
    for col in numeric_cols_sheet2:
        if col in df_display_sheet2.columns:
            df_display_sheet2[col] = df_display_sheet2[col].apply(lambda x: format_currency_br(x, show_cents))
    st.dataframe(df_display_sheet2, use_container_width=True)
else:
    st.info("Não há dados de despesas fixas para exibir.")

st.markdown("---")
