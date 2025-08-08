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
    return df

df = load_data()

st.title("📊 Dashboard de Obras - Cadastro Geral")

# --- Filtros ---
col1, col2 = st.columns(2)
with col1:
    cidades = st.multiselect("Filtrar por Cidade", options=df["Cidade"].dropna().unique(), default=df["Cidade"].dropna().unique())
with col2:
    empresas = st.multiselect("Filtrar por Empresa Desenvolvedora", options=df["Empresa desenvolvedora"].dropna().unique(), default=df["Empresa desenvolvedora"].dropna().unique())

df_filtered = df[df["Cidade"].isin(cidades) & df["Empresa desenvolvedora"].isin(empresas)]

# --- KPIs ---
total_obras = len(df_filtered)
investimento_total = df_filtered["Custo Raso Meta"].sum()
investimento_exec = df_filtered["Custo Fluxo"].sum()
avance_fisico_medio = df_filtered["% Avanço Físico"].mean()
avance_fin_medio = df_filtered["%Avanço Financeiro"].mean()

kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
kpi1.metric("🏗️ Total de Obras", total_obras)
kpi2.metric("💰 Custo Raso Meta", f"R$ {investimento_total:,.0f}")
kpi3.metric("🧾 Custo Fluxo", f"R$ {investimento_exec:,.0f}")
kpi4.metric("📏 Avanço Físico Médio", f"{avance_fisico_medio:.0%}")
kpi5.metric("📊 Avanço Financeiro Médio", f"{avance_fin_medio:.0%}")

st.markdown("---")

# --- Gráfico 1: Avanço físico vs financeiro por projeto ---
st.subheader("📐 Avanço Físico vs Financeiro por Projeto")
grafico1 = px.bar(
    df_filtered,
    x="Projeto",
    y=["% Avanço Físico", "%Avanço Financeiro"],
    barmode="group",
    labels={"value": "Avanço (%)", "variable": "Tipo de Avanço"},
    height=400
)
st.plotly_chart(grafico1, use_container_width=True)

# --- Gráfico 2: Obras por Cidade ---
st.subheader("🏘️ Distribuição de Obras por Cidade")
obras_por_cidade = df_filtered["Cidade"].value_counts().reset_index()
obras_por_cidade.columns = ["Cidade", "Qtd Obras"]
grafico2 = px.bar(obras_por_cidade, x="Cidade", y="Qtd Obras", height=400)
st.plotly_chart(grafico2, use_container_width=True)

# --- Gráfico 3: Cronograma (Gantt simplificado) ---
st.subheader("📅 Cronograma das Obras")
gantt_data = df_filtered[["Projeto", "Início Obra", "Fim Obra"]].dropna()
grafico3 = px.timeline(gantt_data, x_start="Início Obra", x_end="Fim Obra", y="Projeto", color="Projeto")
grafico3.update_yaxes(autorange="reversed")
st.plotly_chart(grafico3, use_container_width=True)

# --- Gráfico 4: Progresso por Empresa ---
st.subheader("🏢 Progresso Médio por Empresa Desenvolvedora")
empresa_avanco = df_filtered.groupby("Empresa desenvolvedora")[["% Avanço Físico", "%Avanço Financeiro"]].mean().reset_index()
grafico4 = px.bar(empresa_avanco, x="Empresa desenvolvedora", y=["% Avanço Físico", "%Avanço Financeiro"], barmode="group")
st.plotly_chart(grafico4, use_container_width=True)

# --- Tabela final ---
st.subheader("📋 Tabela Detalhada de Obras")
st.dataframe(df_filtered, use_container_width=True)
