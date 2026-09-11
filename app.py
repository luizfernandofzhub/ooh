import pandas as pd
import plotly.express as px
import streamlit as st

from data_loader import DATA_FILE, carregar_dados

st.set_page_config(page_title="Clima Portugal", page_icon="🌦️", layout="wide")

try:
    df = carregar_dados()
except FileNotFoundError:
    st.title("🌦️ Clima em Portugal")
    st.warning(
        f"Ainda não há dados em `{DATA_FILE}`. "
        "Rode `python update_data.py` localmente para gerar o CSV e enviá-lo ao GitHub "
        "(isso faz o commit + push automaticamente). O site atualiza sozinho assim que o push chegar."
    )
    st.stop()

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
tab_resumo, tab_evolucao, tab_precip, tab_fds, tab_dados = st.tabs(
    ["📊 Resumo por cidade", "📈 Evolução de temperatura", "🌧️ Precipitação",
     "🗓️ Comparar fins de semana", "📋 Dados"]
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
# Aba 4: Comparar o mesmo nº de fim de semana entre anos
# ---------------------------------------------------------------------------
with tab_fds:
    df_fds = df_f[df_f["FDS"] == "Fim de Semana"].dropna(subset=["Wknd Code"])
    if df_fds.empty:
        st.info("Sem dias de fim de semana no período/cidades selecionados.")
    else:
        max_wknd = int(df_fds["Wknd Code"].max())
        numero_fds = st.slider("Nº do fim de semana no ano", 1, max_wknd, min(3, max_wknd))

        selecionado = df_fds[df_fds["Wknd Code"] == numero_fds]
        st.caption(f"Comparando o **{numero_fds}º fim de semana** de cada ano, entre cidades.")

        resumo_fds = (
            selecionado.groupby(["Ano", "Cidade"])
            .agg(
                Temp_Media=("Temp. Média (°C)", "mean"),
                Temp_Max=("Temp. Máxima (°C)", "max"),
                Temp_Min=("Temp. Mínima (°C)", "min"),
                Precipitacao=("Precipitação (mm)", "sum"),
            )
            .round(1)
            .reset_index()
        )
        st.dataframe(resumo_fds, use_container_width=True, hide_index=True)

        fig = px.bar(
            resumo_fds, x="Ano", y="Temp_Media", color="Cidade", barmode="group",
            title=f"Temperatura média — {numero_fds}º fim de semana do ano, por cidade",
            labels={"Temp_Media": "Temp. média (°C)"},
        )
        st.plotly_chart(fig, use_container_width=True)

        with st.expander("Ver os dias exatos incluídos"):
            st.dataframe(
                selecionado[["Cidade", "Data", "Dia da Semana", "Ano", "Wknd Code",
                             "Temp. Média (°C)", "Precipitação (mm)"]].sort_values(["Ano", "Data"]),
                use_container_width=True, hide_index=True,
            )

# ---------------------------------------------------------------------------
# Aba 5: Dados brutos
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
