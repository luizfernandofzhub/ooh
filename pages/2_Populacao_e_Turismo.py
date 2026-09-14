"""
Página Streamlit: População e Turismo (INE) — nível Distrito.

Deve ficar em `pages/2_Populacao_e_Turismo.py` no repositório "ooh", ao
lado do `app.py` principal.

Espera encontrar estes 4 CSVs dentro da pasta `data/` no repositório
(Dormidas não tem aba própria, mas é usada no cálculo de "dias por
estadia" da aba Período de Hospedagem; Dormidas-por-Origem não é usada):
  data/populacao_residente_distrito_nativo_anual.csv   (Distrito, Anual, 2020-2025)
  data/turismo_hospedes_distrito_mensal.csv             (Distrito, Mensal, 2020-2026)
  data/turismo_dormidas_distrito_mensal.csv             (Distrito, Mensal, 2020-2026)
  data/turismo_hospedes_origem_distrito_anual.csv       (Distrito, Anual, 2020-2025, por país)
"""

import re
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="População e Turismo", page_icon="📊", layout="wide")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

ARQUIVOS = {
    "populacao": "populacao_residente_distrito_nativo_anual.csv",
    "hospedes": "turismo_hospedes_distrito_mensal.csv",
    "dormidas": "turismo_dormidas_distrito_mensal.csv",
    "hospedes_origem": "turismo_hospedes_origem_distrito_anual.csv",
}

NOMES_MES = {
    1: "Jan", 2: "Fev", 3: "Mar", 4: "Abr", 5: "Mai", 6: "Jun",
    7: "Jul", 8: "Ago", 9: "Set", 10: "Out", 11: "Nov", 12: "Dez",
}


def chave_faixa_etaria(faixa: str) -> int:
    """Ordena faixas etárias pelo número inicial ('5 - 9 anos' -> 5,
    '85 e mais anos' -> 85) — ordenação alfabética normal puxava
    '10 - 14' para antes de '5 - 9'."""
    m = re.match(r"(\d+)", str(faixa))
    return int(m.group(1)) if m else 999


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
        "CSVs gerados pelo extrator do INE foram carregados para essa "
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
# Filtro de Distrito partilhado (barra lateral) — usado pelas abas
# População, Turismo-Hóspedes e Cruzamento. As abas Divisão Etária e
# Hóspedes por Origem têm os seus próprios filtros no topo, como pedido.
# ---------------------------------------------------------------------------

def todos_distritos(dfs: list) -> list:
    valores = set()
    for df in dfs:
        if not df.empty and "distrito" in df.columns:
            valores.update(df["distrito"].dropna().unique().tolist())
    return sorted(valores)


st.sidebar.header("Filtros (População / Hóspedes / Cruzamento)")
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


def aviso_muitos_distritos(df: pd.DataFrame, limite: int = 10):
    n = df["distrito"].nunique()
    if n > limite:
        st.warning(
            f"{n} distritos no gráfico — pode ficar poluído. Seleciona "
            "alguns na barra lateral para veres melhor."
        )


# ---------------------------------------------------------------------------
# Gráfico mensal partilhado (Turismo — Hóspedes): Série temporal ou
# Sazonalidade (mês × ano)
# ---------------------------------------------------------------------------

