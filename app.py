import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Clima Portugal", page_icon="🌦️", layout="wide")

DATA_FILE = "data/clima_portugal.csv"

ESTACAO = {
    12: "Inverno", 1: "Inverno", 2: "Inverno",
    3: "Primavera", 4: "Primavera", 5: "Primavera",
    6: "Verão", 7: "Verão", 8: "Verão",
    9: "Outono", 10: "Outono", 11: "Outono",
}


@st.cache_data(ttl=3600)
def carregar_dados():
    df = pd.read_csv(DATA_FILE, parse_dates=["Data"])
    df["Ano"] = df["Data"].dt.year
    df["Mes"] = df["Data"].dt.month
    df["Estação"] = df["Mes"].map(ESTACAO)
    return df


df = carregar_dados()

st.title("🌦️ Clima em Portugal")
st.caption(f"Dados diários de {df['Data'].min():%d/%m/%Y} a {df['Data'].max():%d/%m/%Y} · atualizado automaticamente")

# ---------------------------------------------------------------------------
# Filtros
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Filtros")
    cidades = st.multiselect(
        "Cidades", sorted(df["Cidade"].unique()), default=sorted(df["Cidade"].unique())
    )
    data_min, data_max = df["Data"].min().date(), df["Data"].max().date()
    intervalo = st.date_input("Período", value=(data_min, data_max), min_value=data_min, max_value=data_max)

if len(intervalo) == 2:
    inicio, fim = intervalo
else:
    inicio, fim = data_min, data_max

df_f = df[
    (df["Cidade"].isin(cidades))
    & (df["Data"].dt.date >= inicio)
    & (df["Data"].dt.date <= fim)
]

if df_f.empty:
    st.warning("Sem dados para os filtros selecionados.")
    st.stop()

# ---------------------------------------------------------------------------
# KPIs rápidos
# ---------------------------------------------------------------------------
c1, c2, c3, c4 = st.columns(4)
c1.metric("Temp. média", f"{df_f['Temp. Média (°C)'].mean():.1f} °C")
c2.metric("Temp. máxima absoluta", f"{df_f['Temp. Máxima (°C)'].max():.1f} °C")
c3.metric("Temp. mínima absoluta", f"{df_f['Temp. Mínima (°C)'].min():.1f} °C")
c4.metric("Precipitação total", f"{df_f['Precipitação (mm)'].sum():,.0f} mm")

st.divider()

# ---------------------------------------------------------------------------
# Aba 1: Resumo por cidade (equivalente à aba "Resumo por Cidade" do Excel)
# ---------------------------------------------------------------------------
tab_resumo, tab_evolucao, tab_precip, tab_dados = st.tabs(
    ["📊 Resumo por cidade", "📈 Evolução de temperatura", "🌧️ Precipitação", "📋 Dados"]
)

with tab_resumo:
    resumo = (
        df_f.groupby("Cidade")
        .agg(
            Temp_Max_Absoluta=("Temp. Máxima (°C)", "max"),
            Temp_Min_Absoluta=("Temp. Mínima (°C)", "min"),
            Temp_Media=("Temp. Média (°C)", "mean"),
            Precip_Media_Diaria=("Precipitação (mm)", "mean"),
            Precip_Total=("Precipitação (mm)", "sum"),
        )
        .round(1)
        .reset_index()
    )
    st.dataframe(resumo, use_container_width=True, hide_index=True)

    fig = px.bar(
        resumo.sort_values("Temp_Media"),
        x="Cidade", y="Temp_Media",
        title="Temperatura média por cidade",
        labels={"Temp_Media": "Temp. média (°C)"},
    )
    st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------------------
# Aba 2: Evolução de temperatura ao longo do tempo
# ---------------------------------------------------------------------------
with tab_evolucao:
    granularidade = st.radio("Agregar por", ["Dia", "Mês", "Ano"], horizontal=True)
    freq_map = {"Dia": "D", "Mês": "ME", "Ano": "YE"}
    serie = (
        df_f.set_index("Data")
        .groupby("Cidade")
        .resample(freq_map[granularidade])["Temp. Média (°C)"]
        .mean()
        .reset_index()
    )
    fig = px.line(
        serie, x="Data", y="Temp. Média (°C)", color="Cidade",
        title="Temperatura média ao longo do tempo",
    )
    st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------------------
# Aba 3: Precipitação (equivalente às tabelas dinâmicas do Excel)
# ---------------------------------------------------------------------------
with tab_precip:
    pivot = (
        df_f.groupby(["Cidade", "Ano", "Mes"])["Precipitação (mm)"]
        .mean()
        .reset_index()
    )
    fig = px.density_heatmap(
        pivot, x="Mes", y="Ano", z="Precipitação (mm)", facet_col="Cidade",
        title="Precipitação média diária por mês/ano",
        color_continuous_scale="Blues",
    )
    st.plotly_chart(fig, use_container_width=True)

    fig2 = px.bar(
        df_f.groupby("Clima Simplificado").size().reset_index(name="Dias"),
        x="Clima Simplificado", y="Dias",
        title="Distribuição de dias por tipo de clima",
    )
    st.plotly_chart(fig2, use_container_width=True)

# ---------------------------------------------------------------------------
# Aba 4: Dados brutos
# ---------------------------------------------------------------------------
with tab_dados:
    st.dataframe(
        df_f.sort_values("Data", ascending=False),
        use_container_width=True,
        hide_index=True,
    )
    st.download_button(
        "⬇️ Descarregar CSV filtrado",
        df_f.to_csv(index=False).encode("utf-8"),
        file_name="clima_portugal_filtrado.csv",
        mime="text/csv",
    )
