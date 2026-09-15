"""
Página Streamlit: População e Turismo (INE) — Distrito e Concelho.

Deve ficar em `pages/2_Populacao_e_Turismo.py` no repositório "ooh", ao
lado do `app.py` principal.

Espera encontrar estes CSVs dentro da pasta `data/` no repositório
(Dormidas não tem aba própria, mas é usada no cálculo de "dias por
estadia" da aba Período de Hospedagem; Dormidas-por-Origem não é usada):

  Nível Distrito (agregado Município -> Distrito):
    data/populacao_residente_distrito_nativo_anual.csv   (2020-2025)
    data/turismo_hospedes_distrito_mensal.csv             (2020-2026)
    data/turismo_dormidas_distrito_mensal.csv             (2020-2026)
    data/turismo_hospedes_origem_distrito_anual.csv       (2020-2025, por país)

  Nível Concelho (granularidade nativa do INE):
    data/populacao_residente_concelho_anual.csv           (2020-2025, ver nota
                                                             'classificacao_nuts')
    data/turismo_hospedes_concelho_mensal.csv              (2020-2026)
    data/turismo_dormidas_concelho_mensal.csv              (2020-2026)
    data/turismo_hospedes_origem_concelho_anual.csv        (2020-2025, por país)

Nota sobre 'populacao_residente_concelho_anual.csv': não existe um único
indicador do INE que cubra 2020-2025 ao nível Município com a mesma
classificação, por isso o extrator reconcilia duas classificações NUTS
(2024 como fonte primária, 2013 só para completar anos que a 2024 não
cobre) e grava a proveniência na coluna 'classificacao_nuts'.
"""

