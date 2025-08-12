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
    from reportlab.lib.pagesizes import landscape, A4
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

st.title("📊 Dashboard de Obras")

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
# Filtrar obras iniciadas até 30/09/2025
from datetime import datetime
data_limite = pd.to_datetime("2025-09-30")
df_obras_iniciadas = df_projetos[
    (df_projetos["Etapa"] == "3. Obras iniciadas") &
    (pd.to_datetime(df_projetos["Início Obra"], errors="coerce") <= data_limite)
]

total_lotes_geral = df_obras_iniciadas["Lotes"].sum()
total_lotes_filtrado = df_filtered_projetos["Lotes"].sum()

# Custo geral executado total
custo_geral_exec_total = df_sheet2["Custo Fluxo"].sum()

# Custo geral executado proporcional baseado nos lotes
if total_lotes_geral > 0:
    proporcao_lotes = total_lotes_filtrado / total_lotes_geral
    custo_geral_exec_proporcional = custo_geral_exec_total * proporcao_lotes
else:
    custo_geral_exec_proporcional = 0

# --- Cálculos mensais proporcionais da Sheet2 ---
custo_ago_geral = df_sheet2["ago/25"].sum() * proporcao_lotes
custo_set_geral = df_sheet2["set/25"].sum() * proporcao_lotes
custo_out_geral = df_sheet2["out/25"].sum() * proporcao_lotes
media_proximos_geral = df_sheet2["Média dos Próximos Meses"].sum() * proporcao_lotes

custo_fluxo_mec_diesel = df_sheet2["Custo Fluxo"].sum()

custo_ago_geral_clean = df_sheet2["ago/25"].sum()
custo_set_geral_clean = df_sheet2["set/25"].sum()
custo_out_geral_clean = df_sheet2["out/25"].sum()
custo_media_proximos_geral_clean = df_sheet2["Média dos Próximos Meses"].sum()


# --- KPIs de Projetos ---
total_obras = len(df_filtered_projetos)
investimento_exec_projetos = df_filtered_projetos["Custo Fluxo"].sum()
media_proximos_meses_projetos = df_filtered_projetos["Média dos Próximos Meses"].sum()
saldo_projetos = df_filtered_projetos["Saldo"].sum()
total_lotes = df_filtered_projetos["Lotes"].sum()

# --- Novos Indicadores Solicitados ---
custo_total_fluxo_obras = investimento_exec_projetos + custo_geral_exec_total
custo_ago_25 = df_filtered_projetos["ago/25"].sum()
custo_set_25 = df_filtered_projetos["set/25"].sum()
custo_out_25 = df_filtered_projetos["out/25"].sum()
valor_restante_pagar_media = media_proximos_meses_projetos
saldo_total_acumulado = saldo_projetos

# --- Funcionalidade de Exportação para PDF (Movida para o topo) ---
st.markdown("---")