def grafico_mensal(df: pd.DataFrame, titulo_eixo_y: str, chave: str):
    if df.empty:
        st.info("Sem dados para os filtros selecionados.")
        return

    modo = st.radio(
        "Visualização", ["Série temporal", "Sazonalidade (mês × ano)", "Anual"],
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
        tabela = df[["ano", "mes", "distrito", "valor"]].sort_values(["ano", "mes", "distrito"])
    elif modo == "Sazonalidade (mês × ano)":
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
        tabela = df[["ano", "mes", "distrito", "valor"]].sort_values(["ano", "mes", "distrito"])
    else:  # Anual
        aviso_muitos_distritos(df)
        resumo = df.groupby(["ano", "distrito"], as_index=False)["valor"].sum().sort_values("ano")
        fig = px.line(
            resumo, x="ano", y="valor", color="distrito", markers=True,
            labels={"valor": titulo_eixo_y, "ano": "Ano", "distrito": "Distrito"},
        )
        fig.update_layout(legend_title_text="Distrito", height=500)
        tabela = resumo[["ano", "distrito", "valor"]].sort_values(["ano", "distrito"])

    st.plotly_chart(fig, use_container_width=True, key=f"chart_{chave}")

    with st.expander("Ver tabela de dados"):
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

aba_idade, aba_pop, aba_hosp, aba_periodo, aba_hosp_o, aba_cruzamento = st.tabs(
    [
        "Divisão Etária",
        "População",
        "Turismo — Hóspedes",
        "Período de Hospedagem",
        "Hóspedes por Origem",
        "Cruzamento População × Turismo",
    ]
)

# --- 1. Divisão Etária ------------------------------------------------------
with aba_idade:
    st.subheader("Divisão etária da população, por Distrito")
    st.caption(
        "Cada segmento mostra a % da faixa etária sobre o TOTAL do distrito "
        "(mesmo que só mostres algumas faixas, a % continua a ser sobre o "
        "total real, não sobre a soma das faixas visíveis)."
    )

    pop_base = dados["populacao"]
    anos_idade = sorted(pop_base["ano"].dropna().unique().tolist())
    distritos_idade = sorted(pop_base["distrito"].dropna().unique().tolist())
    faixas_idade = sorted(
        [f for f in pop_base["dim_4_t"].dropna().unique().tolist() if f != "Total"],
        key=chave_faixa_etaria,
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        distritos_idade_sel = st.multiselect(
            "Distrito", distritos_idade, default=distritos_idade, key="idade_distritos"
        )
    with col2:
        ano_idade_sel = st.selectbox(
            "Período (ano)", anos_idade, index=len(anos_idade) - 1, key="idade_ano"
        )
    with col3:
        faixas_idade_sel = st.multiselect(
            "Faixa etária", faixas_idade, default=faixas_idade, key="idade_faixas"
        )

    df_ano_idade = pop_base[pop_base["ano"] == ano_idade_sel]
    faixas_todas = df_ano_idade[df_ano_idade["dim_4_t"] != "Total"]
    totais_por_distrito = (
        df_ano_idade[df_ano_idade["dim_4_t"] == "Total"].set_index("distrito")["valor"].to_dict()
    )

    # "Total Portugal" é sempre calculado a partir de TODOS os distritos do
    # ano escolhido, independentemente do filtro de distrito acima.
    pt_faixas = faixas_todas.groupby("dim_4_t", as_index=False)["valor"].sum()
    pt_faixas["distrito"] = "Total Portugal"
    totais_por_distrito["Total Portugal"] = sum(
        v for k, v in totais_por_distrito.items() if k != "Total Portugal"
    )

    faixas_filtradas = faixas_todas[
        faixas_todas["distrito"].isin(distritos_idade_sel)
        & faixas_todas["dim_4_t"].isin(faixas_idade_sel)
    ]
    faixas_final = pd.concat(
        [pt_faixas[pt_faixas["dim_4_t"].isin(faixas_idade_sel)], faixas_filtradas],
        ignore_index=True,
    )

    if faixas_final.empty:
        st.info("Sem dados para os filtros selecionados.")
    else:
        faixas_final["total_distrito"] = faixas_final["distrito"].map(totais_por_distrito)
        faixas_final["percentual"] = (
            faixas_final["valor"] / faixas_final["total_distrito"] * 100
        )
        faixas_final["rotulo"] = faixas_final["percentual"].round(1).astype(str) + "%"

        ordem_distritos = ["Total Portugal"] + [
            d for d in distritos_idade_sel if d in faixas_final["distrito"].unique()
        ]

        fig_idade = px.bar(
            faixas_final, x="distrito", y="percentual", color="dim_4_t", text="rotulo",
            category_orders={"distrito": ordem_distritos, "dim_4_t": faixas_idade_sel},
            labels={"percentual": "% da população do distrito", "distrito": "Distrito", "dim_4_t": "Faixa etária"},
        )
        fig_idade.update_traces(textposition="inside", textfont_size=10)
        fig_idade.update_layout(barmode="stack", height=650, legend_title_text="Faixa etária")
        st.plotly_chart(fig_idade, use_container_width=True, key="chart_idade")

        with st.expander("Ver tabela de dados"):
            tabela_idade = faixas_final[["distrito", "dim_4_t", "valor", "percentual"]].sort_values(
                ["distrito", "dim_4_t"], key=lambda s: s.map(chave_faixa_etaria) if s.name == "dim_4_t" else s
            )
            st.dataframe(tabela_idade, use_container_width=True, hide_index=True)
            st.download_button(
                "⬇️ Descarregar CSV filtrado",
                tabela_idade.to_csv(index=False).encode("utf-8-sig"),
                file_name="divisao_etaria_filtrado.csv",
                mime="text/csv",
                key="download_idade",
            )

# --- 2. População -----------------------------------------------------------
with aba_pop:
    st.subheader("População residente (2020-2025)")
    df_pop = aplicar_filtro_distrito(dados["populacao"])
    df_pop = df_pop[df_pop["dim_4_t"] == "Total"]
    df_pop = filtro_ano(df_pop, key="pop_ano")

    if df_pop.empty:
        st.info("Sem dados para os filtros selecionados.")
    else:
        col_esq, col_dir = st.columns([2, 3])

        # --- gráfico esquerdo: barras, soma dos distritos selecionados, 1
        # barra por ano, com rótulo de % de evolução vs. ano anterior
        resumo_barra = (
            df_pop.groupby("ano", as_index=False)["valor"].sum().sort_values("ano")
        )
        resumo_barra["variacao_pct"] = resumo_barra["valor"].pct_change() * 100
        resumo_barra["rotulo"] = resumo_barra["variacao_pct"].apply(
            lambda v: f"{v:+.1f}%" if pd.notna(v) else ""
        )
        resumo_barra["ano_str"] = resumo_barra["ano"].astype(int).astype(str)

        with col_esq:
            st.markdown("**Total da população (distritos selecionados)**")
            fig_barra = px.bar(
                resumo_barra, x="ano_str", y="valor", text="rotulo",
                labels={"valor": "População (N.º)", "ano_str": "Ano"},
            )
            fig_barra.update_traces(textposition="outside")
            fig_barra.update_layout(height=480)
            st.plotly_chart(fig_barra, use_container_width=True, key="chart_pop_barra")

        # --- gráfico direito: linhas por distrito, com rótulo no fim de
        # cada linha (nome + CAGR entre primeiro e último ano selecionado)
        resumo_linha = (
            df_pop.groupby(["ano", "distrito"], as_index=False)["valor"]
            .sum()
            .sort_values("ano")
        )
        anos_sel = sorted(resumo_linha["ano"].unique())
        ano_ini, ano_fim = anos_sel[0], anos_sel[-1]
        n_anos = ano_fim - ano_ini

        with col_dir:
            st.markdown(f"**Evolução por distrito** (CAGR {ano_ini}–{ano_fim})")
            aviso_muitos_distritos(resumo_linha, limite=15)
            fig_linha = px.line(
                resumo_linha, x="ano", y="valor", color="distrito", markers=True,
                labels={"valor": "População (N.º)", "ano": "Ano", "distrito": "Distrito"},
            )
            fig_linha.update_layout(height=480, showlegend=False)

            cagr_por_distrito = {}
            for distrito, grp in resumo_linha.groupby("distrito"):
                v_ini = grp.loc[grp["ano"] == ano_ini, "valor"]
                v_fim = grp.loc[grp["ano"] == ano_fim, "valor"]
                if not v_ini.empty and not v_fim.empty and v_ini.iloc[0] > 0 and n_anos > 0:
                    cagr = ((v_fim.iloc[0] / v_ini.iloc[0]) ** (1 / n_anos) - 1) * 100
                    cagr_por_distrito[distrito] = cagr
                    texto = f"{distrito} ({cagr:+.1f}%)"
                else:
                    cagr_por_distrito[distrito] = None
                    texto = distrito
                if not v_fim.empty:
                    fig_linha.add_annotation(
                        x=ano_fim, y=v_fim.iloc[0], text=texto, showarrow=False,
                        xanchor="left", xshift=8, font=dict(size=10),
                    )
            fig_linha.update_layout(margin=dict(r=160))
            st.plotly_chart(fig_linha, use_container_width=True, key="chart_pop_linha")

        st.markdown("---")
        col_tab_esq, col_tab_dir = st.columns(2)
        with col_tab_esq:
            with st.expander("Ver tabela — total por ano", expanded=False):
                st.dataframe(
                    resumo_barra[["ano", "valor", "variacao_pct"]],
                    use_container_width=True, hide_index=True,
                )
        with col_tab_dir:
            with st.expander("Ver tabela — por distrito e ano", expanded=False):
                tabela_cagr = resumo_linha.copy()
                tabela_cagr["cagr_periodo_pct"] = tabela_cagr["distrito"].map(cagr_por_distrito)
                st.dataframe(tabela_cagr, use_container_width=True, hide_index=True)

# --- 4. Turismo — Hóspedes ---------------------------------------------------
with aba_hosp:
    st.subheader("Hóspedes nos estabelecimentos de alojamento turístico (mensal)")
    df_hosp = aplicar_filtro_distrito(dados["hospedes"])
    df_hosp = filtro_ano(df_hosp, key="hosp_ano")
    grafico_mensal(df_hosp, "Hóspedes (N.º)", "hospedes")

# --- Período de Hospedagem ---------------------------------------------------
with aba_periodo:
    st.subheader("Período médio de hospedagem (dias), por Distrito e Ano")
    st.caption(
        "Dormidas ÷ Hóspedes = número médio de noites por estadia. Mesma "
        "ressalva dos concelhos confidenciais aplica-se aqui, em ambos os "
        "indicadores."
    )

    dorm_anual = (
        dados["dormidas"][["ano", "distrito", "valor"]]
        .groupby(["ano", "distrito"], as_index=False)["valor"].sum()
        .rename(columns={"valor": "dormidas"})
    )
    hosp_anual = (
        dados["hospedes"][["ano", "distrito", "valor"]]
        .groupby(["ano", "distrito"], as_index=False)["valor"].sum()
        .rename(columns={"valor": "hospedes"})
    )
    periodo = dorm_anual.merge(hosp_anual, on=["ano", "distrito"], how="inner")
    periodo = periodo[periodo["hospedes"] > 0]
    periodo["valor"] = periodo["dormidas"] / periodo["hospedes"]

    periodo_f = aplicar_filtro_distrito(periodo)
    periodo_f = filtro_ano(periodo_f, key="periodo_ano")

    if periodo_f.empty:
        st.info("Sem dados para os filtros selecionados.")
    else:
        aviso_muitos_distritos(periodo_f)
        fig_periodo = px.line(
            periodo_f.sort_values("ano"), x="ano", y="valor", color="distrito", markers=True,
            labels={"valor": "Dias por estadia", "ano": "Ano", "distrito": "Distrito"},
        )
        fig_periodo.update_layout(legend_title_text="Distrito", height=550)
        st.plotly_chart(fig_periodo, use_container_width=True, key="chart_periodo")

        with st.expander("Ver tabela de dados"):
            tabela_periodo = periodo_f[["ano", "distrito", "dormidas", "hospedes", "valor"]].sort_values(
                ["ano", "distrito"]
            )
            st.dataframe(tabela_periodo, use_container_width=True, hide_index=True)
            st.download_button(
                "⬇️ Descarregar CSV filtrado",
                tabela_periodo.to_csv(index=False).encode("utf-8-sig"),
                file_name="periodo_hospedagem_filtrado.csv",
                mime="text/csv",
                key="download_periodo",
            )

# --- 6. Hóspedes por Origem (ranking) ---------------------------------------
with aba_hosp_o:
    st.subheader("Ranking dos países de origem dos hóspedes, por Distrito")
    st.caption(
        "Cada linha é um país; a posição mostra em que lugar do ranking "
        "esse país fica como origem de hóspedes em cada distrito (1º = "
        "maior número de hóspedes desse país)."
    )

    df_origem = dados["hospedes_origem"]
    df_origem = df_origem[df_origem["dim_3_t"] != "Total"]

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        distritos_origem_disp = sorted(df_origem["distrito"].dropna().unique().tolist())
        distritos_origem_sel = st.multiselect(
            "Distrito (vazio = todos)", distritos_origem_disp, default=[], key="origem_distritos"
        )
    with col2:
        anos_origem_disp = sorted(df_origem["ano"].dropna().unique().tolist())
        periodo_origem = st.select_slider(
            "Período (ano)", options=anos_origem_disp,
            value=(anos_origem_disp[0], anos_origem_disp[-1]), key="origem_periodo",
        )
    with col3:
        paises_origem_disp = sorted(df_origem["dim_3_t"].dropna().unique().tolist())
        paises_origem_sel = st.multiselect(
            "País de origem (vazio = usar Top N abaixo)", paises_origem_disp, default=[],
            key="origem_paises",
        )
    with col4:
        top_n = st.slider(
            "Top N países por distrito (só se não escolheres países acima)",
            min_value=3, max_value=15, value=6, key="origem_topn",
        )

    df_origem_f = df_origem[
        (df_origem["ano"] >= periodo_origem[0]) & (df_origem["ano"] <= periodo_origem[1])
    ]
    if distritos_origem_sel:
        df_origem_f = df_origem_f[df_origem_f["distrito"].isin(distritos_origem_sel)]

    agregado = df_origem_f.groupby(["distrito", "dim_3_t"], as_index=False)["valor"].sum()

    if agregado.empty:
        st.info("Sem dados para os filtros selecionados.")
    else:
        agregado["ranking"] = agregado.groupby("distrito")["valor"].rank(
            method="min", ascending=False
        ).astype(int)

        if paises_origem_sel:
            agregado_plot = agregado[agregado["dim_3_t"].isin(paises_origem_sel)]
        else:
            paises_relevantes = agregado.loc[agregado["ranking"] <= top_n, "dim_3_t"].unique()
            agregado_plot = agregado[agregado["dim_3_t"].isin(paises_relevantes)]

        fig_ranking = px.line(
            agregado_plot.sort_values(["dim_3_t", "distrito"]),
            x="distrito", y="ranking", color="dim_3_t", markers=True,
            labels={"ranking": "Posição no ranking", "distrito": "Distrito", "dim_3_t": "País de origem"},
        )
        fig_ranking.update_yaxes(autorange="reversed", dtick=1)
        fig_ranking.update_layout(height=550, legend_title_text="País de origem")
        st.plotly_chart(fig_ranking, use_container_width=True, key="chart_ranking_origem")

        with st.expander("Ver tabela de dados"):
            st.dataframe(
                agregado_plot.sort_values(["distrito", "ranking"]),
                use_container_width=True, hide_index=True,
            )
            st.download_button(
                "⬇️ Descarregar CSV filtrado",
                agregado_plot.to_csv(index=False).encode("utf-8-sig"),
                file_name="ranking_origem_filtrado.csv",
                mime="text/csv",
                key="download_ranking_origem",
            )

# --- 7. Cruzamento População × Turismo --------------------------------------
with aba_cruzamento:
    st.subheader("Hóspedes por 100 habitantes, por Distrito")
    st.caption(
        "Cruza a população residente (ano completo, valor fixo dentro do "
        "ano) com os hóspedes. População fica fixa dentro do ano — a "
        "variação mensal/sazonal vem só do turismo. Só aparecem os anos em "
        "que há população estimada (2020-2025) — 2026 ainda não tem "
        "estimativa do INE."
    )

    pop_total = dados["populacao"]
    pop_total = pop_total[pop_total.get("dim_4_t") == "Total"][
        ["ano", "distrito", "valor"]
    ].rename(columns={"valor": "populacao"})

    hosp_total = dados["hospedes"][["ano", "mes", "data", "distrito", "valor"]].rename(
        columns={"valor": "hospedes"}
    )

    cruzado = hosp_total.merge(pop_total, on=["ano", "distrito"], how="inner")
    cruzado = cruzado[cruzado["populacao"] > 0]
    cruzado["valor"] = cruzado["hospedes"] / cruzado["populacao"] * 100

    cruzado = aplicar_filtro_distrito(cruzado)
    cruzado = filtro_ano(cruzado, key="cruz_ano")

    if cruzado.empty:
        st.info("Sem dados suficientes para os filtros selecionados.")
    else:
        modo_cruz = st.radio(
            "Visualização", ["Série temporal", "Sazonalidade (mês × ano)", "Anual"],
            horizontal=True, key="modo_cruzamento",
        )

        if modo_cruz == "Série temporal":
            aviso_muitos_distritos(cruzado)
            resumo = (
                cruzado.groupby(["data", "distrito"], as_index=False)["valor"]
                .mean()
                .sort_values("data")
            )
            fig_cruz = px.line(
                resumo, x="data", y="valor", color="distrito", markers=True,
                labels={"valor": "Hóspedes por 100 habitantes", "data": "Mês", "distrito": "Distrito"},
            )
            fig_cruz.update_layout(legend_title_text="Distrito", height=500)
            tabela_cruz = cruzado[["ano", "mes", "distrito", "hospedes", "populacao", "valor"]]

        elif modo_cruz == "Sazonalidade (mês × ano)":
            resumo = cruzado.groupby(["ano", "mes"], as_index=False)["valor"].mean()
            resumo["mes_nome"] = resumo["mes"].map(NOMES_MES)
            resumo["ano"] = resumo["ano"].astype(int).astype(str)
            fig_cruz = px.line(
                resumo.sort_values("mes"), x="mes_nome", y="valor", color="ano", markers=True,
                category_orders={"mes_nome": list(NOMES_MES.values())},
                labels={"valor": "Hóspedes por 100 habitantes", "mes_nome": "Mês", "ano": "Ano"},
            )
            fig_cruz.update_layout(legend_title_text="Ano", height=500)
            if not distritos_sel:
                st.caption("A somar todos os distritos (nenhum filtro de distrito aplicado).")
            tabela_cruz = cruzado[["ano", "mes", "distrito", "hospedes", "populacao", "valor"]]

        else:  # Anual — soma hóspedes do ano inteiro / população desse ano
            # (recalcular a partir dos totais anuais, não fazer média das
            # razões mensais, que distorceria o resultado)
            aviso_muitos_distritos(cruzado)
            hosp_anual = cruzado.groupby(["ano", "distrito"], as_index=False)["hospedes"].sum()
            hosp_anual = hosp_anual.merge(pop_total, on=["ano", "distrito"], how="left")
            hosp_anual["valor"] = hosp_anual["hospedes"] / hosp_anual["populacao"] * 100
            fig_cruz = px.line(
                hosp_anual, x="ano", y="valor", color="distrito", markers=True,
                labels={"valor": "Hóspedes por 100 habitantes (ano)", "ano": "Ano", "distrito": "Distrito"},
            )
            fig_cruz.update_layout(legend_title_text="Distrito", height=500)
            tabela_cruz = hosp_anual[["ano", "distrito", "hospedes", "populacao", "valor"]]

        st.plotly_chart(fig_cruz, use_container_width=True, key="chart_cruzamento")

        with st.expander("Ver tabela de dados"):
            st.dataframe(tabela_cruz.sort_values(list(tabela_cruz.columns[:2])), use_container_width=True, hide_index=True)
            st.download_button(
                "⬇️ Descarregar CSV filtrado",
                tabela_cruz.to_csv(index=False).encode("utf-8-sig"),
                file_name="cruzamento_filtrado.csv",
                mime="text/csv",
                key="download_cruzamento",
            )