import re
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="População e Turismo", page_icon="📊", layout="wide")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Ficheiros por nível geográfico. As chaves internas ("populacao",
# "hospedes", ...) são as mesmas nos dois níveis — só o nome do ficheiro
# muda — para o resto do código não precisar de saber qual nível está
# ativo.
ARQUIVOS_POR_NIVEL = {
    "Distrito": {
        "populacao": "populacao_residente_distrito_nativo_anual.csv",
        "hospedes": "turismo_hospedes_distrito_mensal.csv",
        "dormidas": "turismo_dormidas_distrito_mensal.csv",
        "hospedes_origem": "turismo_hospedes_origem_distrito_anual.csv",
    },
    "Concelho": {
        "populacao": "populacao_residente_concelho_anual.csv",
        "hospedes": "turismo_hospedes_concelho_mensal.csv",
        "dormidas": "turismo_dormidas_concelho_mensal.csv",
        "hospedes_origem": "turismo_hospedes_origem_concelho_anual.csv",
    },
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


# ---------------------------------------------------------------------------
# Seletor MESTRE de nível geográfico — a primeira decisão da página, porque
# determina que ficheiros carregar e qual coluna usar como eixo/agrupamento
# em TODAS as abas.
# ---------------------------------------------------------------------------

st.sidebar.header("Nível Geográfico")
nivel_geo = st.sidebar.radio(
    "Ver dados por:", ["Distrito", "Concelho"], horizontal=True, key="nivel_geo"
)
GEO_COL = "distrito" if nivel_geo == "Distrito" else "concelho"
ROTULO_GEO = nivel_geo  # "Distrito" ou "Concelho" — para textos/labels

dados = {chave: carregar(nome) for chave, nome in ARQUIVOS_POR_NIVEL[nivel_geo].items()}

if all(df.empty for df in dados.values()):
    st.error(
        f"Não encontrei nenhum dos ficheiros CSV de nível **{nivel_geo}** em "
        f"`data/`. Confirma que os CSVs gerados pelo extrator do INE foram "
        f"carregados para essa pasta no repositório."
    )
    st.stop()

st.title(f"📊 População e Turismo em Portugal — por {ROTULO_GEO}")
if nivel_geo == "Distrito":
    st.caption(
        "Fonte: INE — Estimativas anuais da população residente (2020-2025, por "
        "Distrito); Inquérito à Permanência de Hóspedes na Hotelaria e Outros "
        "Alojamentos (mensal, 2020-2026, agregado de Município para Distrito). "
        "Concelhos pequenos com valor confidencial não entram na soma do "
        "Distrito — números de distritos com muitos concelhos rurais podem "
        "estar ligeiramente subestimados."
    )
else:
    st.caption(
        "Fonte: INE — Estimativas anuais da população residente (2020-2025, "
        "reconciliando classificações NUTS-2024 e NUTS-2013 — ver coluna "
        "'classificacao_nuts' nas tabelas); Inquérito à Permanência de "
        "Hóspedes na Hotelaria e Outros Alojamentos (mensal, 2020-2026, "
        "granularidade nativa de Concelho). Cerca de 42% dos concelhos "
        "pequenos têm valor confidencial no turismo mensal — esses meses "
        "aparecem como vazios para esse concelho, não como zero."
    )


# ---------------------------------------------------------------------------
# Filtro de geografia partilhado (barra lateral) — usado pelas abas
# População, Turismo-Hóspedes, Período de Hospedagem e Cruzamento. As abas
# Divisão Etária e Hóspedes por Origem têm os seus próprios filtros no
# topo, como pedido.
#
# Comportamento por nível (decisão de UX): em Distrito, vazio = todos (só
# 20 entradas, continua legível). Em Concelho, vazio = NADA é mostrado —
# com ~308 concelhos, "todos por omissão" transforma os gráficos de
# ranking/linhas/barras empilhadas em ruído ilegível, por isso o modo
# Concelho obriga a escolher primeiro.
# ---------------------------------------------------------------------------

def todos_valores(dfs: list, coluna: str) -> list:
    valores = set()
    for df in dfs:
        if not df.empty and coluna in df.columns:
            valores.update(df[coluna].dropna().unique().tolist())
    return sorted(valores)


st.sidebar.header("Filtros (População / Hóspedes / Cruzamento)")
geo_disponiveis = todos_valores(list(dados.values()), GEO_COL)
geo_sel = st.sidebar.multiselect(
    f"{ROTULO_GEO} (vazio = {'todos' if nivel_geo == 'Distrito' else 'nada — escolhe pelo menos um'})",
    geo_disponiveis,
    default=geo_disponiveis if nivel_geo == "Distrito" else [],
)

if nivel_geo == "Concelho" and not geo_sel:
    st.sidebar.info(
        "Nenhum concelho selecionado — as abas que dependem deste filtro "
        "vão pedir para escolheres pelo menos um."
    )


def exige_selecao(sel: list, rotulo_contexto: str = "") -> bool:
    """Verdadeiro se o render pode prosseguir. No nível Concelho, exige
    seleção explícita (evita gráficos com ~308 categorias); no nível
    Distrito, vazio continua a significar 'todos', como antes."""
    if nivel_geo == "Concelho" and not sel:
        st.info(
            f"Modo Concelho: seleciona pelo menos um concelho"
            f"{(' ' + rotulo_contexto) if rotulo_contexto else ''} para ver "
            f"este gráfico — com ~308 concelhos, mostrar tudo por omissão "
            f"fica ilegível."
        )
        return False
    return True


def aplicar_filtro_geo(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    if not geo_sel:
        # Distrito: vazio = todos. Concelho: vazio = nada (o aviso já foi
        # mostrado por exige_selecao onde relevante).
        return df if nivel_geo == "Distrito" else df.iloc[0:0]
    return df[df[GEO_COL].isin(geo_sel)]


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


def aviso_muitos_geos(df: pd.DataFrame, limite: int = 10):
    n = df[GEO_COL].nunique()
    if n > limite:
        st.warning(
            f"{n} {ROTULO_GEO.lower()}s no gráfico — pode ficar poluído. "
            f"Seleciona alguns na barra lateral para veres melhor."
        )


def obter_total_populacao(df_pop: pd.DataFrame) -> pd.DataFrame:
    """Linhas de população TOTAL (todas as idades) por geo/ano. Prefere a
    categoria 'Total' de dim_4_t; se um indicador não a tiver, soma todas
    as faixas etárias como alternativa (defensivo — evita a aba ficar
    vazia por causa de uma diferença de estrutura entre indicadores)."""
    if df_pop.empty or "dim_4_t" not in df_pop.columns:
        return df_pop
    total = df_pop[df_pop["dim_4_t"] == "Total"]
    if not total.empty:
        return total
    chave = [c for c in [GEO_COL, "ano"] if c in df_pop.columns]
    return df_pop.groupby(chave, as_index=False)["valor"].sum()


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
        aviso_muitos_geos(df)
        resumo = (
            df.groupby(["data", GEO_COL], as_index=False)["valor"]
            .sum()
            .sort_values("data")
        )
        fig = px.line(
            resumo, x="data", y="valor", color=GEO_COL, markers=True,
            labels={"valor": titulo_eixo_y, "data": "Mês", GEO_COL: ROTULO_GEO},
        )
        fig.update_layout(legend_title_text=ROTULO_GEO, height=500)
        tabela = df[["ano", "mes", GEO_COL, "valor"]].sort_values(["ano", "mes", GEO_COL])
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
        if not geo_sel:
            st.caption(f"A somar todos os {ROTULO_GEO.lower()}s (nenhum filtro aplicado).")
        tabela = df[["ano", "mes", GEO_COL, "valor"]].sort_values(["ano", "mes", GEO_COL])
    else:  # Anual
        aviso_muitos_geos(df)
        resumo = df.groupby(["ano", GEO_COL], as_index=False)["valor"].sum().sort_values("ano")
        fig = px.line(
            resumo, x="ano", y="valor", color=GEO_COL, markers=True,
            labels={"valor": titulo_eixo_y, "ano": "Ano", GEO_COL: ROTULO_GEO},
        )
        fig.update_layout(legend_title_text=ROTULO_GEO, height=500)
        tabela = resumo[["ano", GEO_COL, "valor"]].sort_values(["ano", GEO_COL])

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
    st.subheader(f"Divisão etária da população, por {ROTULO_GEO}")
    st.caption(
        f"Cada segmento mostra a % da faixa etária sobre o TOTAL do "
        f"{ROTULO_GEO.lower()} (mesmo que só mostres algumas faixas, a % "
        f"continua a ser sobre o total real, não sobre a soma das faixas "
        f"visíveis)."
    )

    pop_base = dados["populacao"]
    anos_idade = sorted(pop_base["ano"].dropna().unique().tolist())
    geos_idade_disp = sorted(pop_base[GEO_COL].dropna().unique().tolist())
    faixas_idade = sorted(
        [f for f in pop_base["dim_4_t"].dropna().unique().tolist() if f != "Total"],
        key=chave_faixa_etaria,
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        geos_idade_sel = st.multiselect(
            ROTULO_GEO, geos_idade_disp,
            default=geos_idade_disp if nivel_geo == "Distrito" else [],
            key="idade_geos",
        )
    with col2:
        ano_idade_sel = st.selectbox(
            "Período (ano)", anos_idade, index=len(anos_idade) - 1, key="idade_ano"
        )
    with col3:
        faixas_idade_sel = st.multiselect(
            "Faixa etária", faixas_idade, default=faixas_idade, key="idade_faixas"
        )

    if not exige_selecao(geos_idade_sel, "(neste filtro acima)"):
        pass
    else:
        df_ano_idade = pop_base[pop_base["ano"] == ano_idade_sel]
        faixas_todas = df_ano_idade[df_ano_idade["dim_4_t"] != "Total"]
        totais_por_geo = (
            df_ano_idade[df_ano_idade["dim_4_t"] == "Total"].set_index(GEO_COL)["valor"].to_dict()
        )

        # "Total Portugal" é sempre calculado a partir de TODAS as
        # geografias do ano escolhido, independentemente do filtro acima.
        pt_faixas = faixas_todas.groupby("dim_4_t", as_index=False)["valor"].sum()
        pt_faixas[GEO_COL] = "Total Portugal"
        totais_por_geo["Total Portugal"] = sum(
            v for k, v in totais_por_geo.items() if k != "Total Portugal"
        )

        faixas_filtradas = faixas_todas[
            faixas_todas[GEO_COL].isin(geos_idade_sel)
            & faixas_todas["dim_4_t"].isin(faixas_idade_sel)
        ]
        faixas_final = pd.concat(
            [pt_faixas[pt_faixas["dim_4_t"].isin(faixas_idade_sel)], faixas_filtradas],
            ignore_index=True,
        )

        if faixas_final.empty:
            st.info("Sem dados para os filtros selecionados.")
        else:
            faixas_final["total_geo"] = faixas_final[GEO_COL].map(totais_por_geo)
            faixas_final["percentual"] = (
                faixas_final["valor"] / faixas_final["total_geo"] * 100
            )
            faixas_final["rotulo"] = faixas_final["percentual"].round(1).astype(str) + "%"

            ordem_geos = ["Total Portugal"] + [
                d for d in geos_idade_sel if d in faixas_final[GEO_COL].unique()
            ]

            fig_idade = px.bar(
                faixas_final, x=GEO_COL, y="percentual", color="dim_4_t", text="rotulo",
                category_orders={GEO_COL: ordem_geos, "dim_4_t": faixas_idade_sel},
                labels={"percentual": f"% da população do {ROTULO_GEO.lower()}", GEO_COL: ROTULO_GEO, "dim_4_t": "Faixa etária"},
            )
            fig_idade.update_traces(textposition="inside", textfont_size=10)
            fig_idade.update_layout(barmode="stack", height=650, legend_title_text="Faixa etária")
            st.plotly_chart(fig_idade, use_container_width=True, key="chart_idade")

            with st.expander("Ver tabela de dados"):
                tabela_idade = faixas_final[[GEO_COL, "dim_4_t", "valor", "percentual"]].sort_values(
                    [GEO_COL, "dim_4_t"], key=lambda s: s.map(chave_faixa_etaria) if s.name == "dim_4_t" else s
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

    if not exige_selecao(geo_sel):
        pass
    else:
        df_pop = aplicar_filtro_geo(dados["populacao"])
        df_pop = obter_total_populacao(df_pop)
        df_pop = filtro_ano(df_pop, key="pop_ano")

        if df_pop.empty:
            st.info("Sem dados para os filtros selecionados.")
        else:
            col_esq, col_dir = st.columns([2, 3])

            # --- gráfico esquerdo: barras, soma das geografias
            # selecionadas, 1 barra por ano, com rótulo de % de evolução
            # vs. ano anterior
            resumo_barra = (
                df_pop.groupby("ano", as_index=False)["valor"].sum().sort_values("ano")
            )
            resumo_barra["variacao_pct"] = resumo_barra["valor"].pct_change() * 100
            resumo_barra["rotulo"] = resumo_barra["variacao_pct"].apply(
                lambda v: f"{v:+.1f}%" if pd.notna(v) else ""
            )
            resumo_barra["ano_str"] = resumo_barra["ano"].astype(int).astype(str)

            with col_esq:
                st.markdown(f"**Total da população ({ROTULO_GEO.lower()}s selecionados)**")
                fig_barra = px.bar(
                    resumo_barra, x="ano_str", y="valor", text="rotulo",
                    labels={"valor": "População (N.º)", "ano_str": "Ano"},
                )
                fig_barra.update_traces(textposition="outside")
                fig_barra.update_layout(height=480)
                st.plotly_chart(fig_barra, use_container_width=True, key="chart_pop_barra")

            # --- gráfico direito: linhas por geografia, com rótulo no fim
            # de cada linha (nome + CAGR entre primeiro e último ano
            # selecionado)
            resumo_linha = (
                df_pop.groupby(["ano", GEO_COL], as_index=False)["valor"]
                .sum()
                .sort_values("ano")
            )
            anos_sel = sorted(resumo_linha["ano"].unique())
            ano_ini, ano_fim = anos_sel[0], anos_sel[-1]
            n_anos = ano_fim - ano_ini

            with col_dir:
                st.markdown(f"**Evolução por {ROTULO_GEO.lower()}** (CAGR {ano_ini}–{ano_fim})")
                aviso_muitos_geos(resumo_linha, limite=15)
                fig_linha = px.line(
                    resumo_linha, x="ano", y="valor", color=GEO_COL, markers=True,
                    labels={"valor": "População (N.º)", "ano": "Ano", GEO_COL: ROTULO_GEO},
                )
                fig_linha.update_layout(height=480, showlegend=False)

                cagr_por_geo = {}
                for geo, grp in resumo_linha.groupby(GEO_COL):
                    v_ini = grp.loc[grp["ano"] == ano_ini, "valor"]
                    v_fim = grp.loc[grp["ano"] == ano_fim, "valor"]
                    if not v_ini.empty and not v_fim.empty and v_ini.iloc[0] > 0 and n_anos > 0:
                        cagr = ((v_fim.iloc[0] / v_ini.iloc[0]) ** (1 / n_anos) - 1) * 100
                        cagr_por_geo[geo] = cagr
                        texto = f"{geo} ({cagr:+.1f}%)"
                    else:
                        cagr_por_geo[geo] = None
                        texto = geo
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
                with st.expander(f"Ver tabela — por {ROTULO_GEO.lower()} e ano", expanded=False):
                    tabela_cagr = resumo_linha.copy()
                    tabela_cagr["cagr_periodo_pct"] = tabela_cagr[GEO_COL].map(cagr_por_geo)
                    st.dataframe(tabela_cagr, use_container_width=True, hide_index=True)

# --- 3. Turismo — Hóspedes ---------------------------------------------------
with aba_hosp:
    st.subheader("Hóspedes nos estabelecimentos de alojamento turístico (mensal)")
    if not exige_selecao(geo_sel):
        pass
    else:
        df_hosp = aplicar_filtro_geo(dados["hospedes"])
        df_hosp = filtro_ano(df_hosp, key="hosp_ano")
        grafico_mensal(df_hosp, "Hóspedes (N.º)", "hospedes")

# --- 4. Período de Hospedagem ---------------------------------------------------
with aba_periodo:
    st.subheader(f"Período médio de hospedagem (dias), por {ROTULO_GEO} e Ano")
    st.caption(
        "Dormidas ÷ Hóspedes = número médio de noites por estadia. Mesma "
        "ressalva dos valores confidenciais aplica-se aqui, em ambos os "
        "indicadores."
    )

    if not exige_selecao(geo_sel):
        pass
    else:
        dorm_anual = (
            dados["dormidas"][["ano", GEO_COL, "valor"]]
            .groupby(["ano", GEO_COL], as_index=False)["valor"].sum()
            .rename(columns={"valor": "dormidas"})
        )
        hosp_anual_periodo = (
            dados["hospedes"][["ano", GEO_COL, "valor"]]
            .groupby(["ano", GEO_COL], as_index=False)["valor"].sum()
            .rename(columns={"valor": "hospedes"})
        )
        periodo = dorm_anual.merge(hosp_anual_periodo, on=["ano", GEO_COL], how="inner")
        periodo = periodo[periodo["hospedes"] > 0]
        periodo["valor"] = periodo["dormidas"] / periodo["hospedes"]

        periodo_f = aplicar_filtro_geo(periodo)
        periodo_f = filtro_ano(periodo_f, key="periodo_ano")

        if periodo_f.empty:
            st.info("Sem dados para os filtros selecionados.")
        else:
            aviso_muitos_geos(periodo_f)
            fig_periodo = px.line(
                periodo_f.sort_values("ano"), x="ano", y="valor", color=GEO_COL, markers=True,
                labels={"valor": "Dias por estadia", "ano": "Ano", GEO_COL: ROTULO_GEO},
            )
            fig_periodo.update_layout(legend_title_text=ROTULO_GEO, height=550)
            st.plotly_chart(fig_periodo, use_container_width=True, key="chart_periodo")

            with st.expander("Ver tabela de dados"):
                tabela_periodo = periodo_f[["ano", GEO_COL, "dormidas", "hospedes", "valor"]].sort_values(
                    ["ano", GEO_COL]
                )
                st.dataframe(tabela_periodo, use_container_width=True, hide_index=True)
                st.download_button(
                    "⬇️ Descarregar CSV filtrado",
                    tabela_periodo.to_csv(index=False).encode("utf-8-sig"),
                    file_name="periodo_hospedagem_filtrado.csv",
                    mime="text/csv",
                    key="download_periodo",
                )

# --- 5. Hóspedes por Origem (ranking) ---------------------------------------
with aba_hosp_o:
    st.subheader(f"Ranking dos países de origem dos hóspedes, por {ROTULO_GEO}")
    st.caption(
        "Cada linha é um país; a posição mostra em que lugar do ranking "
        f"esse país fica como origem de hóspedes em cada {ROTULO_GEO.lower()} "
        "(1º = maior número de hóspedes desse país)."
    )

    df_origem = dados["hospedes_origem"]
    df_origem = df_origem[df_origem["dim_3_t"] != "Total"]

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        geos_origem_disp = sorted(df_origem[GEO_COL].dropna().unique().tolist())
        geos_origem_sel = st.multiselect(
            ROTULO_GEO, geos_origem_disp,
            default=geos_origem_disp if nivel_geo == "Distrito" else [],
            key="origem_geos",
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
            f"Top N países por {ROTULO_GEO.lower()} (só se não escolheres países acima)",
            min_value=3, max_value=15, value=6, key="origem_topn",
        )

    if not exige_selecao(geos_origem_sel, "(no filtro acima desta aba)"):
        pass
    else:
        df_origem_f = df_origem[
            (df_origem["ano"] >= periodo_origem[0]) & (df_origem["ano"] <= periodo_origem[1])
        ]
        df_origem_f = df_origem_f[df_origem_f[GEO_COL].isin(geos_origem_sel)]

        agregado = df_origem_f.groupby([GEO_COL, "dim_3_t"], as_index=False)["valor"].sum()

        if agregado.empty:
            st.info("Sem dados para os filtros selecionados.")
        else:
            agregado["ranking"] = agregado.groupby(GEO_COL)["valor"].rank(
                method="min", ascending=False
            ).astype(int)

            if paises_origem_sel:
                agregado_plot = agregado[agregado["dim_3_t"].isin(paises_origem_sel)]
            else:
                paises_relevantes = agregado.loc[agregado["ranking"] <= top_n, "dim_3_t"].unique()
                agregado_plot = agregado[agregado["dim_3_t"].isin(paises_relevantes)]

            fig_ranking = px.line(
                agregado_plot.sort_values(["dim_3_t", GEO_COL]),
                x=GEO_COL, y="ranking", color="dim_3_t", markers=True,
                labels={"ranking": "Posição no ranking", GEO_COL: ROTULO_GEO, "dim_3_t": "País de origem"},
            )
            fig_ranking.update_yaxes(autorange="reversed", dtick=1)
            fig_ranking.update_layout(height=550, legend_title_text="País de origem")
            st.plotly_chart(fig_ranking, use_container_width=True, key="chart_ranking_origem")

            with st.expander("Ver tabela de dados"):
                st.dataframe(
                    agregado_plot.sort_values([GEO_COL, "ranking"]),
                    use_container_width=True, hide_index=True,
                )
                st.download_button(
                    "⬇️ Descarregar CSV filtrado",
                    agregado_plot.to_csv(index=False).encode("utf-8-sig"),
                    file_name="ranking_origem_filtrado.csv",
                    mime="text/csv",
                    key="download_ranking_origem",
                )

# --- 6. Cruzamento População × Turismo --------------------------------------
with aba_cruzamento:
    st.subheader(f"Hóspedes por 100 habitantes, por {ROTULO_GEO}")
    st.caption(
        "Cruza a população residente (ano completo, valor fixo dentro do "
        "ano) com os hóspedes. População fica fixa dentro do ano — a "
        "variação mensal/sazonal vem só do turismo. Só aparecem os anos em "
        "que há população estimada (2020-2025) — 2026 ainda não tem "
        "estimativa do INE."
    )

    if not exige_selecao(geo_sel):
        pass
    else:
        pop_total = obter_total_populacao(dados["populacao"])[
            ["ano", GEO_COL, "valor"]
        ].rename(columns={"valor": "populacao"})

        hosp_total = dados["hospedes"][["ano", "mes", "data", GEO_COL, "valor"]].rename(
            columns={"valor": "hospedes"}
        )

        cruzado = hosp_total.merge(pop_total, on=["ano", GEO_COL], how="inner")
        cruzado = cruzado[cruzado["populacao"] > 0]
        cruzado["valor"] = cruzado["hospedes"] / cruzado["populacao"] * 100

        cruzado = aplicar_filtro_geo(cruzado)
        cruzado = filtro_ano(cruzado, key="cruz_ano")

        if cruzado.empty:
            st.info("Sem dados suficientes para os filtros selecionados.")
        else:
            modo_cruz = st.radio(
                "Visualização", ["Série temporal", "Sazonalidade (mês × ano)", "Anual"],
                horizontal=True, key="modo_cruzamento",
            )

            if modo_cruz == "Série temporal":
                aviso_muitos_geos(cruzado)
                resumo = (
                    cruzado.groupby(["data", GEO_COL], as_index=False)["valor"]
                    .mean()
                    .sort_values("data")
                )
                fig_cruz = px.line(
                    resumo, x="data", y="valor", color=GEO_COL, markers=True,
                    labels={"valor": "Hóspedes por 100 habitantes", "data": "Mês", GEO_COL: ROTULO_GEO},
                )
                fig_cruz.update_layout(legend_title_text=ROTULO_GEO, height=500)
                tabela_cruz = cruzado[["ano", "mes", GEO_COL, "hospedes", "populacao", "valor"]]

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
                if not geo_sel:
                    st.caption(f"A somar todos os {ROTULO_GEO.lower()}s (nenhum filtro aplicado).")
                tabela_cruz = cruzado[["ano", "mes", GEO_COL, "hospedes", "populacao", "valor"]]

            else:  # Anual — soma hóspedes do ano inteiro / população desse
                # ano (recalcular a partir dos totais anuais, não fazer
                # média das razões mensais, que distorceria o resultado)
                aviso_muitos_geos(cruzado)
                hosp_anual = cruzado.groupby(["ano", GEO_COL], as_index=False)["hospedes"].sum()
                hosp_anual = hosp_anual.merge(pop_total, on=["ano", GEO_COL], how="left")
                hosp_anual["valor"] = hosp_anual["hospedes"] / hosp_anual["populacao"] * 100
                fig_cruz = px.line(
                    hosp_anual, x="ano", y="valor", color=GEO_COL, markers=True,
                    labels={"valor": "Hóspedes por 100 habitantes (ano)", "ano": "Ano", GEO_COL: ROTULO_GEO},
                )
                fig_cruz.update_layout(legend_title_text=ROTULO_GEO, height=500)
                tabela_cruz = hosp_anual[["ano", GEO_COL, "hospedes", "populacao", "valor"]]

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
