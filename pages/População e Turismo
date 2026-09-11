"""
Página Streamlit: População e Turismo (INE).

Para funcionar como página do dashboard existente (ooh-tmicc.streamlit.app),
este ficheiro deve ficar em `pages/2_Populacao_e_Turismo.py` no repositório
"ooh", ao lado do `app.py` principal. O Streamlit deteta automaticamente
qualquer ficheiro dentro de `pages/` e adiciona-o como página extra no menu
lateral — não é preciso alterar o app.py.

Espera encontrar os 5 CSVs gerados por ine_extrator_populacao_turismo.py
dentro de uma pasta `data/` no repositório (mesmo padrão do
clima_portugal.csv já usado no projeto):
  data/populacao_residente_anual.csv
  data/turismo_dormidas.csv
  data/turismo_hospedes.csv
  data/turismo_dormidas_origem.csv
  data/turismo_hospedes_origem.csv
"""

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="População e Turismo", page_icon="📊", layout="wide")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

ARQUIVOS = {
    "populacao": "populacao_residente_anual.csv",
    "dormidas": "turismo_dormidas.csv",
    "hospedes": "turismo_hospedes.csv",
    "dormidas_origem": "turismo_dormidas_origem.csv",
    "hospedes_origem": "turismo_hospedes_origem.csv",
}


@st.cache_data
def carregar(nome_ficheiro: str) -> pd.DataFrame:
    caminho = DATA_DIR / nome_ficheiro
    if not caminho.exists():
        return pd.DataFrame()
    df = pd.read_csv(caminho)
    if "valor" in df.columns:
        df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    return df


dados = {chave: carregar(nome) for chave, nome in ARQUIVOS.items()}

if all(df.empty for df in dados.values()):
    st.error(
        "Não encontrei nenhum dos ficheiros CSV em `data/`. Confirma que os "
        "5 CSVs gerados pelo extrator do INE foram carregados para essa "
        "pasta no repositório."
    )
    st.stop()

st.title("📊 População e Turismo em Portugal")
st.caption(
    "Fonte: INE — Estimativas anuais da população residente; Inquérito à "
    "Permanência de Hóspedes na Hotelaria e Outros Alojamentos."
)


# ---------------------------------------------------------------------------
# Filtros de geografia partilhados por todas as abas
# ---------------------------------------------------------------------------

def universo_geografico(dfs: list[pd.DataFrame]) -> pd.DataFrame:
    partes = [df[["distrito", "concelho", "nivel_geo"]] for df in dfs if not df.empty]
    if not partes:
        return pd.DataFrame(columns=["distrito", "concelho", "nivel_geo"])
    return pd.concat(partes, ignore_index=True).drop_duplicates()


geo = universo_geografico(list(dados.values()))

st.sidebar.header("Filtros de geografia")

nivel_sel = st.sidebar.radio(
    "Nível geográfico",
    ["Município", "Agregado (NUTS/Continente)", "Todos"],
    index=0,
)

geo_filtrada = geo if nivel_sel == "Todos" else geo[geo["nivel_geo"] == nivel_sel]

distritos_disponiveis = sorted(geo_filtrada["distrito"].dropna().unique().tolist())
distritos_sel = st.sidebar.multiselect(
    "Distrito / Região Autónoma", distritos_disponiveis, default=[]
)

if distritos_sel:
    concelhos_disponiveis = sorted(
        geo_filtrada.loc[geo_filtrada["distrito"].isin(distritos_sel), "concelho"]
        .dropna()
        .unique()
        .tolist()
    )
else:
    concelhos_disponiveis = sorted(geo_filtrada["concelho"].dropna().unique().tolist())

concelhos_sel = st.sidebar.multiselect(
    "Concelho (deixa vazio para ver todos os do filtro acima)",
    concelhos_disponiveis,
    default=[],
)

agrupar_por = st.sidebar.radio("Agrupar gráficos por", ["Concelho", "Distrito"], index=0)