# Função para criar PDF completo - "Print da tela" - VERSÃO MELHORADA (refatorada)
def create_complete_dashboard_pdf():
    """Cria um PDF completo que replica exatamente o dashboard na tela - versão melhorada"""
    
    if not REPORTLAB_AVAILABLE:
        st.error("ReportLab não está instalado.")
        return None
    
    buffer = BytesIO()
    
    # Configurar documento em paisagem
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=0.5*inch,
        leftMargin=0.5*inch,
        topMargin=0.5*inch,
        bottomMargin=0.5*inch
    )
    
    # Estilos sem emojis
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("Title", parent=styles["Heading1"], fontSize=18, spaceAfter=20, 
                                textColor=colors.HexColor("#00497A"), alignment=1, fontName="Helvetica-Bold")
    
    section_style = ParagraphStyle("Section", parent=styles["Heading2"], fontSize=14, spaceBefore=15, 
                                  spaceAfter=10, textColor=colors.HexColor("#00497A"), fontName="Helvetica-Bold")
    
    subsection_style = ParagraphStyle("Subsection", parent=styles["Heading3"], fontSize=12, spaceBefore=10, 
                                     spaceAfter=8, textColor=colors.HexColor("#008DDE"), fontName="Helvetica-Bold")
    
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
    """.format(data_geracao=pd.Timestamp.now().strftime("%d/%m/%Y às %H:%M"))
    
    story.append(Paragraph(observacoes_text, styles["Normal"]))
    story.append(Spacer(1, 20))
    
    # === FILTROS APLICADOS ===
    story.append(Paragraph("Filtros Aplicados", section_style))
    filtros_text = f"<b>Filtros Aplicados:</b><br/>"
    filtros_text += f"• <b>Obras Selecionadas:</b> {", ".join(selected_obras[:5])}{"..." if len(selected_obras) > 5 else ""}<br/>"
    filtros_text += f"• <b>Cidades Selecionadas:</b> {", ".join(selected_cidades[:5])}{"..." if len(selected_cidades) > 5 else ""}"
    story.append(Paragraph(filtros_text, styles["Normal"]))
    story.append(Spacer(1, 20))
    
    # === KPIs PRINCIPAIS ===
    story.append(Paragraph("Principais Indicadores", section_style))
    
    # KPIs em formato de cards
    kpis_principais = [
        ["Total de Obras", str(total_obras)],
        ["Custo Fluxo Projetos", format_currency_br(investimento_exec_projetos, show_cents)],
        ["Média Próximos Meses (Projetos)", format_currency_br(media_proximos_meses_projetos, show_cents)],
        ["Saldo Projetos", format_currency_br(saldo_projetos, show_cents)],
        ["Total de Lotes", f"{total_lotes:,}".replace(",", ".")]
    ]
    
    kpis_table = Table(kpis_principais, colWidths=[4*inch, 3*inch])
    kpis_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.lightblue),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 11),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8)
    ]))
    story.append(kpis_table)
    story.append(Spacer(1, 20))
    
    # === CUSTOS GERAIS (DESPESAS FIXAS) ===
    story.append(Paragraph("Sumário de Custos Gerais (Despesas Fixas)", section_style))
    
    custos_gerais = [
        ["Custo Geral Exec. (Fixas - Proporcional)", format_currency_br(custo_geral_exec_proporcional, show_cents)]
    ]
    if show_cents:
        custos_gerais.append(["Proporção de Lotes", f"{proporcao_lotes:.1%}"])
    
    custos_table = Table(custos_gerais, colWidths=[4*inch, 3*inch])
    custos_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.lightgreen),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 11),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8)
    ]))
    story.append(custos_table)
    story.append(Spacer(1, 20))
    
    # === INDICADORES TOTAIS ===
    story.append(Paragraph("Indicadores de Custos Totais", section_style))
    
    indicadores_totais = [
        ["Custo Total do Fluxo (Geral)", format_currency_br(custo_total_fluxo_obras, show_cents)],
        ["Custo Ago/25", format_currency_br(custo_ago_25, show_cents)],
        ["Custo Set/25", format_currency_br(custo_set_25, show_cents)],
        ["Custo Out/25", format_currency_br(custo_out_25, show_cents)],
        ["Valor Restante a Pagar (Média)", format_currency_br(valor_restante_pagar_media, show_cents)]
    ]
    
    indicadores_table = Table(indicadores_totais, colWidths=[4*inch, 3*inch])
    indicadores_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.lightyellow),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 11),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8)
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
                font=dict(size=12),
                showlegend=True,
                height=400,
            )
            img_bytes = fig_tipologia.to_image(format="png", width=700, height=400, scale=2)
            img_tipologia = Image(BytesIO(img_bytes), width=6*inch, height=3*inch)
            story.append(img_tipologia)
        
        story.append(Spacer(1, 20))
        
        # 2. SALDO POR PROJETO (PIE)
        story.append(Paragraph("Saldo por Projeto", section_style))
        
        if KALEIDO_AVAILABLE:
            saldo_por_projeto = df_filtered_projetos[["Projeto", "Saldo", "Lotes"]].copy()
            saldo_por_projeto = saldo_por_projeto[saldo_por_projeto["Saldo"] > 0]
            
            if not saldo_por_projeto.empty:
                fig_saldo = px.pie(
                    saldo_por_projeto,
                    values="Saldo",
                    names="Projeto",
                    title="Saldo Restante por Projeto",
                    hover_data=["Lotes"],
                    color_discrete_sequence=px.colors.sequential.RdBu,
                )
                fig_saldo.update_layout(
                    title_font_size=14,
                    title_font_color=COLORS["primary"],
                    height=400,
                )
                fig_saldo.update_traces(
                    hovertemplate="<b>%{label}</b><br>Saldo: R$ %{value:,.2f}<br>Lotes: %{customdata[0]}<extra></extra>"
                )
                img_bytes = fig_saldo.to_image(format="png", width=700, height=400, scale=2)
                img_saldo = Image(BytesIO(img_bytes), width=6*inch, height=3*inch)
                story.append(img_saldo)
        
        story.append(Spacer(1, 20))
        
        # 3. OBRAS POR CIDADE
        story.append(Paragraph("Obras por Cidade", section_style))
        
        if KALEIDO_AVAILABLE:
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
            grafico_cidade.update_layout(
                title_font_size=14,
                title_font_color=COLORS["primary"],
                xaxis_tickangle=-45,
            )
            img_bytes = grafico_cidade.to_image(format="png", width=700, height=400, scale=2)
            img_cidade = Image(BytesIO(img_bytes), width=6*inch, height=3*inch)
            story.append(img_cidade)
        
        story.append(Spacer(1, 20))
        
        # 4. CUSTO FLUXO POR PROJETO
        story.append(Paragraph("Custo Fluxo por Projeto", section_style))
        
        if KALEIDO_AVAILABLE:
            grafico1 = px.bar(
                df_filtered_projetos,
                x="Projeto",
                y="Custo Fluxo",
                title="Custo do Fluxo por Projeto",
                labels={"Custo Fluxo": "Custo (R$)"},
                color_discrete_sequence=[COLORS["primary"]],
                hover_data=["Lotes"]
            )
            grafico1.update_layout(
                title_font_size=14,
                title_font_color=COLORS["primary"],
                xaxis_tickangle=-45,
                height=500
            )
            img_bytes = grafico1.to_image(format="png", width=800, height=500, scale=2)
            img_custo = Image(BytesIO(img_bytes), width=7*inch, height=4*inch)
            story.append(img_custo)
        
        story.append(PageBreak())
        
        # 5. DESPESAS RECORRENTES (PIES SEPARADAS)
        story.append(Paragraph("Despesas Recorrentes Detalhadas (Diesel e Mecânica)", section_style))
        
        if not df_sheet2.empty and KALEIDO_AVAILABLE:
            fig_nested_pie = make_subplots(
                rows=1,
                cols=2,
                specs=[[{"type": "pie"}, {"type": "pie"}]],
                subplot_titles=("Diesel por Empreendimento", "Mecânica por Empreendimento"),
            )
            
            # Dados dos empreendimentos para proporção (filtrado)
            empreendimentos_lotes = df_obras_iniciadas.groupby("Projeto")["Lotes"].sum().reset_index()
            total_lotes_filtered = empreendimentos_lotes["Lotes"].sum()
            
            if total_lotes_filtered > 0:
                # Diesel
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
                
                # Mecânica
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
                
                img_bytes = fig_nested_pie.to_image(format="png", width=800, height=500, scale=2)
                img_despesas = Image(BytesIO(img_bytes), width=7*inch, height=4*inch)
                story.append(img_despesas)
        
        story.append(Spacer(1, 20))
        
        # 6. CUSTOS MENSAIS E MÉDIA
        story.append(Paragraph("Custos Mensais e Média dos Próximos Meses por Projeto", section_style))
        
        if KALEIDO_AVAILABLE:
            df_custos_mensais = df_filtered_projetos[["Projeto", "ago/25", "set/25", "out/25", "Média dos Próximos Meses"]].copy()
            df_custos_mensais = df_custos_mensais.melt(id_vars=["Projeto"], var_name="Mês", value_name="Custo")
            
            fig_custos_mensais = px.bar(
                df_custos_mensais,
                x="Projeto",
                y="Custo",
                color="Mês",
                barmode="group",
                title="Custos Mensais e Média por Projeto",
                color_discrete_map={
                    "ago/25": COLORS["support1"],
                    "set/25": COLORS["support2"],
                    "out/25": COLORS["support3"],
                    "Média dos Próximos Meses": COLORS["support4"]
                }
            )
            fig_custos_mensais.update_layout(
                title_font_size=14,
                title_font_color=COLORS["primary"],
                xaxis_tickangle=-45,
                height=500
            )
            
            img_bytes = fig_custos_mensais.to_image(format="png", width=800, height=500, scale=2)
            img_custos_mensais = Image(BytesIO(img_bytes), width=7*inch, height=4*inch)
            story.append(img_custos_mensais)
        
        story.append(PageBreak())
        
        # 7. VALORES A PAGAR POR MÊS (AREA)
        story.append(Paragraph("Valores a Pagar por Mês", section_style))
        
        if KALEIDO_AVAILABLE:
            df_pagar = df_filtered_projetos[["Projeto", "ago/25", "set/25", "out/25"]].copy()
            df_pagar = df_pagar.melt(id_vars=["Projeto"], var_name="Mês", value_name="Valor a Pagar")
            
            fig_pagar = px.area(
                df_pagar,
                x="Mês",
                y="Valor a Pagar",
                color="Projeto",
                title="Valores a Pagar por Mês (Áreas Empilhadas)",
                color_discrete_sequence=ALL_GANTT_COLORS,
                category_orders={"Mês": ["ago/25", "set/25", "out/25"]},
            )
            fig_pagar.update_layout(
                title_font_size=14,
                title_font_color=COLORS["primary"],
                height=500,
                hovermode="x unified",
            )
            fig_pagar.update_traces(
                hovertemplate="<b>%{fullData.name}</b><br>Mês: %{x}<br>Valor: R$ %{y:,.2f}<extra></extra>"
            )
            
            img_bytes = fig_pagar.to_image(format="png", width=800, height=500, scale=2)
            img_pagar = Image(BytesIO(img_bytes), width=7*inch, height=4*inch)
            story.append(img_pagar)
    
    # === TABELA DE DADOS SHEET1 ===
    story.append(PageBreak())
    story.append(Paragraph("Tabela de Dados Detalhada", section_style))
    
    df_tabela = df_filtered_projetos.copy()
    
    # Formatar colunas para exibição
    for col in ["Custo Fluxo", "Saldo", "Média dos Próximos Meses"]:
        if col in df_tabela.columns:
            df_tabela[col] = df_tabela[col].apply(lambda x: format_currency_br(x, show_cents))
    
    for col in ["Início Obra", "Fim Obra"]:
        if col in df_tabela.columns:
            df_tabela[col] = df_tabela[col].dt.strftime("%d/%m/%Y").fillna("N/A")
    
    # Selecionar colunas para a tabela
    display_cols = [
        "Projeto", "Cidade", "Lotes", "Custo Fluxo", "Saldo", 
        "Média dos Próximos Meses", "Início Obra", "Fim Obra"
    ]
    df_tabela = df_tabela[display_cols]
    
    # Converter para lista de listas
    data = [df_tabela.columns.tolist()] + df_tabela.values.tolist()
    
    # Criar tabela
    table = Table(data, colWidths=[2*inch, 1*inch, 0.5*inch, 1*inch, 1*inch, 1*inch, 1*inch, 1*inch])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
        ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
        ("GRID", (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    story.append(table)
    
    # === TABELA DE DADOS SHEET2 ===
    story.append(PageBreak())
    story.append(Paragraph("Tabela de Dados Detalhada - Diesel e Mecânica", section_style))
    
    df_sheet2_display = df_sheet2.copy()
    for col in ["Custo Fluxo", "ago/25", "set/25", "out/25", "Média dos Próximos Meses"]:
        if col in df_sheet2_display.columns:
            df_sheet2_display[col] = df_sheet2_display[col].apply(lambda x: format_currency_br(x, show_cents))
    
    data_sheet2 = [df_sheet2_display.columns.tolist()] + df_sheet2_display.values.tolist()
    
    table_sheet2 = Table(data_sheet2, colWidths=[2*inch] * len(df_sheet2_display.columns))
    table_sheet2.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
        ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
        ("GRID", (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    story.append(table_sheet2)
    
    # Construir o PDF
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
                    if pdf_buffer:
                        st.download_button(
                            label="⬇️ Download Relatório PDF",
                            data=pdf_buffer.getvalue(),
                            file_name=f"dashboard_obras_{pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")}.pdf",
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
kpi_cg1.metric("🧾 Custos Fixos - Total 13 Meses", format_currency_br(custo_fluxo_mec_diesel, show_cents))
kpi_cg2.metric("🗓️ Custos Ago/25", format_currency_br(custo_ago_geral_clean, show_cents))
kpi_cg3.metric("🗓️ Custos Set/25", format_currency_br(custo_set_geral_clean, show_cents))
kpi_cg4.metric("🗓️ Custos Out/25", format_currency_br(custo_out_geral_clean, show_cents))
kpi_cg5.metric("💸 Média dos Demais Meses", format_currency_br(custo_media_proximos_geral_clean, show_cents))

st.subheader("Indicadores de Custos Totais")
kpi_ct1, kpi_ct2, kpi_ct3, kpi_ct4, kpi_ct5 = st.columns(5)
kpi_ct1.metric("💰 Custo Total do Fluxo (Geral)", format_currency_br(custo_total_fluxo_obras, show_cents))
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
            labels={"Número de Obras": "Obras", "Total de Lotes": "Lotes"},
        )
        fig_tipologia.update_traces(
            textposition="inside",
            textinfo="percent+label",
            hovertemplate="<b>%{label}</b><br>Número de Obras: %{value}<br>Total de Lotes: %{customdata[0]}<extra></extra>",
        )
        fig_tipologia.update_layout(
            title_font_size=16,
            title_font_color=COLORS["primary"],
            font=dict(size=12),
            showlegend=True,
            height=400,
        )
        st.plotly_chart(fig_tipologia, use_container_width=True)
    else:
        st.warning("Nenhuma obra para exibir com os filtros selecionados.")

with col_saldo:
    st.subheader("💰 Saldo por Projeto")
    if not df_filtered_projetos.empty:
        saldo_por_projeto = df_filtered_projetos[["Projeto", "Saldo", "Lotes"]].copy()
        saldo_por_projeto = saldo_por_projeto[saldo_por_projeto["Saldo"] > 0]

        if not saldo_por_projeto.empty:
            fig_saldo = px.pie(
                saldo_por_projeto,
                values="Saldo",
                names="Projeto",
                title="Saldo Restante por Projeto",
                hover_data=["Lotes"],
                color_discrete_sequence=px.colors.sequential.RdBu,
            )
            fig_saldo.update_layout(
                title_font_size=16,
                title_font_color=COLORS["primary"],
                height=400,
            )
            fig_saldo.update_traces(
                hovertemplate="<b>%{label}</b><br>Saldo: R$ %{value:,.2f}<br>Lotes: %{customdata[0]}<extra></extra>"
            )
            st.plotly_chart(fig_saldo, use_container_width=True)
        else:
            st.info("Não há dados de Saldo para exibir no gráfico de pizza para os filtros selecionados.")

st.markdown("---")

# Gráfico de obras por cidade (full width)
st.subheader("🏙️ Obras por Cidade")
if not df_filtered_projetos.empty:
    obras_por_cidade = df_filtered_projetos["Cidade"].value_counts().reset_index()
    obras_por_cidade.columns = ["Cidade", "Número de Obras"]
    grafico_cidade = px.bar(
        obras_por_cidade,
        x="Cidade",
        y="Número de Obras",
        title="Distribuição por Cidade",
        labels={"Número de Obras": "Quantidade de Obras"},
        height=400,
        color_discrete_sequence=[COLORS["support6"]],
    )
    grafico_cidade.update_layout(
        title_font_size=16,
        title_font_color=COLORS["primary"],
        xaxis_tickangle=-45,
    )
    st.plotly_chart(grafico_cidade, use_container_width=True)
else:
    st.warning("Nenhuma obra para exibir com os filtros selecionados.")

st.markdown("---")

# --- Análise de Custos e Cronograma ---
st.subheader("Análise de Custos e Cronograma")

# Custo do Fluxo por Projeto (largura total)
st.subheader("💰 Custo do Fluxo por Projeto")
if not df_filtered_projetos.empty:
    grafico1 = px.bar(
        df_filtered_projetos,
        x="Projeto",
        y="Custo Fluxo",
        title="Custo do Fluxo por Projeto",
        labels={"Custo Fluxo": "Custo (R$)"},
        color_discrete_sequence=[COLORS["primary"]],
        hover_data=["Lotes"],
    )
    grafico1.update_layout(
        title_font_size=16,
        title_font_color=COLORS["primary"],
        xaxis_tickangle=-45,
        font=dict(size=12),
        height=500,
    )
    st.plotly_chart(grafico1, use_container_width=True)

# Cronograma das Obras (largura total)
st.subheader("📅 Cronograma das Obras")
if not df_filtered_projetos.empty:
    df_gantt = df_filtered_projetos[["Projeto", "Início Obra", "Fim Obra"]].copy()
    df_gantt = df_gantt.dropna(subset=["Início Obra", "Fim Obra"])
    df_gantt = df_gantt[df_gantt["Fim Obra"].dt.year >= 2024]

    if not df_gantt.empty:
        fig_gantt = px.timeline(
            df_gantt,
            x_start="Início Obra",
            x_end="Fim Obra",
            y="Projeto",
            color="Projeto",
            color_discrete_sequence=ALL_GANTT_COLORS,
            title="Cronograma das Obras (a partir de 2024)",
        )
        fig_gantt.update_layout(
            title_font_size=16,
            title_font_color=COLORS["primary"],
            xaxis_title="",
            yaxis_title="",
            showlegend=False,
            height=500,
            xaxis_range=['2024-01-01', df_gantt["Fim Obra"].max()]
        )
        st.plotly_chart(fig_gantt, use_container_width=True)
    else:
        st.warning("Nenhuma obra com data de término a partir de 2024 para exibir.")

st.markdown("---")

# --- Análise de Despesas e Custos Mensais ---
st.subheader("Análise de Despesas e Custos Mensais")

# Despesas Recorrentes (duas pizzas dividindo tela)
col_pie1, col_pie2 = st.columns(2)

with col_pie1:
    st.subheader("Diesel por Empreendimento")
    if not df_sheet2.empty and not df_filtered_projetos.empty:
        # Dados dos empreendimentos para proporção (filtrado até sep/2025)
        empreendimentos_lotes = df_obras_iniciadas.groupby("Projeto")["Lotes"].sum().reset_index()
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

                fig_diesel = px.pie(
                    df_diesel_emp,
                    values="Valor",
                    names="Empreendimento",
                    title="Diesel Segmentado por Obra (até Set/25)",
                    color_discrete_sequence=px.colors.sequential.Blues_r,
                )
                fig_diesel.update_traces(
                    hovertemplate="<b>%{label}</b><br>Valor: R$ %{value:,.2f}<br>Lotes: %{customdata}<extra></extra>",
                    customdata=df_diesel_emp["Lotes"]
                )
                fig_diesel.update_layout(height=400)
                st.plotly_chart(fig_diesel, use_container_width=True)

with col_pie2:
    st.subheader("Mecânica por Empreendimento")
    if not df_sheet2.empty and not df_filtered_projetos.empty:
        if total_lotes_filtered > 0:
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

                fig_mecanica = px.pie(
                    df_mecanica_emp,
                    values="Valor",
                    names="Empreendimento",
                    title="Mecânica Segmentada por Obra (até Set/25)",
                    color_discrete_sequence=px.colors.sequential.Oranges_r,
                )
                fig_mecanica.update_traces(
                    hovertemplate="<b>%{label}</b><br>Valor: R$ %{value:,.2f}<br>Lotes: %{customdata}<extra></extra>",
                    customdata=df_mecanica_emp["Lotes"]
                )
                fig_mecanica.update_layout(height=400)
                st.plotly_chart(fig_mecanica, use_container_width=True)

# Custos Mensais e Média (largura total)
st.subheader("Custos Mensais e Média dos Próximos Meses por Projeto")
if not df_filtered_projetos.empty:
    df_custos_mensais = df_filtered_projetos[
        ["Projeto", "ago/25", "set/25", "out/25", "Média dos Próximos Meses"]
    ].copy()
    df_custos_mensais = df_custos_mensais.melt(
        id_vars=["Projeto"], var_name="Mês", value_name="Custo"
    )

    fig_custos_mensais = px.bar(
        df_custos_mensais,
        x="Projeto",
        y="Custo",
        color="Mês",
        barmode="group",
        title="Custos Mensais e Média por Projeto",
        color_discrete_map={
            "ago/25": COLORS["support1"],
            "set/25": COLORS["support2"],
            "out/25": COLORS["support3"],
            "Média dos Próximos Meses": COLORS["support4"],
        },
    )
    fig_custos_mensais.update_layout(
        title_font_size=16,
        title_font_color=COLORS["primary"],
        xaxis_tickangle=-45,
        height=500,
    )
    st.plotly_chart(fig_custos_mensais, use_container_width=True)

st.markdown("---")

# --- Gráfico de Valores a Pagar por Mês (Áreas Empilhadas) ---
st.subheader("💰 Valores a Pagar por Mês")
if not df_filtered_projetos.empty:
    df_pagar = df_filtered_projetos[["Projeto", "ago/25", "set/25", "out/25"]].copy()
    
    df_pagar = df_pagar.melt(id_vars=["Projeto"], var_name="Mês", value_name="Valor a Pagar")
    
    fig_pagar = px.area(
        df_pagar,
        x="Mês",
        y="Valor a Pagar",
        color="Projeto",
        title="Valores a Pagar por Mês (Áreas Empilhadas)",
        color_discrete_sequence=ALL_GANTT_COLORS,
        category_orders={"Mês": ["ago/25", "set/25", "out/25"]},
    )
    fig_pagar.update_layout(
        title_font_size=16,
        title_font_color=COLORS["primary"],
        height=500,
        hovermode="x unified",
    )
    fig_pagar.update_traces(
        hovertemplate="<b>%{fullData.name}</b><br>Mês: %{x}<br>Valor: R$ %{y:,.2f}<extra></extra>"
    )
    st.plotly_chart(fig_pagar, use_container_width=True)
else:
    st.warning("Nenhuma obra para exibir com os filtros selecionados.")

st.markdown("---")

# --- Tabela final Sheet1 ---
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
st.subheader("📋 Tabela Detalhada das Despesas Fixas - Diesel e Mecânica")
if not df_sheet2.empty:
    df_display_sheet2 = df_sheet2.copy()
    for col in ["Custo Fluxo", "ago/25", "set/25", "out/25", "Média dos Próximos Meses"]:
        if col in df_display_sheet2.columns:
            df_display_sheet2[col] = df_display_sheet2[col].apply(lambda x: format_currency_br(x, show_cents))
    st.dataframe(df_display_sheet2, use_container_width=True)
else:
    st.info("Não há dados de despesas fixas para exibir.")

st.markdown("---")