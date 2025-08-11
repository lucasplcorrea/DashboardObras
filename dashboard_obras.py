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

st.title("📊 Dashboard de Obras - Cadastro Geral")

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
    """
    )

# --- Melhoria 3: Filtros com prioridade para obras ---
st.header("⚙️ Filtros")
col1, col2 = st.columns(2)

with col1:
    # Filtro principal: Obras
    obras_options = df_projetos["Projeto"].dropna().unique().tolist()
    selected_obras = st.multiselect(
        "🏗️ Filtrar por Nome da Obra (Principal)",
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
        "🏙️ Filtrar por Cidade (Secundário)",
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
st.subheader("📄 Exportar Dashboard")

# Função para criar PDF do dashboard (melhorada para incluir todos os dados)
def create_pdf_report():
    """Cria um relatório PDF completo com todos os dados do dashboard respeitando os filtros"""

    # Configurar matplotlib para português
    plt.rcParams["font.family"] = "DejaVu Sans"
    plt.rcParams["font.size"] = 8

    buffer = BytesIO()

    with PdfPages(buffer) as pdf:
        # Página 1: KPIs Principais e Filtros Aplicados
        fig = plt.figure(figsize=(11, 8))
        fig.suptitle("Dashboard de Obras - Relatório Completo", fontsize=16, fontweight="bold")
        
        # Informações dos filtros aplicados
        gs = fig.add_gridspec(4, 3, height_ratios=[0.5, 1, 1, 0.3])
        
        # Filtros aplicados
        ax_filtros = fig.add_subplot(gs[0, :])
        ax_filtros.axis("off")
        filtros_text = f"Filtros Aplicados:\nObras: {', '.join(selected_obras[:3])}{'...' if len(selected_obras) > 3 else ''}\n"
        filtros_text += f"Cidades: {', '.join(selected_cidades[:3])}{'...' if len(selected_cidades) > 3 else ''}"
        ax_filtros.text(0.5, 0.5, filtros_text, ha="center", va="center", fontsize=10, 
                       bbox=dict(boxstyle="round,pad=0.3", facecolor="lightgray", alpha=0.7))

        # KPIs principais (2x3 grid)
        kpis_data = [
            ("Total de Obras", total_obras, "lightblue"),
            ("Custo Fluxo Projetos", format_currency_br(investimento_exec_projetos, show_cents), "lightgreen"),
            ("Total de Lotes", f"{total_lotes:,}".replace(",", "."), "lightyellow"),
            ("Saldo Projetos", format_currency_br(saldo_projetos, show_cents), "lightcoral"),
            ("Média Próximos Meses", format_currency_br(media_proximos_meses_projetos, show_cents), "lightpink"),
            ("Custo Geral (Proporcional)", format_currency_br(custo_geral_exec_proporcional, show_cents), "lightcyan")
        ]
        
        for i, (label, valor, cor) in enumerate(kpis_data):
            row, col = divmod(i, 3)
            ax = fig.add_subplot(gs[row + 1, col])
            ax.text(0.5, 0.5, f"{label}\n{valor}", ha="center", va="center", fontsize=12,
                    fontweight="bold", bbox=dict(boxstyle="round,pad=0.3", facecolor=cor))
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
            ax.axis("off")

        # Indicadores de custos totais na parte inferior
        ax_custos_totais = fig.add_subplot(gs[3, :])
        ax_custos_totais.axis("off")
        custos_text = f"Indicadores Totais: Custo Total Fluxo: {format_currency_br(custo_total_fluxo_obras, show_cents)} | "
        custos_text += f"Ago/25: {format_currency_br(custo_ago_25, show_cents)} | "
        custos_text += f"Set/25: {format_currency_br(custo_set_25, show_cents)} | "
        custos_text += f"Out/25: {format_currency_br(custo_out_25, show_cents)}"
        ax_custos_totais.text(0.5, 0.5, custos_text, ha="center", va="center", fontsize=9,
                            bbox=dict(boxstyle="round,pad=0.3", facecolor="lavender"))

        plt.tight_layout()
        pdf.savefig(fig, bbox_inches="tight")
        plt.close()

        # Página 2: Custo Fluxo por Projeto
        if not df_filtered_projetos.empty:
            fig, ax = plt.subplots(figsize=(11, 8))
            projetos = df_filtered_projetos["Projeto"].tolist()
            custos = df_filtered_projetos["Custo Fluxo"].tolist()

            bars = ax.bar(range(len(projetos)), custos, color=COLORS["primary"])
            ax.set_xlabel("Projetos", fontweight="bold")
            ax.set_ylabel("Custo (R$)", fontweight="bold")
            ax.set_title("Custo Fluxo por Projeto", fontsize=14, fontweight="bold")
            ax.set_xticks(range(len(projetos)))
            ax.set_xticklabels(projetos, rotation=45, ha="right")

            # Adicionar valores nas barras
            for i, bar in enumerate(bars):
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width() / 2.0, height,
                        f"R$ {height:,.0f}".replace(",", "."),
                        ha="center", va="bottom", fontsize=8)

            # Formatação do eixo y
            ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f"R$ {x:,.0f}".replace(",", ".")))
            plt.xticks(rotation=45, ha="right")
            plt.tight_layout()
            pdf.savefig(fig, bbox_inches="tight")
            plt.close()

        # Página 3: Distribuição por Tipologia e Saldo
        if not df_filtered_projetos.empty:
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 8))
            fig.suptitle("Distribuição por Tipologia e Saldo por Projeto", fontsize=14, fontweight="bold")

            # Gráfico de tipologia
            tipologia_counts = df_filtered_projetos["Tipologia"].value_counts()
            if not tipologia_counts.empty:
                wedges, texts, autotexts = ax1.pie(tipologia_counts.values, labels=tipologia_counts.index,
                                                  autopct="%1.1f%%", startangle=90)
                ax1.set_title("Obras por Tipologia")

            # Gráfico de saldo por projeto
            saldo_por_projeto = df_filtered_projetos.groupby("Projeto")["Saldo"].sum().reset_index()
            saldo_por_projeto = saldo_por_projeto[saldo_por_projeto["Saldo"] > 0]
            
            if not saldo_por_projeto.empty:
                wedges, texts, autotexts = ax2.pie(saldo_por_projeto["Saldo"], 
                                                  labels=saldo_por_projeto["Projeto"],
                                                  autopct="%1.1f%%", startangle=90)
                ax2.set_title("Saldo por Projeto")
            else:
                ax2.text(0.5, 0.5, "Não há dados de saldo\npara exibir", ha="center", va="center")
                ax2.set_xlim(0, 1)
                ax2.set_ylim(0, 1)

            plt.tight_layout()
            pdf.savefig(fig, bbox_inches="tight")
            plt.close()

        # Página 4: Cronograma (Gantt) das Obras
        if not df_filtered_projetos.empty:
            gantt_data = df_filtered_projetos[["Projeto", "Início Obra", "Fim Obra"]].dropna()
            if not gantt_data.empty:
                fig, ax = plt.subplots(figsize=(11, 8))
                
                # Filtrar para começar a visualização em 2024
                gantt_data_filtered = gantt_data.copy()
                gantt_data_filtered.loc[gantt_data_filtered["Início Obra"] < "2024-01-01", "Início Obra"] = pd.to_datetime("2024-01-01")

                for i, (_, row) in enumerate(gantt_data_filtered.iterrows()):
                    start_date = row["Início Obra"]
                    end_date = row["Fim Obra"]
                    ax.barh(i, (end_date - start_date).days, left=start_date, 
                           color=ALL_GANTT_COLORS[i % len(ALL_GANTT_COLORS)], alpha=0.7)

                ax.set_yticks(range(len(gantt_data_filtered)))
                ax.set_yticklabels(gantt_data_filtered["Projeto"], fontsize=8)
                ax.set_xlabel("Timeline", fontweight="bold")
                ax.set_title("Cronograma das Obras", fontsize=14, fontweight="bold")
                
                # Formatação das datas
                import matplotlib.dates as mdates
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%Y'))
                ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
                plt.xticks(rotation=45)
                
                plt.tight_layout()
                pdf.savefig(fig, bbox_inches="tight")
                plt.close()

        # Página 5: Valores Mensais e Despesas Fixas
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 8))
        fig.suptitle("Valores Mensais e Despesas Fixas", fontsize=14, fontweight="bold")

        # Gráfico de valores mensais
        meses = ["Ago/25", "Set/25", "Out/25", "Média Próximos"]
        valores_mensais = [custo_ago_25, custo_set_25, custo_out_25, valor_restante_pagar_media]
        
        ax1.plot(meses, valores_mensais, marker='o', linewidth=3, markersize=8, color=COLORS["support7"])
        ax1.set_title("Valores a Pagar por Mês")
        ax1.set_ylabel("Valor (R$)")
        ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f"R$ {x:,.0f}".replace(",", ".")))
        
        # Adicionar valores nos pontos
        for i, valor in enumerate(valores_mensais):
            ax1.annotate(format_currency_br(valor, False), (i, valor), 
                        textcoords="offset points", xytext=(0,10), ha='center')

        # Gráfico de despesas fixas (se houver dados da Sheet2)
        if not df_sheet2.empty:
            diesel_data = df_sheet2[df_sheet2["Tipologia"].str.contains("Diesel", na=False)]
            mecanica_data = df_sheet2[df_sheet2["Tipologia"].str.contains("Mecanica", na=False)]
            
            despesas_labels = []
            despesas_valores = []
            
            if not diesel_data.empty:
                despesas_labels.append("Diesel")
                despesas_valores.append(diesel_data["Custo Fluxo"].iloc[0])
            
            if not mecanica_data.empty:
                despesas_labels.append("Mecânica")
                despesas_valores.append(mecanica_data["Custo Fluxo"].iloc[0])
            
            if despesas_labels:
                ax2.bar(despesas_labels, despesas_valores, color=[COLORS["support7"], COLORS["support8"]])
                ax2.set_title("Despesas Fixas (Diesel e Mecânica)")
                ax2.set_ylabel("Valor (R$)")
                ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f"R$ {x:,.0f}".replace(",", ".")))
                
                # Adicionar valores nas barras
                for i, valor in enumerate(despesas_valores):
                    ax2.text(i, valor, format_currency_br(valor, False), 
                           ha="center", va="bottom", fontweight="bold")
        else:
            ax2.text(0.5, 0.5, "Não há dados de despesas fixas\npara exibir", 
                    ha="center", va="center", transform=ax2.transAxes)

        plt.tight_layout()
        pdf.savefig(fig, bbox_inches="tight")
        plt.close()

        # Página 6: Obras por Cidade e Empresa
        if not df_filtered_projetos.empty:
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 8))
            fig.suptitle("Distribuição por Cidade e Empresa", fontsize=14, fontweight="bold")

            # Obras por cidade
            obras_por_cidade = df_filtered_projetos["Cidade"].value_counts()
            if not obras_por_cidade.empty:
                ax1.bar(obras_por_cidade.index, obras_por_cidade.values, color=COLORS["support6"])
                ax1.set_title("Número de Obras por Cidade")
                ax1.set_xlabel("Cidade")
                ax1.set_ylabel("Número de Obras")
                plt.setp(ax1.get_xticklabels(), rotation=45, ha="right")

            # Custo médio por empresa
            if "Empresa desenvolvedora" in df_filtered_projetos.columns:
                empresa_custo = df_filtered_projetos.groupby("Empresa desenvolvedora")["Custo Fluxo"].mean()
                if not empresa_custo.empty:
                    ax2.bar(empresa_custo.index, empresa_custo.values, color=COLORS["support5"])
                    ax2.set_title("Custo Fluxo Médio por Empresa Desenvolvedora")
                    ax2.set_xlabel("Empresa")
                    ax2.set_ylabel("Custo Médio (R$)")
                    ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f"R$ {x:,.0f}".replace(",", ".")))
                    plt.setp(ax2.get_xticklabels(), rotation=45, ha="right")

            plt.tight_layout()
            pdf.savefig(fig, bbox_inches="tight")
            plt.close()

        # Página 7: Tabela Detalhada das Obras (Principal)
        if not df_filtered_projetos.empty:
            # Dividir a tabela em páginas se necessário
            colunas_tabela = ["Projeto", "Cidade", "Tipologia", "Custo Fluxo", "Saldo", "Lotes", "% Avanço Físico"]
            
            # Filtrar apenas colunas que existem
            colunas_existentes = [col for col in colunas_tabela if col in df_filtered_projetos.columns]
            
            df_tabela = df_filtered_projetos[colunas_existentes].copy()
            
            # Formatação das colunas monetárias
            for col in ["Custo Fluxo", "Saldo"]:
                if col in df_tabela.columns:
                    df_tabela[col] = df_tabela[col].apply(lambda x: format_currency_br(x, False))
            
            # Formatação da coluna de lotes
            if "Lotes" in df_tabela.columns:
                df_tabela["Lotes"] = df_tabela["Lotes"].apply(lambda x: f"{x:,}".replace(",", "."))
            
            # Formatação da coluna de avanço físico
            if "% Avanço Físico" in df_tabela.columns:
                df_tabela["% Avanço Físico"] = df_tabela["% Avanço Físico"].apply(lambda x: f"{x:.1f}%" if pd.notna(x) else "N/A")

            # Dividir em chunks de 25 linhas
            chunk_size = 25
            for chunk_num, start_idx in enumerate(range(0, len(df_tabela), chunk_size)):
                end_idx = min(start_idx + chunk_size, len(df_tabela))
                chunk_data = df_tabela.iloc[start_idx:end_idx]
                
                fig, ax = plt.subplots(figsize=(11, 8))
                ax.axis("tight")
                ax.axis("off")

                table = ax.table(cellText=chunk_data.values, colLabels=chunk_data.columns,
                               cellLoc="center", loc="center")
                
                table.auto_set_font_size(False)
                table.set_fontsize(7)
                table.scale(1.0, 1.2)
                
                # Colorir cabeçalho
                for i in range(len(chunk_data.columns)):
                    table[(0, i)].set_facecolor('#4472C4')
                    table[(0, i)].set_text_props(weight='bold', color='white')

                titulo_pagina = f"Tabela Detalhada das Obras - Página {chunk_num + 1}"
                if len(df_tabela) > chunk_size:
                    titulo_pagina += f" (Linhas {start_idx + 1} a {end_idx})"
                
                ax.set_title(titulo_pagina, fontsize=12, fontweight="bold", pad=20)

                plt.tight_layout()
                pdf.savefig(fig, bbox_inches="tight")
                plt.close()

        # Página 8: Tabela de Despesas Fixas (Sheet2)
        if not df_sheet2.empty:
            fig, ax = plt.subplots(figsize=(11, 8))
            ax.axis("tight")
            ax.axis("off")

            # Preparar dados da Sheet2 para exibição
            df_sheet2_display = df_sheet2.copy()
            
            # Formatação das colunas monetárias da Sheet2
            cols_monetarias_sheet2 = ["Custo Fluxo", "ago/25", "set/25", "out/25", "Média dos Próximos Meses"]
            for col in cols_monetarias_sheet2:
                if col in df_sheet2_display.columns:
                    df_sheet2_display[col] = df_sheet2_display[col].apply(lambda x: format_currency_br(x, False))

            # Selecionar colunas mais relevantes para o PDF
            colunas_sheet2 = ["Projeto", "Tipologia", "Custo Fluxo", "ago/25", "set/25", "out/25"]
            colunas_sheet2_existentes = [col for col in colunas_sheet2 if col in df_sheet2_display.columns]
            
            if colunas_sheet2_existentes:
                df_sheet2_filtered = df_sheet2_display[colunas_sheet2_existentes]
                
                table = ax.table(cellText=df_sheet2_filtered.values, 
                               colLabels=df_sheet2_filtered.columns,
                               cellLoc="center", loc="center")
                
                table.auto_set_font_size(False)
                table.set_fontsize(9)
                table.scale(1.2, 1.5)
                
                # Colorir cabeçalho
                for i in range(len(df_sheet2_filtered.columns)):
                    table[(0, i)].set_facecolor('#70AD47')
                    table[(0, i)].set_text_props(weight='bold', color='white')

            ax.set_title("Despesas Fixas Detalhadas (Diesel e Mecânica)", 
                        fontsize=12, fontweight="bold", pad=20)

            plt.tight_layout()
            pdf.savefig(fig, bbox_inches="tight")
            plt.close()

        # Página 9: Estatísticas Complementares
        if not df_filtered_projetos.empty:
            fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(11, 8))
            fig.suptitle("Estatísticas Complementares", fontsize=14, fontweight="bold")

            # Percentual de avanço físico por projeto
            if "% Avanço Físico" in df_filtered_projetos.columns:
                avanco_fisico = df_filtered_projetos[df_filtered_projetos["% Avanço Físico"] > 0]
                if not avanco_fisico.empty:
                    ax1.bar(range(len(avanco_fisico)), avanco_fisico["% Avanço Físico"], 
                           color=COLORS["support1"], alpha=0.7)
                    ax1.set_title("% Avanço Físico por Projeto")
                    ax1.set_ylabel("Avanço (%)")
                    ax1.set_xticks(range(len(avanco_fisico)))
                    ax1.set_xticklabels([proj[:15] + "..." if len(proj) > 15 else proj 
                                        for proj in avanco_fisico["Projeto"]], 
                                       rotation=45, ha="right", fontsize=8)

            # Distribuição de lotes por tipologia
            if "Tipologia" in df_filtered_projetos.columns and "Lotes" in df_filtered_projetos.columns:
                lotes_por_tip = df_filtered_projetos.groupby("Tipologia")["Lotes"].sum()
                if not lotes_por_tip.empty:
                    ax2.pie(lotes_por_tip.values, labels=lotes_por_tip.index, autopct="%1.1f%%")
                    ax2.set_title("Distribuição de Lotes por Tipologia")

            # Tempo de obra vs Custo (scatter plot)
            if "Tempo de Obra" in df_filtered_projetos.columns:
                tempo_obra = df_filtered_projetos[df_filtered_projetos["Tempo de Obra"] > 0]
                if not tempo_obra.empty:
                    ax3.scatter(tempo_obra["Tempo de Obra"], tempo_obra["Custo Fluxo"], 
                              color=COLORS["support3"], alpha=0.6, s=60)
                    ax3.set_xlabel("Tempo de Obra (meses)")
                    ax3.set_ylabel("Custo Fluxo (R$)")
                    ax3.set_title("Relação Tempo vs Custo")
                    ax3.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f"R$ {x:,.0f}".replace(",", ".")))

            # Saldo restante por etapa
            if "Etapa" in df_filtered_projetos.columns:
                saldo_por_etapa = df_filtered_projetos.groupby("Etapa")["Saldo"].sum()
                saldo_por_etapa = saldo_por_etapa[saldo_por_etapa > 0]
                if not saldo_por_etapa.empty:
                    ax4.bar(saldo_por_etapa.index, saldo_por_etapa.values, color=COLORS["support2"])
                    ax4.set_title("Saldo Restante por Etapa")
                    ax4.set_ylabel("Saldo (R$)")
                    ax4.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f"R$ {x:,.0f}".replace(",", ".")))
                    plt.setp(ax4.get_xticklabels(), rotation=45, ha="right")

            plt.tight_layout()
            pdf.savefig(fig, bbox_inches="tight")
            plt.close()

        # Página 10: Tabela Completa com Todas as Colunas (se solicitado)
        if not df_filtered_projetos.empty and len(df_filtered_projetos.columns) > 15:
            # Selecionar todas as colunas principais
            all_display_columns = [
                "ID", "Empresa desenvolvedora", "Sócia", "Projeto", "Tipologia", "Cidade", "UF", "Etapa",
                "Custo Raso Meta", "Custo Fluxo", "Percentual Incorrido do Fluxo%", "ago/25", "set/25", "out/25",
                "Média dos Próximos Meses", "Saldo", "Índice Ômega", "% Avanço Físico", "%Avanço Financeiro",
                "Tempo de Obra", "Início Obra", "Fim Obra", "Meses Restantes Pós Out/25", "Lotes"
            ]

            # Filtrar apenas colunas que existem
            colunas_existentes_completas = [col for col in all_display_columns if col in df_filtered_projetos.columns]
            
            if len(colunas_existentes_completas) > 7:  # Se há muitas colunas, criar tabela extendida
                df_tabela_completa = df_filtered_projetos[colunas_existentes_completas].copy()
                
                # Formatação das colunas
                currency_cols = ["Custo Raso Meta", "Custo Fluxo", "ago/25", "set/25", "out/25", 
                               "Média dos Próximos Meses", "Saldo"]
                for col in currency_cols:
                    if col in df_tabela_completa.columns:
                        df_tabela_completa[col] = df_tabela_completa[col].apply(lambda x: format_currency_br(x, False))

                # Formatação de percentuais
                percent_cols = ["Percentual Incorrido do Fluxo%", "% Avanço Físico", "%Avanço Financeiro"]
                for col in percent_cols:
                    if col in df_tabela_completa.columns:
                        df_tabela_completa[col] = df_tabela_completa[col].apply(lambda x: f"{x:.1f}%" if pd.notna(x) else "N/A")

                # Formatação de datas
                date_cols = ["Início Obra", "Fim Obra"]
                for col in date_cols:
                    if col in df_tabela_completa.columns:
                        df_tabela_completa[col] = df_tabela_completa[col].apply(
                            lambda x: x.strftime('%d/%m/%Y') if pd.notna(x) and hasattr(x, 'strftime') else 'N/A'
                        )

                # Dividir em chunks ainda menores para tabela extendida (15 linhas)
                chunk_size_extended = 15
                for chunk_num, start_idx in enumerate(range(0, len(df_tabela_completa), chunk_size_extended)):
                    end_idx = min(start_idx + chunk_size_extended, len(df_tabela_completa))
                    chunk_data = df_tabela_completa.iloc[start_idx:end_idx]
                    
                    # Dividir colunas em duas tabelas se necessário
                    mid_col = len(chunk_data.columns) // 2
                    
                    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 8))
                    fig.suptitle(f"Tabela Completa das Obras - Página {chunk_num + 1}", fontsize=12, fontweight="bold")

                    # Primeira metade das colunas
                    chunk_data_1 = chunk_data.iloc[:, :mid_col]
                    table1 = ax1.table(cellText=chunk_data_1.values, colLabels=chunk_data_1.columns,
                                      cellLoc="center", loc="center")
                    table1.auto_set_font_size(False)
                    table1.set_fontsize(6)
                    table1.scale(1.0, 1.1)
                    ax1.set_title(f"Colunas 1-{mid_col}", fontsize=10)
                    ax1.axis("off")

                    # Segunda metade das colunas
                    if mid_col < len(chunk_data.columns):
                        chunk_data_2 = chunk_data.iloc[:, mid_col:]
                        table2 = ax2.table(cellText=chunk_data_2.values, colLabels=chunk_data_2.columns,
                                          cellLoc="center", loc="center")
                        table2.auto_set_font_size(False)
                        table2.set_fontsize(6)
                        table2.scale(1.0, 1.1)
                        ax2.set_title(f"Colunas {mid_col+1}-{len(chunk_data.columns)}", fontsize=10)
                    ax2.axis("off")

                    plt.tight_layout()
                    pdf.savefig(fig, bbox_inches="tight")
                    plt.close()

    buffer.seek(0)
    return buffer

if st.button("📥 Exportar Dashboard para PDF"):
    try:
        with st.spinner("Gerando relatório PDF..."):
            pdf_buffer = create_pdf_report()

            st.download_button(
                label="📥 Download do Relatório PDF",
                data=pdf_buffer.getvalue(),
                file_name=f"dashboard_obras_relatorio_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                mime="application/pdf",
            )
            st.success("Relatório PDF gerado com sucesso!")
    except Exception as e:
        st.error(f"Erro ao gerar PDF: {str(e)}")
        st.info("Funcionalidade de exportação para PDF em desenvolvimento. Tente novamente mais tarde.")

st.markdown("---")

# KPIs principais com formatação condicional
kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
kpi1.metric("🏗️ Total de Obras", total_obras)
kpi2.metric(
    "🧾 Custo Fluxo Projetos", format_currency_br(investimento_exec_projetos, show_cents)
)
kpi3.metric(
    "📈 Média Próximos Meses (Projetos)",
    format_currency_br(media_proximos_meses_projetos, show_cents),
)
kpi4.metric("💰 Saldo Projetos", format_currency_br(saldo_projetos, show_cents))
kpi5.metric("🏘️ Total de Lotes", f"{total_lotes:,}".replace(",", "."))

st.markdown("---")

st.subheader("Sumário de Custos Gerais (Despesas Fixas)")
kpi_cg1, kpi_cg2 = st.columns(2)
kpi_cg1.metric("🧾 Custo Geral Exec. (Fixas - Proporcional)", format_currency_br(custo_geral_exec_proporcional, show_cents))
if show_cents:
    kpi_cg2.metric("📊 Proporção de Lotes", f"{proporcao_lotes:.1%}")

st.subheader("Indicadores de Custos Totais")
kpi_ct1, kpi_ct2, kpi_ct3, kpi_ct4, kpi_ct5 = st.columns(5)
kpi_ct1.metric(
    "💰 Custo Total do Fluxo (Geral)", format_currency_br(custo_total_fluxo_obras, show_cents)
)
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

# Gráfico de linhas e pontos para Custos Mensais e Média dos Próximos Meses por Projeto (Sheet 2)
st.write("**Custos Mensais e Média dos Próximos Meses por Projeto (Segmentado por Tipo de Custo):**")

if not df_sheet2.empty:
    # Preparar dados para linhas e pontos por tipo de custo
    monthly_data = []
    for _, row in df_sheet2.iterrows():
        projeto = row["Projeto"]
        tipologia = "Diesel" if "Diesel" in row["Tipologia"] else "Mecânica"

        monthly_data.extend(
            [
                {"Projeto": projeto, "Tipo": tipologia, "Mês": "Ago/25", "Valor": row["ago/25"]},
                {"Projeto": projeto, "Tipo": tipologia, "Mês": "Set/25", "Valor": row["set/25"]},
                {"Projeto": projeto, "Tipo": tipologia, "Mês": "Out/25", "Valor": row["out/25"]},
                {
                    "Projeto": projeto,
                    "Tipo": tipologia,
                    "Mês": "Média Próximos",
                    "Valor": row["Média dos Próximos Meses"],
                },
            ]
        )

    df_monthly_costs = pd.DataFrame(monthly_data)

    fig_monthly_costs_sheet2 = px.line(
        df_monthly_costs,
        x="Mês",
        y="Valor",
        color="Tipo",
        markers=True,
        labels={
            "Valor": "Valor (R$)",
            "Tipo": "Tipo de Custo",
        },
        color_discrete_sequence=[COLORS["support7"], COLORS["support8"]],
    )
    fig_monthly_costs_sheet2.update_traces(
        mode="lines+markers",
        line=dict(width=3),
        marker=dict(size=10),
    )
    st.plotly_chart(fig_monthly_costs_sheet2, use_container_width=True)
else:
    st.info("Não há dados de custos mensais para exibir.")

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

# --- Novo Gráfico: Valores a Pagar por Mês (Linhas com pontos) ---
st.subheader("💰 Valores a Pagar por Mês")

# Criar um DataFrame para os valores mensais
monthly_costs = pd.DataFrame(
    {
        "Mês": ["Agosto/25", "Setembro/25", "Outubro/25", "Média Próximos Meses"],
        "Valor": [custo_ago_25, custo_set_25, custo_out_25, valor_restante_pagar_media],
    }
)

grafico_mensal = px.line(
    monthly_costs,
    x="Mês",
    y="Valor",
    labels={"Valor": "Valor (R$)"},
    height=400,
    markers=True,
    line_shape="linear",
)
grafico_mensal.update_traces(
    line=dict(color=COLORS["support7"], width=3),
    marker=dict(size=10, color=COLORS["support8"]),
)
st.plotly_chart(grafico_mensal, use_container_width=True)

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
