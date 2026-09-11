import plotly.graph_objects as go
import streamlit as st

from data_loader import DATA_FILE, carregar_dados

st.set_page_config(page_title="Clima Portugal — Comparar Cenários", page_icon="🆚", layout="wide")

try:
    df = carregar_dados()
except FileNotFoundError:
    st.warning(f"Ainda não há dados em `{DATA_FILE}`. Rode `python update_data.py` primeiro.")
    st.stop()

st.title("🆚 Comparar Cenários")
st.caption(
    "Compare dois recortes independentes dos dados (ex.: mesma cidade em anos diferentes) "
    "ao longo do **dia do ano** — isto alinha meses/estações de anos distintos no mesmo eixo X, "
    "para uma comparação direta. A linha vermelha é a média histórica (todos os anos) do mesmo "
    "tipo de dia (cidade/estação/fim-de-semana/mês combinados entre os dois cenários)."
)

CIDADES = sorted(df["Cidade"].unique())
ANOS = sorted(df["Ano"].unique())
ESTACOES = ["Inverno", "Primavera", "Verão", "Outono"]
MESES_NOMES = {1: "Jan", 2: "Fev", 3: "Mar", 4: "Abr", 5: "Mai", 6: "Jun",
               7: "Jul", 8: "Ago", 9: "Set", 10: "Out", 11: "Nov", 12: "Dez"}
MESES = list(MESES_NOMES.keys())
VARIAVEIS = {"Média": "Temp. Média (°C)", "Máxima": "Temp. Máxima (°C)", "Mínima": "Temp. Mínima (°C)"}

st.markdown("##### Variável de temperatura a comparar (aplica-se ao Gráfico 1)")
variavel_label = st.radio(
    "Variável", list(VARIAVEIS.keys()), horizontal=True, label_visibility="collapsed"
)
coluna_temp = VARIAVEIS[variavel_label]

st.divider()


def filtros_cenario(titulo, key_prefix, ano_default):
    st.markdown(f"#### {titulo}")
    cidades = st.multiselect("Cidade", CIDADES, default=CIDADES[:1], key=f"{key_prefix}_cidade")
    estacoes = st.multiselect("Estação", ESTACOES, default=ESTACOES, key=f"{key_prefix}_estacao")
    fds = st.radio(
        "Dias", ["Todos os dias", "Fim de Semana", "Semana"],
        horizontal=True, key=f"{key_prefix}_fds",
    )
    anos = st.multiselect(
        "Ano", ANOS, default=[ano_default] if ano_default in ANOS else ANOS[-1:], key=f"{key_prefix}_ano"
    )
    meses = st.multiselect(
        "Mês", MESES, default=MESES, format_func=lambda m: MESES_NOMES[m], key=f"{key_prefix}_mes"
    )
    return {"cidades": cidades, "estacoes": estacoes, "fds": fds, "anos": anos, "meses": meses}


col_a, col_b = st.columns(2)
with col_a:
    filtro_a = filtros_cenario("🟡 Cenário A (área amarela)", "a", ANOS[-2] if len(ANOS) >= 2 else ANOS[-1])
with col_b:
    filtro_b = filtros_cenario("⚫ Cenário B (linha preta)", "b", ANOS[-1])

st.divider()


def aplicar_filtro(df, f):
    out = df[df["Cidade"].isin(f["cidades"])]
    out = out[out["Estação"].isin(f["estacoes"])]
    if f["fds"] != "Todos os dias":
        out = out[out["FDS"] == f["fds"]]
    out = out[out["Ano"].isin(f["anos"])]
    out = out[out["Mes"].isin(f["meses"])]
    return out


def serie_por_dia_do_ano(df_filtrado, coluna):
    return (
        df_filtrado.groupby("Dia do Ano")[coluna]
        .mean()
        .reset_index()
        .sort_values("Dia do Ano")
    )


def media_historica(df_total, f_a, f_b, coluna):
    """Média do histórico completo (todos os anos) para o tipo de dia comum aos 2 cenários."""
    cidades = sorted(set(f_a["cidades"]) | set(f_b["cidades"]))
    estacoes = sorted(set(f_a["estacoes"]) | set(f_b["estacoes"]))
    meses = sorted(set(f_a["meses"]) | set(f_b["meses"]))
    fds_valores = set()
    for f in (f_a, f_b):
        if f["fds"] == "Todos os dias":
            fds_valores.update(["Fim de Semana", "Semana"])
        else:
            fds_valores.add(f["fds"])

    base = df_total[df_total["Cidade"].isin(cidades)]
    base = base[base["Estação"].isin(estacoes)]
    base = base[base["FDS"].isin(fds_valores)]
    base = base[base["Mes"].isin(meses)]
    return None if base.empty else base[coluna].mean()


df_a_full = aplicar_filtro(df, filtro_a)
df_b_full = aplicar_filtro(df, filtro_b)

if df_a_full.empty or df_b_full.empty:
    st.warning("Um dos dois cenários não tem dados para os filtros selecionados. Ajusta os filtros acima.")
    st.stop()


def montar_grafico(coluna, titulo, unidade):
    serie_a = serie_por_dia_do_ano(df_a_full, coluna)
    serie_b = serie_por_dia_do_ano(df_b_full, coluna)
    media = media_historica(df, filtro_a, filtro_b, coluna)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=serie_a["Dia do Ano"], y=serie_a[coluna],
        name="Cenário A", fill="tozeroy", mode="lines",
        line=dict(color="#f2c744"),
    ))
    fig.add_trace(go.Scatter(
        x=serie_b["Dia do Ano"], y=serie_b[coluna],
        name="Cenário B", mode="lines+markers",
        line=dict(color="black"),
    ))
    if media is not None:
        fig.add_hline(
            y=media, line_color="red", line_width=2,
            annotation_text=f"Média histórica: {media:.1f} {unidade}",
            annotation_position="top left",
        )
    fig.update_layout(
        title=titulo,
        xaxis_title="Dia do ano",
        yaxis_title=unidade,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(t=60),
    )
    return fig


col_g1, col_g2 = st.columns(2)
with col_g1:
    st.plotly_chart(montar_grafico(coluna_temp, f"Temperatura {variavel_label} (°C)", "°C"), use_container_width=True)
with col_g2:
    st.plotly_chart(montar_grafico("Precipitação (mm)", "Precipitação (mm)", "mm"), use_container_width=True)

with st.expander("Ver os dias exatos incluídos em cada cenário"):
    ca, cb = st.columns(2)
    with ca:
        st.caption(f"Cenário A — {len(df_a_full)} dias")
        st.dataframe(
            df_a_full[["Cidade", "Data", "Dia da Semana", "Estação", coluna_temp, "Precipitação (mm)"]]
            .sort_values("Data"),
            use_container_width=True, hide_index=True,
        )
    with cb:
        st.caption(f"Cenário B — {len(df_b_full)} dias")
        st.dataframe(
            df_b_full[["Cidade", "Data", "Dia da Semana", "Estação", coluna_temp, "Precipitação (mm)"]]
            .sort_values("Data"),
            use_container_width=True, hide_index=True,
        )