def aplicar_filtros_geo(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df if nivel_sel == "Todos" else df[df["nivel_geo"] == nivel_sel]
    if distritos_sel:
        out = out[out["distrito"].isin(distritos_sel)]
    if concelhos_sel:
        out = out[out["concelho"].isin(concelhos_sel)]
    return out


def filtro_ano(df: pd.DataFrame, key: str) -> pd.DataFrame:
    if df.empty or "ano" not in df.columns or df["ano"].dropna().empty:
        return df
    ano_min, ano_max = int(df["ano"].min()), int(df["ano"].max())
    if ano_min == ano_max:
        return df
    intervalo = st.slider(
        "Período (ano)", min_value=ano_min, max_value=ano_max,
        value=(ano_min, ano_max), key=key,
    )
    return df[(df["ano"] >= intervalo[0]) & (df["ano"] <= intervalo[1])]


def filtro_dimensao(
    df: pd.DataFrame, col: str, label: str, key: str, default_total: bool = True
) -> pd.DataFrame:
    """Filtro genérico para colunas de dimensão extra do INE (sexo, grupo
    etário, tipo de alojamento, país de residência). Por omissão seleciona
    a categoria 'Total' quando existe, para já vires com números
    consolidados — mas dá para abrir por qualquer quebra disponível."""
    if col not in df.columns or df[col].dropna().empty:
        return df
    opcoes = sorted(df[col].dropna().unique().tolist())
    default = [o for o in opcoes if str(o).strip().lower() == "total"]
    if default_total and not default and opcoes:
        default = [opcoes[0]]
    sel = st.multiselect(label, opcoes, default=default, key=key)
    if sel:
        return df[df[col].isin(sel)]
    return df


def grafico_e_tabela(df: pd.DataFrame, titulo_eixo_y: str, chave: str):
    if df.empty:
        st.info("Sem dados para os filtros selecionados.")
        return

    col_grupo = "concelho" if agrupar_por == "Concelho" else "distrito"
    resumo = (
        df.groupby(["ano", col_grupo], as_index=False)["valor"]
        .sum()
        .sort_values("ano")
    )

    if resumo[col_grupo].nunique() > 25 and agrupar_por == "Concelho":
        st.warning(
            f"{resumo[col_grupo].nunique()} concelhos selecionados — o "
            "gráfico pode ficar poluído. Considera filtrar por distrito "
            "ou selecionar concelhos específicos na barra lateral."
        )

    fig = px.line(
        resumo, x="ano", y="valor", color=col_grupo, markers=True,
        labels={"valor": titulo_eixo_y, "ano": "Ano", col_grupo: col_grupo.capitalize()},
    )
    fig.update_layout(legend_title_text=col_grupo.capitalize(), height=500)
    st.plotly_chart(fig, use_container_width=True, key=f"chart_{chave}")

    with st.expander("Ver tabela de dados"):
        tabela = df[
            ["ano", "distrito", "concelho", "valor"]
            + [c for c in df.columns if c.endswith("_t") and c not in ("geo_dsg",)]
        ].sort_values(["ano", "distrito", "concelho"])
        st.dataframe(tabela, use_container_width=True, hide_index=True)
        st.download_button(
            "⬇️ Descarregar CSV filtrado",
            tabela.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"{chave}_filtrado.csv",
            mime="text/csv",
            key=f"download_{chave}",
        )


# ---------------------------------------------------------------------------
# Abas
# ---------------------------------------------------------------------------

aba_pop, aba_dorm, aba_hosp, aba_dorm_o, aba_hosp_o, aba_cruzamento = st.tabs(
    [
        "População",
        "Turismo — Dormidas",
        "Turismo — Hóspedes",
        "Dormidas por Origem",
        "Hóspedes por Origem",
        "Cruzamento População × Turismo",
    ]
)

with aba_pop:
    st.subheader("População residente")
    df = aplicar_filtros_geo(dados["populacao"])
    df = filtro_dimensao(df, "dim_3_t", "Sexo", key="pop_sexo")
    df = filtro_dimensao(df, "dim_4_t", "Grupo etário", key="pop_idade")
    df = filtro_ano(df, key="pop_ano")
    grafico_e_tabela(df, "População residente (N.º)", "populacao")

with aba_dorm:
    st.subheader("Dormidas nos estabelecimentos de alojamento turístico")
    df = aplicar_filtros_geo(dados["dormidas"])
    df = filtro_dimensao(df, "dim_3_t", "Tipo de alojamento", key="dorm_tipo")
    df = filtro_ano(df, key="dorm_ano")
    grafico_e_tabela(df, "Dormidas (N.º)", "dormidas")

with aba_hosp:
    st.subheader("Hóspedes nos estabelecimentos de alojamento turístico")
    df = aplicar_filtros_geo(dados["hospedes"])
    df = filtro_dimensao(df, "dim_3_t", "Tipo de alojamento", key="hosp_tipo")
    df = filtro_ano(df, key="hosp_ano")
    grafico_e_tabela(df, "Hóspedes (N.º)", "hospedes")

with aba_dorm_o:
    st.subheader("Dormidas por país de residência do turista")
    df = aplicar_filtros_geo(dados["dormidas_origem"])
    df = filtro_dimensao(df, "dim_3_t", "País de residência", key="dormo_pais", default_total=True)
    df = filtro_ano(df, key="dormo_ano")
    grafico_e_tabela(df, "Dormidas (N.º)", "dormidas_origem")

with aba_hosp_o:
    st.subheader("Hóspedes por país de residência do turista")
    df = aplicar_filtros_geo(dados["hospedes_origem"])
    df = filtro_dimensao(df, "dim_3_t", "País de residência", key="hospo_pais", default_total=True)
    df = filtro_ano(df, key="hospo_ano")
    grafico_e_tabela(df, "Hóspedes (N.º)", "hospedes_origem")

with aba_cruzamento:
    st.subheader("Turistas por 100 habitantes, por concelho e ano")
    st.caption(
        "Cruza a população residente (Total) com as dormidas totais para "
        "estimar a intensidade turística de cada concelho ao longo do tempo."
    )

    pop_total = dados["populacao"]
    pop_total = pop_total[
        (pop_total.get("dim_3_t") == "HM") & (pop_total.get("dim_4_t") == "Total")
    ][["ano", "concelho", "distrito", "nivel_geo", "valor"]].rename(
        columns={"valor": "populacao"}
    )

    dorm_total = dados["dormidas"]
    dorm_total = dorm_total[dorm_total.get("dim_3_t") == "Total"][
        ["ano", "concelho", "valor"]
    ].rename(columns={"valor": "dormidas"})

    cruzado = pop_total.merge(dorm_total, on=["ano", "concelho"], how="inner")
    cruzado = cruzado[cruzado["populacao"] > 0]
    cruzado["dormidas_por_100_hab"] = (
        cruzado["dormidas"] / cruzado["populacao"] * 100
    )

    cruzado = aplicar_filtros_geo(cruzado)
    cruzado = filtro_ano(cruzado, key="cruz_ano")

    if cruzado.empty:
        st.info("Sem dados suficientes para os filtros selecionados.")
    else:
        col_grupo = "concelho" if agrupar_por == "Concelho" else "distrito"
        resumo = (
            cruzado.groupby(["ano", col_grupo], as_index=False)
            .apply(
                lambda g: pd.Series(
                    {
                        "dormidas": g["dormidas"].sum(),
                        "populacao": g["populacao"].sum(),
                    }
                ),
                include_groups=False,
            )
        )
        resumo["dormidas_por_100_hab"] = resumo["dormidas"] / resumo["populacao"] * 100

        fig = px.line(
            resumo, x="ano", y="dormidas_por_100_hab", color=col_grupo, markers=True,
            labels={
                "dormidas_por_100_hab": "Dormidas por 100 habitantes",
                "ano": "Ano",
                col_grupo: col_grupo.capitalize(),
            },
        )
        fig.update_layout(height=500)
        st.plotly_chart(fig, use_container_width=True, key="chart_cruzamento")

        with st.expander("Ver tabela de dados"):
            st.dataframe(
                cruzado.sort_values(["ano", "distrito", "concelho"]),
                use_container_width=True,
                hide_index=True,
            )
            st.download_button(
                "⬇️ Descarregar CSV filtrado",
                cruzado.to_csv(index=False).encode("utf-8-sig"),
                file_name="cruzamento_populacao_turismo.csv",
                mime="text/csv",
                key="download_cruzamento",
            )
