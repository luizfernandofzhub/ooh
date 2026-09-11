import plotly.graph_objects as go
import streamlit as st

from data_loader import DATA_FILE, carregar_dados

st.set_page_config(page_title="Clima em Portugal", page_icon="☀️", layout="wide")

try:
    df = carregar_dados()
except FileNotFoundError:
    st.warning(f"Ainda não há dados em `{DATA_FILE}`. Rode `python update_data.py` primeiro.")
    st.stop()

st.title("☀️ Clima em Portugal")
st.caption(
    "Compare dois recortes independentes dos dados (ex.: mesma cidade em anos diferentes) "
    "ao longo do **dia do ano** — isto alinha meses/estações de anos distintos no mesmo eixo X, "
    "para uma comparação direta. A média histórica (todos os anos) do mesmo tipo de dia aparece "
    "ao passar o cursor sobre a linha tracejada vermelha."
)

CIDADES = sorted(df["Cidade"].unique())
ANOS = sorted(df["Ano"].unique())
ESTACOES = ["Inverno", "Primavera", "Verão", "Outono"]
MESES_NOMES = {1: "Jan", 2: "Fev", 3: "Mar", 4: "Abr", 5: "Mai", 6: "Jun",
               7: "Jul", 8: "Ago", 9: "Set", 10: "Out", 11: "Nov", 12: "Dez"}
MESES = list(MESES_NOMES.keys())
VARIAVEIS = {"Média": "Temp. Média (°C)", "Máxima": "Temp. Máxima (°C)", "Mínima": "Temp. Mínima (°C)"}

CAMPOS_SINCRONIZAVEIS = ["cidade", "estacao", "fds", "mes"]  # Ano fica de fora, por pedido


def sincronizar(origem, destino):
    for campo in CAMPOS_SINCRONIZAVEIS:
        chave_origem = f"{origem}_{campo}"
        chave_destino = f"{destino}_{campo}"
        if chave_origem in st.session_state:
            st.session_state[chave_destino] = st.session_state[chave_origem]


st.markdown("##### Variável de temperatura a comparar (aplica-se ao 1º gráfico)")
variavel_label = st.pills(
    "Variável", list(VARIAVEIS.keys()), default="Média", label_visibility="collapsed", key="variavel"
)
variavel_label = variavel_label or "Média"
coluna_temp = VARIAVEIS[variavel_label]

st.divider()


def filtros_cenario(titulo, key_prefix, ano_default, origem_sync):
    col_titulo, col_sync = st.columns([5, 1])
    with col_titulo:
        st.markdown(f"#### {titulo}")
    with col_sync:
        st.button(
            "🔄 SYNC", key=f"sync_{key_prefix}", type="primary",
            help=f"Copiar Cidade/Estação/Dias/Mês do outro cenário",
            on_click=sincronizar, args=(origem_sync, key_prefix),
        )

    cidades = st.pills(
        "Cidade", CIDADES, selection_mode="multi", default=CIDADES[:1], key=f"{key_prefix}_cidade"
    )
    estacoes = st.pills(
        "Estação", ESTACOES, selection_mode="multi", default=ESTACOES, key=f"{key_prefix}_estacao"
    )
    fds = st.pills(
        "Dias", ["Todos os dias", "Fim de Semana", "Semana"],
        selection_mode="single", default="Todos os dias", key=f"{key_prefix}_fds",
    )
    anos = st.pills(
        "Ano", ANOS, selection_mode="multi",
        default=[ano_default] if ano_default in ANOS else ANOS[-1:], key=f"{key_prefix}_ano",
    )
    meses = st.pills(
        "Mês", MESES, selection_mode="multi", default=MESES,
        format_func=lambda m: MESES_NOMES[m], key=f"{key_prefix}_mes",
    )
    return {
        "cidades": cidades or [], "estacoes": estacoes or [],
        "fds": fds or "Todos os dias", "anos": anos or [], "meses": meses or [],
    }


col_a, col_b = st.columns(2)
with col_a:
    filtro_a = filtros_cenario("⬜ Cenário A (área cinza)", "a", ANOS[-2] if len(ANOS) >= 2 else ANOS[-1], "b")
with col_b:
    filtro_b = filtros_cenario("⚫ Cenário B (linha preta)", "b", ANOS[-1], "a")

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
        line=dict(color="#D9D9D9"),
        hovertemplate="Dia %{x}: %{y:.1f}" + f" {unidade}<extra>Cenário A</extra>",
    ))
    fig.add_trace(go.Scatter(
        x=serie_b["Dia do Ano"], y=serie_b[coluna],
        name="Cenário B", mode="lines+markers",
        line=dict(color="black"),
        hovertemplate="Dia %{x}: %{y:.1f}" + f" {unidade}<extra>Cenário B</extra>",
    ))
    if media is not None:
        x_min = min(serie_a["Dia do Ano"].min(), serie_b["Dia do Ano"].min())
        x_max = max(serie_a["Dia do Ano"].max(), serie_b["Dia do Ano"].max())
        fig.add_trace(go.Scatter(
            x=[x_min, x_max], y=[media, media],
            name="Média histórica", mode="lines",
            line=dict(color="#A6192E", dash="dash"),
            hovertemplate=f"Média histórica: %{{y:.1f}} {unidade}<extra></extra>",
        ))
    fig.update_layout(
        title=dict(text=titulo, x=0.5, xanchor="center", font=dict(size=26)),
        xaxis_title="Dia do ano",
        yaxis_title=unidade,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(t=80),
        height=420,
    )
    return fig


st.plotly_chart(montar_grafico(coluna_temp, f"Temperatura {variavel_label} (°C)", "°C"), use_container_width=True)
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
