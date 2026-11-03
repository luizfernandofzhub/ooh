import pandas as pd
import streamlit as st

DATA_FILE = "data/clima_portugal.csv"

ESTACAO = {
    12: "Inverno", 1: "Inverno", 2: "Inverno",
    3: "Primavera", 4: "Primavera", 5: "Primavera",
    6: "Verão", 7: "Verão", 8: "Verão",
    9: "Outono", 10: "Outono", 11: "Outono",
}

DIAS_SEMANA_PT = {
    0: "segunda-feira", 1: "terça-feira", 2: "quarta-feira", 3: "quinta-feira",
    4: "sexta-feira", 5: "sábado", 6: "domingo",
}


def calcular_wknd_code(df):
    """Numera sequencialmente os fins de semana de cada ano (Sab+Dom = mesmo numero)."""
    datas = pd.to_datetime(df["Data"])

    # Para cada linha de fim de semana, calcula a data do sabado correspondente.
    # Sabado -> mesma data; domingo -> dia anterior; dias de semana -> NaT.
    weekday = datas.dt.weekday
    data_sabado = datas.where(weekday == 5)
    data_sabado = data_sabado.mask(weekday == 6, datas - pd.Timedelta(days=1))

    # Cria uma tabela independente de sabados e atribui um numero sequencial por ano.
    sabados = pd.Series(data_sabado.dropna().unique())
    if sabados.empty:
        return pd.Series(pd.NA, index=df.index, dtype="Int64")

    sabados = pd.to_datetime(sabados).sort_values().reset_index(drop=True)
    tabela = pd.DataFrame({"DataSabado": sabados})
    tabela["Ano"] = tabela["DataSabado"].dt.year
    tabela["Wknd Code"] = tabela.groupby("Ano").cumcount() + 1

    mapa = tabela.set_index("DataSabado")["Wknd Code"]

    # Um unico map, sem atribuicao booleana dentro de Series.
    # Isso evita o erro 'setting an array element with a sequence'.
    resultado = data_sabado.map(mapa)
    return resultado.astype("Int64")


@st.cache_data(ttl=3600)
def carregar_dados():
    df = pd.read_csv(DATA_FILE, parse_dates=["Data"])
    df["Ano"] = df["Data"].dt.year
    df["Mes"] = df["Data"].dt.month
    df["Dia"] = df["Data"].dt.day
    df["Dia do Ano"] = df["Data"].dt.dayofyear
    df["Estação"] = df["Mes"].map(ESTACAO)
    df["Dia da Semana"] = df["Data"].dt.weekday.map(DIAS_SEMANA_PT)
    df["FDS"] = df["Data"].dt.weekday.apply(
        lambda d: "Fim de Semana" if d >= 5 else "Semana"
    )
    df["Wknd Code"] = calcular_wknd_code(df)
    df["#FDS"] = df["Wknd Code"].apply(
        lambda x: f"FDS {int(x)}" if pd.notna(x) else ""
    )
    return df
