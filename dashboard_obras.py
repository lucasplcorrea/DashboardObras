import streamlit as st
import pandas as pd
import plotly.express as px

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
    "support10": "#806EAF"
}

# Adicionando mais 10 cores para o gráfico de Gantt
ADDITIONAL_COLORS = [
    "#FF6347", "#4682B4", "#DAA520", "#8A2BE2", "#3CB371",
    "#FFDAB9", "#CD5C5C", "#40E0D0", "#EE82EE", "#7B68EE"
]

ALL_GANTT_COLORS = list(COLORS.values()) + ADDITIONAL_COLORS

# Função para formatar valores como moeda brasileira
def format_currency_br(value):
    if pd.isna(value):
        return "R$ 0,00"
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# --- Carregamento dos dados ---
@st.cache_data
def load_data():
    df = pd.read_excel("./cadastro_obras_simplificado.xlsx", sheet_name="Sheet1")
    df_sheet2 = pd.read_excel("./cadastro_obras_simplificado.xlsx", sheet_name="Sheet2")
    
    # Preencher valores nulos para colunas numéricas e de data
    numeric_cols = [
        "Custo Raso Meta", "Custo Fluxo", "Percentual Incorrido do Fluxo%",
        "ago/25", "set/25", "out/25", "Média dos Próximos Meses", "Saldo",
        "Índice Ômega", "% Avanço Físico", "%Avanço Financeiro", "Tempo de Obra"
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
despesas_fixas = pd.DataFrame({
    'ID': [900, 901],
    'Projeto': ['Diesel dos Equipamentos', 'Custo de Operação da Mecanica'],
    'Custo Fluxo': [779000 * 12 / 13, 641891 * 12 / 13] # Valores diluídos por 13 meses
})

# Concatenar despesas fixas com os custos gerais lidos do excel, se houver
df_custos_gerais = pd.concat([df_custos_gerais_from_excel, despesas_fixas], ignore_index=True)

st.title("📊 Dashboard de Obras - Cadastro Geral")

# --- Observações Fixas e Filtros (na sidebar para serem mais discretos) ---
with st.sidebar:
    st.header("📝 Observações")
    st.markdown("""
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
    """)
    st.header("⚙️ Filtros")
    cidades = st.multiselect("Filtrar por Cidade", options=df_projetos["Cidade"].dropna().unique(), default=df_projetos["Cidade"].dropna().unique())
    empresas = st.multiselect("Filtrar por Empresa Desenvolvedora", options=df_projetos["Empresa desenvolvedora"].dropna().unique(), default=df_projetos["Empresa desenvolvedora"].dropna().unique())

df_filtered_projetos = df_projetos[df_projetos["Cidade"].isin(cidades) & df_projetos["Empresa desenvolvedora"].isin(empresas)]

# --- KPIs de Projetos ---
total_obras = len(df_filtered_projetos)
investimento_exec_projetos = df_filtered_projetos["Custo Fluxo"].sum()
media_proximos_meses_projetos = df_filtered_projetos["Média dos Próximos Meses"].sum()
saldo_projetos = df_filtered_projetos["Saldo"].sum()

# --- KPIs de Custos Gerais ---
custo_geral_exec = df_custos_gerais["Custo Fluxo"].sum()

# --- Novos Indicadores Solicitados ---
custo_total_fluxo_obras = investimento_exec_projetos + custo_geral_exec
custo_ago_25 = df_filtered_projetos["ago/25"].sum()
custo_set_25 = df_filtered_projetos["set/25"].sum()
custo_out_25 = df_filtered_projetos["out/25"].sum()
valor_restante_pagar_media = media_proximos_meses_projetos # Já é a soma da média dos próximos meses
saldo_total_acumulado = saldo_projetos # Já é o saldo total dos projetos

# --- Novas Métricas ---
# Custo Total Geral (Projetos + Custos Gerais)
custo_total_exec_geral = investimento_exec_projetos + custo_geral_exec

# Custo por Obra (Média)
custo_medio_por_obra_exec = investimento_exec_projetos / total_obras if total_obras > 0 else 0

kpi1, kpi2, kpi3, kpi4 = st.columns(4)
kpi1.metric("🏗️ Total de Obras", total_obras)
kpi2.metric("🧾 Custo Fluxo Projetos", format_currency_br(investimento_exec_projetos))
kpi3.metric("📈 Média Próximos Meses (Projetos)", format_currency_br(media_proximos_meses_projetos))
kpi4.metric("💰 Saldo Projetos", format_currency_br(saldo_projetos))

st.markdown("---")

st.subheader("Sumário de Custos Gerais (Despesas Fixas)")
kpi_cg1, kpi_cg2 = st.columns(2)
kpi_cg1.metric("🧾 Custo Geral Exec. (Fixas)", format_currency_br(custo_geral_exec))

# Exibir as despesas fixas individualmente
# REMOVIDO: st.write("**Detalhamento das Despesas Fixas:**")
# REMOVIDO: for index, row in despesas_fixas.iterrows():
# REMOVIDO:     st.write(f"- {row["Projeto"]}: {format_currency_br(row["Custo Fluxo"])}")

st.subheader("Indicadores de Custos Totais")
kpi_ct1, kpi_ct2, kpi_ct3, kpi_ct4, kpi_ct5 = st.columns(5)
kpi_ct1.metric("💰 Custo Total do Fluxo (Geral)", format_currency_br(custo_total_fluxo_obras))
kpi_ct2.metric("🗓️ Custo Ago/25", format_currency_br(custo_ago_25))
kpi_ct3.metric("🗓️ Custo Set/25", format_currency_br(custo_set_25))
kpi_ct4.metric("🗓️ Custo Out/25", format_currency_br(custo_out_25))
kpi_ct5.metric("💸 Valor Restante a Pagar (Média)", format_currency_br(valor_restante_pagar_media))

st.markdown("---")

# --- Novos Indicadores de Etapa e Tipologia ---
col_saldo, col_tipologia = st.columns(2)

with col_tipologia:
    st.subheader("📊 Obras por Tipologia")
    tipologia_counts = df_filtered_projetos["Tipologia"].value_counts().reset_index()
    tipologia_counts.columns = ["Tipologia", "Número de Obras"]
    fig_tipologia = px.pie(tipologia_counts, values="Número de Obras", names="Tipologia", title="Distribuição por Tipologia",
                           color_discrete_sequence=px.colors.sequential.Greens_r)
    st.plotly_chart(fig_tipologia, use_container_width=True)

with col_saldo:
    st.subheader("📊 Saldo por Projeto")
    saldo_por_projeto = df_filtered_projetos.groupby("Projeto")["Saldo"].sum().reset_index()
    saldo_por_projeto = saldo_por_projeto[saldo_por_projeto["Saldo"] > 0]

    if not saldo_por_projeto.empty:
        grafico2 = px.pie(
            saldo_por_projeto,
            values="Saldo",
            names="Projeto",
            title="Saldo Total por Projeto",
            height=400,
            color_discrete_sequence=px.colors.sequential.RdBu
        )
        st.plotly_chart(grafico2, use_container_width=True)
    else:
        st.info("Não há dados de Saldo para exibir no gráfico de pizza para os filtros selecionados.")

st.markdown("---")

# --- Gráfico 1: Custo Fluxo por Projeto ---
st.subheader("💰 Custo Fluxo por Projeto")
grafico1 = px.bar(
    df_filtered_projetos,
    x="Projeto",
    y="Custo Fluxo",
    labels={"Custo Fluxo": "Custo (R$)"},
    height=400,
    color_discrete_sequence=[COLORS["primary"]]
)
st.plotly_chart(grafico1, use_container_width=True)


# --- Gráfico 3: Cronograma (Gantt simplificado) ---
st.subheader("📅 Cronograma das Obras")
gantt_data = df_filtered_projetos[["Projeto", "Início Obra", "Fim Obra"]].dropna()
# Usar a sequência de cores ALL_GANTT_COLORS
grafico3 = px.timeline(gantt_data, x_start="Início Obra", x_end="Fim Obra", y="Projeto", color="Projeto",
                        color_discrete_sequence=ALL_GANTT_COLORS)
grafico3.update_yaxes(autorange="reversed")
st.plotly_chart(grafico3, use_container_width=True)

st.markdown("---")

# --- Visualizações da Sheet 2 ---
st.subheader("📊 Despesas Recorrentes Detalhadas (Diesel e Mecânica)")

# Certificar-se de que as colunas numéricas estão no formato correto
numeric_cols_sheet2 = ["Custo Fluxo", "ago/25", "set/25", "out/25", "Média dos Próximos Meses"]
for col in numeric_cols_sheet2:
    if col in df_sheet2.columns:
        df_sheet2[col] = pd.to_numeric(df_sheet2[col], errors="coerce").fillna(0)



# Gráfico de pizza para Custo Fluxo por Tipologia (Sheet 2)
st.write("**Custo Fluxo por Tipo de Despesa:**")
custo_fluxo_tipologia_sheet2 = df_sheet2.groupby("Tipologia")["Custo Fluxo"].sum().reset_index()
fig_custo_fluxo_tipologia_sheet2 = px.pie(
    custo_fluxo_tipologia_sheet2,
    values="Custo Fluxo",
    names="Tipologia",
    color_discrete_sequence=px.colors.sequential.RdBu
)
st.plotly_chart(fig_custo_fluxo_tipologia_sheet2, use_container_width=True)

st.markdown("---")

# Gráfico de barras para Custos Mensais e Média dos Próximos Meses por Projeto (Sheet 2)
st.write("**Custos Mensais e Média dos Próximos Meses por Projeto:**")

# Selecionar as colunas relevantes e derreter o DataFrame para o formato longo
monthly_costs_sheet2 = df_sheet2[["Projeto", "ago/25", "set/25", "out/25", "Média dos Próximos Meses"]].copy()
monthly_costs_sheet2_melted = monthly_costs_sheet2.melt(id_vars=["Projeto"], 
                                                         var_name="Mês/Tipo", 
                                                         value_name="Valor")

fig_monthly_costs_sheet2 = px.bar(
    monthly_costs_sheet2_melted,
    x="Projeto",
    y="Valor",
    color="Mês/Tipo", # Usar a coluna 'Mês/Tipo' para diferenciar as barras
    barmode="group", # Agrupar as barras por projeto
    labels={
        "Valor": "Valor (R$)",
        "Mês/Tipo": "Período"
    },
    color_discrete_sequence=[COLORS["support7"], COLORS["support8"], COLORS["support9"], COLORS["support10"]]
)
st.plotly_chart(fig_monthly_costs_sheet2, use_container_width=True)


# --- Gráfico 4: Custo Fluxo Médio por Empresa ---
st.subheader("🏢 Custo Fluxo Médio por Empresa Desenvolvedora")
empresa_custo_fluxo = df_filtered_projetos.groupby("Empresa desenvolvedora")["Custo Fluxo"].mean().reset_index()
grafico4 = px.bar(empresa_custo_fluxo, x="Empresa desenvolvedora", y="Custo Fluxo",
                   color_discrete_sequence=[COLORS["support5"]])
st.plotly_chart(grafico4, use_container_width=True)

# --- Novo Gráfico: Obras por Cidade ---
st.subheader("🏙️ Obras por Cidade")
obras_por_cidade = df_filtered_projetos["Cidade"].value_counts().reset_index()
obras_por_cidade.columns = ["Cidade", "Número de Obras"]
grafico_cidade = px.bar(obras_por_cidade, x="Cidade", y="Número de Obras",
                         labels={"Número de Obras": "Quantidade de Obras"},
                         height=400,
                         color_discrete_sequence=[COLORS["support6"]])
st.plotly_chart(grafico_cidade, use_container_width=True)

# --- Novo Gráfico: Valores a Pagar por Mês (Ago, Set, Out e Média dos Próximos Meses) ---
st.subheader("💰 Valores a Pagar por Mês")

# Criar um DataFrame para os valores mensais
monthly_costs = pd.DataFrame({
    'Mês': ['Agosto/25', 'Setembro/25', 'Outubro/25', 'Média Próximos Meses'],
    'Valor': [custo_ago_25, custo_set_25, custo_out_25, valor_restante_pagar_media]
})

grafico_mensal = px.bar(monthly_costs, x="Mês", y="Valor",
                        labels={"Valor": "Valor (R$)"},
                        height=400,
                        color_discrete_sequence=[COLORS["support7"], COLORS["support8"], COLORS["support9"], COLORS["support10"]])
st.plotly_chart(grafico_mensal, use_container_width=True)

# --- Tabela final ---
st.subheader("📋 Tabela Detalhada de Obras")

# Selecionar todas as colunas relevantes para exibição na tabela final
all_display_columns = [
    "ID", "Empresa desenvolvedora", "Sócia", "Projeto", "Tipologia", "Cidade", "UF", "Etapa",
    "Custo Raso Meta", "Custo Fluxo", "Percentual Incorrido do Fluxo%",
    "ago/25", "set/25", "out/25", "Média dos Próximos Meses", "Saldo",
    "Índice Ômega", "% Avanço Físico", "%Avanço Financeiro", "Tempo de Obra",
    "Início Obra", "Fim Obra", "Meses Restantes Pós Out/25"
]

df_display = df_filtered_projetos[all_display_columns].copy()

# Aplicar formatação de moeda às colunas financeiras
currency_display_cols = [
    "Custo Raso Meta", "Custo Fluxo", "ago/25", "set/25", "out/25",
    "Média dos Próximos Meses", "Saldo"
]
for col in currency_display_cols:
    if col in df_display.columns:
        df_display[col] = df_display[col].apply(format_currency_br)

st.dataframe(df_display, use_container_width=True)

# Tabela com os dados da Sheet 2
st.subheader("📋 Tabela Detalhada das Despesas Fixas (Diesel e Mecânica)")
df_display_sheet2 = df_sheet2.copy()
for col in numeric_cols_sheet2:
    if col in df_display_sheet2.columns:
        df_display_sheet2[col] = df_display_sheet2[col].apply(format_currency_br)
st.dataframe(df_display_sheet2, use_container_width=True)

st.markdown("---")
