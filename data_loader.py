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
    """Numera sequencialmente os fins de semana de cada ano (Sáb+Dom = mesmo número)."""
    weekday = df["Data"].dt.weekday  # segunda=0 ... domingo=6
    sabados = df.loc[weekday == 5, ["Data"]].drop_duplicates().sort_values("Data").copy()
    sabados["Ano"] = sabados["Data"].dt.year
    sabados["Wknd Code"] = sabados.groupby("Ano").cumcount() + 1
    mapa = dict(zip(sabados["Data"], sabados["Wknd Code"]))

    wknd_code = df["Data"].map(mapa)  # preenche os sábados
    domingos_mask = weekday == 6
    # domingo herda o código do sábado anterior (mesmo fim de semana)
    wknd_code[domingos_mask] = (df["Data"] - pd.Timedelta(days=1)).map(mapa)[domingos_mask]
    return wknd_code


@st.cache_data(ttl=3600)
def carregar_dados():
    df = pd.read_csv(DATA_FILE, parse_dates=["Data"])
    df["Ano"] = df["Data"].dt.year
    df["Mes"] = df["Data"].dt.month
    df["Dia"] = df["Data"].dt.day
    df["Dia do Ano"] = df["Data"].dt.dayofyear  # equivalente ao "Dia Seguido"
    df["Estação"] = df["Mes"].map(ESTACAO)
    df["Dia da Semana"] = df["Data"].dt.weekday.map(DIAS_SEMANA_PT)
    df["FDS"] = df["Data"].dt.weekday.apply(lambda d: "Fim de Semana" if d >= 5 else "Semana")
    df["Wknd Code"] = calcular_wknd_code(df)
    df["#FDS"] = df["Wknd Code"].apply(lambda x: f"FDS {int(x)}" if pd.notna(x) else "")
    return df
