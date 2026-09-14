"""
Página Streamlit: População e Turismo (INE) — nível Distrito.

Para funcionar como página do dashboard existente (ooh-tmicc.streamlit.app),
este ficheiro deve ficar em `pages/2_Populacao_e_Turismo.py` no repositório
"ooh", ao lado do `app.py` principal.

Espera encontrar os 5 CSVs gerados por ine_extrator_populacao_turismo.py
dentro da pasta `data/` no repositório:
  data/populacao_residente_distrito_nativo_anual.csv   (Distrito, Anual, 2020-2025)
  data/turismo_dormidas_distrito_mensal.csv             (Distrito, Mensal, 2020-2026)
  data/turismo_hospedes_distrito_mensal.csv             (Distrito, Mensal, 2020-2026)
  data/turismo_dormidas_origem_distrito_anual.csv       (Distrito, Anual, 2020-2025, por país)
  data/turismo_hospedes_origem_distrito_anual.csv       (Distrito, Anual, 2020-2025, por país)

Nota: a partir desta versão os dados já vêm ao nível Distrito (não Município)
— não há mais coluna "concelho" nem "nivel_geo".
"""

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="População e Turismo", page_icon="📊", layout="wide")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

ARQUIVOS = {
    "populacao": "populacao_residente_distrito_nativo_anual.csv",
    "dormidas": "turismo_dormidas_distrito_mensal.csv",
    "hospedes": "turismo_hospedes_distrito_mensal.csv",
    "dormidas_origem": "turismo_dormidas_origem_distrito_anual.csv",
    "hospedes_origem": "turismo_hospedes_origem_distrito_anual.csv",
}

NOMES_MES = {
    1: "Jan", 2: "Fev", 3: "Mar", 4: "Abr", 5: "Mai", 6: "Jun",
    7: "Jul", 8: "Ago", 9: "Set", 10: "Out", 11: "Nov", 12: "Dez",
}


@st.cache_data
def carregar(nome_ficheiro: str) -> pd.DataFrame:
    caminho = DATA_DIR / nome_ficheiro
    if not caminho.exists():
        return pd.DataFrame()
    df = pd.read_csv(caminho)
    if "valor" in df.columns:
        df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    if "mes" in df.columns:
        df["mes"] = pd.to_numeric(df["mes"], errors="coerce").astype("Int64")
        # Data do 1º dia do mês — só para dar um eixo temporal contínuo aos
        # gráficos de série temporal (o valor mensal em si já vem no "valor").
        tem_mes = df["mes"].notna()
        df.loc[tem_mes, "data"] = pd.to_datetime(
            df.loc[tem_mes, "ano"].astype(int).astype(str)
            + "-"
            + df.loc[tem_mes, "mes"].astype(int).astype(str)
            + "-01",
            format="%Y-%m-%d",
        )
    return df


dados = {chave: carregar(nome) for chave, nome in ARQUIVOS.items()}

if all(df.empty for df in dados.values()):
    st.error(
        "Não encontrei nenhum dos ficheiros CSV em `data/`. Confirma que os "
        "5 CSVs gerados pelo extrator do INE foram carregados para essa "
        "pasta no repositório."
    )
    st.stop()

st.title("📊 População e Turismo em Portugal — por Distrito")
st.caption(
    "Fonte: INE — Estimativas anuais da população residente (2020-2025, por "
    "Distrito); Inquérito à Permanência de Hóspedes na Hotelaria e Outros "
    "Alojamentos (mensal, 2020-2026, agregado de Município para Distrito). "
    "Concelhos pequenos com valor confidencial não entram na soma do "
    "Distrito — números de distritos com muitos concelhos rurais podem "
    "estar ligeiramente subestimados."
)


# ---------------------------------------------------------------------------
# Filtro de geografia partilhado por todas as abas (só Distrito, a partir
# desta versão — os dados já não têm concelho)
# ---------------------------------------------------------------------------

def todos_distritos(dfs: list) -> list:
    valores = set()
    for df in dfs:
        if not df.empty and "distrito" in df.columns:
            valores.update(df["distrito"].dropna().unique().tolist())
    return sorted(valores)


