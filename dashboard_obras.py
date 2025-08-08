import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Dashboard de Obras", layout="wide")

# --- Carregamento dos dados ---
@st.cache_data
def load_data():
    df = pd.read_excel("cadastro_obras_simplificado.xlsx")
    df["Início Obra"] = pd.to_datetime(df["Início Obra"], errors="coerce")
    df["Fim Obra"] = pd.to_datetime(df["Fim Obra"], errors="coerce")
    df["Tempo de Obra"] = pd.to_numeric(df["Tempo de Obra"], errors="coerce")
    df["% Avanço Físico"] = df["% Avanço Físico"].fillna(0)
    df["%Avanço Financeiro"] = df["%Avanço Financeiro"].fillna(0)
    df["Custo Raso Meta"] = df["Custo Raso Meta"].fillna(0)
    df["Custo Fluxo"] = df["Custo Fluxo"].fillna(0)

    # Separar custos gerais (IDs 900 e 901)
    df_custos_gerais = df[df['ID'].isin([900, 901])].copy()
    df_projetos = df[~df['ID'].isin([900, 901])].copy()

    return df_projetos, df_custos_gerais

df_projetos, df_custos_gerais = load_data()

st.title("📊 Dashboard de Obras - Cadastro Geral")

# --- Filtros ---
col1, col2 = st.columns(2)
with col1:
    cidades = st.multiselect("Filtrar por Cidade", options=df_projetos["Cidade"].dropna().unique(), default=df_projetos["Cidade"].dropna().unique())
with col2:
    empresas = st.multiselect("Filtrar por Empresa Desenvolvedora", options=df_projetos["Empresa desenvolvedora"].dropna().unique(), default=df_projetos["Empresa desenvolvedora"].dropna().unique())

df_filtered_projetos = df_projetos[df_projetos["Cidade"].isin(cidades) & df_projetos["Empresa desenvolvedora"].isin(empresas)]

# --- KPIs de Projetos ---
total_obras = len(df_filtered_projetos)
investimento_total_projetos = df_filtered_projetos["Custo Raso Meta"].sum()
investimento_exec_projetos = df_filtered_projetos["Custo Fluxo"].sum()
avance_fisico_medio = df_filtered_projetos["% Avanço Físico"].mean()
avance_fin_medio = df_filtered_projetos["%Avanço Financeiro"].mean()

# --- KPIs de Custos Gerais ---
custo_geral_meta = df_custos_gerais["Custo Raso Meta"].sum()
custo_geral_exec = df_custos_gerais["Custo Fluxo"].sum()

# --- Novas Métricas ---
# Custo Total Geral (Projetos + Custos Gerais)
custo_total_meta_geral = investimento_total_projetos + custo_geral_meta
custo_total_exec_geral = investimento_exec_projetos + custo_geral_exec

# Custo por Obra (Média)
custo_medio_por_obra_meta = investimento_total_projetos / total_obras if total_obras > 0 else 0
custo_medio_por_obra_exec = investimento_exec_projetos / total_obras if total_obras > 0 else 0

# % de Custo Geral sobre o Custo Total Meta
perc_custo_geral_meta = (custo_geral_meta / custo_total_meta_geral) if custo_total_meta_geral > 0 else 0

kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
kpi1.metric("🏗️ Total de Obras", total_obras)
kpi2.metric("💰 Custo Meta Projetos", f"R$ {investimento_total_projetos:,.0f}")
kpi3.metric("🧾 Custo Exec. Projetos", f"R$ {investimento_exec_projetos:,.0f}")
kpi4.metric("📏 Avanço Físico Médio", f"{avance_fisico_medio:.0%}")
kpi5.metric("📊 Avanço Financeiro Médio", f"{avance_fin_medio:.0%}")

st.markdown("---")

st.subheader("Sumário de Custos Gerais")
kpi_cg1, kpi_cg2, kpi_cg3 = st.columns(3)
kpi_cg1.metric("💰 Custo Geral Meta", f"R$ {custo_geral_meta:,.0f}")
kpi_cg2.metric("🧾 Custo Geral Exec.", f"R$ {custo_geral_exec:,.0f}")
kpi_cg3.metric("% Custo Geral (Meta)", f"{perc_custo_geral_meta:.2%}")

st.subheader("Custos Totais (Projetos + Gerais)")
kpi_ct1, kpi_ct2 = st.columns(2)
kpi_ct1.metric("💰 Custo Total Meta", f"R$ {custo_total_meta_geral:,.0f}")
kpi_ct2.metric("🧾 Custo Total Exec.", f"R$ {custo_total_exec_geral:,.0f}")

st.subheader("Média de Custos por Obra")
kpi_cm1, kpi_cm2 = st.columns(2)
kpi_cm1.metric("💰 Custo Médio/Obra (Meta)", f"R$ {custo_medio_por_obra_meta:,.0f}")
kpi_cm2.metric("🧾 Custo Médio/Obra (Exec.)", f"R$ {custo_medio_por_obra_exec:,.0f}")

st.markdown("---")

# --- Gráfico 1: Avanço físico vs financeiro por projeto ---
st.subheader("📐 Avanço Físico vs Financeiro por Projeto")
grafico1 = px.bar(
    df_filtered_projetos,
    x="Projeto",
    y=["% Avanço Físico", "%Avanço Financeiro"],
    barmode="group",
    labels={"value": "Avanço (%)", "variable": "Tipo de Avanço"},
    height=400
)
st.plotly_chart(grafico1, use_container_width=True)

# --- Gráfico 2: Obras por Cidade ---
st.subheader("🏘️ Distribuição de Obras por Cidade")
obras_por_cidade = df_filtered_projetos["Cidade"].value_counts().reset_index()
obras_por_cidade.columns = ["Cidade", "Qtd Obras"]
grafico2 = px.bar(obras_por_cidade, x="Cidade", y="Qtd Obras", height=400)
st.plotly_chart(grafico2, use_container_width=True)

# --- Gráfico 3: Cronograma (Gantt simplificado) ---
st.subheader("📅 Cronograma das Obras")
gantt_data = df_filtered_projetos[["Projeto", "Início Obra", "Fim Obra"]].dropna()
grafico3 = px.timeline(gantt_data, x_start="Início Obra", x_end="Fim Obra", y="Projeto", color="Projeto")
grafico3.update_yaxes(autorange="reversed")
st.plotly_chart(grafico3, use_container_width=True)

# --- Gráfico 4: Progresso por Empresa ---
st.subheader("🏢 Progresso Médio por Empresa Desenvolvedora")
empresa_avanco = df_filtered_projetos.groupby("Empresa desenvolvedora")[["% Avanço Físico", "%Avanço Financeiro"]].mean().reset_index()
grafico4 = px.bar(empresa_avanco, x="Empresa desenvolvedora", y=["% Avanço Físico", "%Avanço Financeiro"], barmode="group")
st.plotly_chart(grafico4, use_container_width=True)

# --- Tabela final ---
st.subheader("📋 Tabela Detalhada de Obras")
st.dataframe(df_filtered_projetos, use_container_width=True)