st.sidebar.header("Filtros")
distritos_disponiveis = todos_distritos(list(dados.values()))
distritos_sel = st.sidebar.multiselect(
    "Distrito / Região Autónoma (vazio = todos)", distritos_disponiveis, default=[]
)


def aplicar_filtro_distrito(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or not distritos_sel:
        return df
    return df[df["distrito"].isin(distritos_sel)]


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
    """Filtro genérico para colunas de dimensão extra do INE (grupo etário,
    país de residência). Por omissão seleciona 'Total' quando existe."""
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


def aviso_muitos_distritos(df: pd.DataFrame):
    n = df["distrito"].nunique()
    if n > 10:
        st.warning(
            f"{n} distritos no gráfico — pode ficar poluído. Seleciona "
            "alguns na barra lateral para veres melhor."
        )


# ---------------------------------------------------------------------------
# Gráfico anual (População, Dormidas/Hóspedes por Origem)
# ---------------------------------------------------------------------------

def grafico_anual(df: pd.DataFrame, titulo_eixo_y: str, chave: str):
    if df.empty:
        st.info("Sem dados para os filtros selecionados.")
        return

    aviso_muitos_distritos(df)
    resumo = (
        df.groupby(["ano", "distrito"], as_index=False)["valor"]
        .sum()
        .sort_values("ano")
    )
    fig = px.line(
        resumo, x="ano", y="valor", color="distrito", markers=True,
        labels={"valor": titulo_eixo_y, "ano": "Ano", "distrito": "Distrito"},
    )
    fig.update_layout(legend_title_text="Distrito", height=500)
    st.plotly_chart(fig, use_container_width=True, key=f"chart_{chave}")

    with st.expander("Ver tabela de dados"):
        colunas_extra = [c for c in df.columns if c.endswith("_t")]
        tabela = df[["ano", "distrito", "valor"] + colunas_extra].sort_values(["ano", "distrito"])
        st.dataframe(tabela, use_container_width=True, hide_index=True)
        st.download_button(
            "⬇️ Descarregar CSV filtrado",
            tabela.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"{chave}_filtrado.csv",
            mime="text/csv",
            key=f"download_{chave}",
        )


# ---------------------------------------------------------------------------
# Gráfico mensal (Dormidas, Hóspedes, Cruzamento) — dois modos:
# série temporal contínua, ou sazonalidade (mês × ano sobrepostos)
# ---------------------------------------------------------------------------

def grafico_mensal(df: pd.DataFrame, titulo_eixo_y: str, chave: str):
    if df.empty:
        st.info("Sem dados para os filtros selecionados.")
        return

    modo = st.radio(
        "Visualização", ["Série temporal", "Sazonalidade (mês × ano)"],
        horizontal=True, key=f"modo_{chave}",
    )

    if modo == "Série temporal":
        aviso_muitos_distritos(df)
        resumo = (
            df.groupby(["data", "distrito"], as_index=False)["valor"]
            .sum()
            .sort_values("data")
        )
        fig = px.line(
            resumo, x="data", y="valor", color="distrito", markers=True,
            labels={"valor": titulo_eixo_y, "data": "Mês", "distrito": "Distrito"},
        )
        fig.update_layout(legend_title_text="Distrito", height=500)
    else:
        # Sazonalidade: soma os distritos selecionados (ou todos, se nenhum
        # filtro) num único total, para comparar mês a mês entre anos —
        # com muitos distritos em simultâneo o gráfico ficaria ilegível.
        resumo = df.groupby(["ano", "mes"], as_index=False)["valor"].sum()
        resumo["mes_nome"] = resumo["mes"].map(NOMES_MES)
        resumo["ano"] = resumo["ano"].astype(int).astype(str)
        fig = px.line(
            resumo.sort_values("mes"), x="mes_nome", y="valor", color="ano", markers=True,
            category_orders={"mes_nome": list(NOMES_MES.values())},
            labels={"valor": titulo_eixo_y, "mes_nome": "Mês", "ano": "Ano"},
        )
        fig.update_layout(legend_title_text="Ano", height=500)
        if not distritos_sel:
            st.caption("A somar todos os distritos (nenhum filtro de distrito aplicado).")

    st.plotly_chart(fig, use_container_width=True, key=f"chart_{chave}")

    with st.expander("Ver tabela de dados"):
        tabela = df[["ano", "mes", "distrito", "valor"]].sort_values(["ano", "mes", "distrito"])
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
    st.subheader("População residente (2020-2025)")
    df = aplicar_filtro_distrito(dados["populacao"])
    df = filtro_dimensao(df, "dim_4_t", "Grupo etário", key="pop_idade")
    df = filtro_ano(df, key="pop_ano")
    grafico_anual(df, "População residente (N.º)", "populacao")

with aba_dorm:
    st.subheader("Dormidas nos estabelecimentos de alojamento turístico (mensal)")
    df = aplicar_filtro_distrito(dados["dormidas"])
    df = filtro_ano(df, key="dorm_ano")
    grafico_mensal(df, "Dormidas (N.º)", "dormidas")

with aba_hosp:
    st.subheader("Hóspedes nos estabelecimentos de alojamento turístico (mensal)")
    df = aplicar_filtro_distrito(dados["hospedes"])
    df = filtro_ano(df, key="hosp_ano")
    grafico_mensal(df, "Hóspedes (N.º)", "hospedes")

with aba_dorm_o:
    st.subheader("Dormidas por país de residência do turista (anual)")
    df = aplicar_filtro_distrito(dados["dormidas_origem"])
    df = filtro_dimensao(df, "dim_3_t", "País de residência", key="dormo_pais")
    df = filtro_ano(df, key="dormo_ano")
    grafico_anual(df, "Dormidas (N.º)", "dormidas_origem")

with aba_hosp_o:
    st.subheader("Hóspedes por país de residência do turista (anual)")
    df = aplicar_filtro_distrito(dados["hospedes_origem"])
    df = filtro_dimensao(df, "dim_3_t", "País de residência", key="hospo_pais")
    df = filtro_ano(df, key="hospo_ano")
    grafico_anual(df, "Hóspedes (N.º)", "hospedes_origem")

with aba_cruzamento:
    st.subheader("Turistas por 100 habitantes, por Distrito e mês")
    st.caption(
        "Cruza a população residente (ano completo, valor fixo dentro do "
        "ano) com o turismo mensal, para estimar a intensidade turística "
        "de cada distrito ao longo do ano. Usa Hóspedes por omissão "
        "(nº de pessoas) em vez de Dormidas (nº de noites), que sobrestima "
        "quem fica vários dias. Só aparecem os anos em que há população "
        "estimada (2020-2025) — 2026 ainda não tem estimativa do INE."
    )

    indicador_sel = st.radio(
        "Indicador de turismo", ["Hóspedes (recomendado)", "Dormidas"],
        horizontal=True, key="cruz_indicador",
    )
    turismo_base = dados["hospedes"] if indicador_sel.startswith("Hóspedes") else dados["dormidas"]

    pop_total = dados["populacao"]
    pop_total = pop_total[pop_total.get("dim_4_t") == "Total"][
        ["ano", "distrito", "valor"]
    ].rename(columns={"valor": "populacao"})

    turismo_total = turismo_base[["ano", "mes", "data", "distrito", "valor"]].rename(
        columns={"valor": "turismo"}
    )

    cruzado = turismo_total.merge(pop_total, on=["ano", "distrito"], how="inner")
    cruzado = cruzado[cruzado["populacao"] > 0]
    cruzado["valor"] = cruzado["turismo"] / cruzado["populacao"] * 100

    cruzado = aplicar_filtro_distrito(cruzado)
    cruzado = filtro_ano(cruzado, key="cruz_ano")

    if cruzado.empty:
        st.info("Sem dados suficientes para os filtros selecionados.")
    else:
        titulo_y = "Hóspedes" if indicador_sel.startswith("Hóspedes") else "Dormidas"
        grafico_mensal(cruzado, f"{titulo_y} por 100 habitantes", "cruzamento")
