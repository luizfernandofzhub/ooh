"""
update_data.py
Roda localmente todos os dias (via Windows Task Scheduler).
1. Lê o CSV já existente em data/clima_portugal.csv
2. Descobre a última data registada por cidade
3. Baixa só os dias novos (open-meteo)
4. Acrescenta ao CSV
5. Faz commit + push para o GitHub (o site em Streamlit Cloud lê direto do repo)
"""

import subprocess
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

REPO_DIR = Path(__file__).resolve().parent          # pasta do repo git local
DATA_FILE = REPO_DIR / "data" / "clima_portugal.csv"

CIDADES = {
    "Faro": {"lat": 37.0194, "lon": -7.9304},
    "Lisboa": {"lat": 38.7169, "lon": -9.1399},
    "Porto": {"lat": 41.1579, "lon": -8.6291},
    "Coimbra": {"lat": 40.2033, "lon": -8.4103},
    "Braga": {"lat": 41.5454, "lon": -8.4265},
    "Évora": {"lat": 38.5667, "lon": -7.9000},
    "Bragança": {"lat": 41.8061, "lon": -6.7570},
}

# Primeira execução (repo sem dados ainda) começa aqui
DATA_INICIO_BACKFILL = "2015-01-01"

WMO_CODES = {
    0: "Céu limpo / Ensolarado", 1: "Predominantemente ensolarado",
    2: "Parcialmente nublado", 3: "Nublado",
    45: "Nevoeiro", 48: "Nevoeiro com geada",
    51: "Garoa / Chuvisco fraco", 53: "Garoa / Chuvisco moderado", 55: "Garoa / Chuvisco denso",
    61: "Chuva fraca", 63: "Chuva moderada", 65: "Chuva forte",
    71: "Neve fraca", 73: "Neve moderada", 75: "Neve forte",
    80: "Pancadas de chuva fracas", 81: "Pancadas de chuva moderadas", 82: "Pancadas de chuva violentas",
    95: "Trovoada / Tempestade", 96: "Tempestade com granizo leve", 99: "Tempestade com granizo forte",
}


def clima_simplificado(code):
    if code in (0, 1):
        return "Ensolarado"
    if code in (2, 3):
        return "Nublado"
    if code in (45, 48):
        return "Nevoeiro"
    if code in (51, 53, 55, 61, 63, 65, 80, 81, 82):
        return "Chuva"
    if code in (71, 73, 75):
        return "Neve"
    if code in (95, 96, 99):
        return "Tempestade"
    return "Outro"


def baixar_com_retentativa(url, params, max_tentativas=5):
    for tentativa in range(max_tentativas):
        try:
            r = requests.get(url, params=params, verify=False, timeout=30)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 429:
                espera = (tentativa + 1) * 5
                print(f"   [429] limite atingido, a aguardar {espera}s...")
                time.sleep(espera)
            else:
                print(f"   erro HTTP {r.status_code}")
                return None
        except Exception as e:
            print(f"   erro de ligação: {e} (tentativa {tentativa + 1}/{max_tentativas})")
            time.sleep(3)
    return None


def baixar_cidade(cidade, coords, data_inicio, data_fim):
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": coords["lat"],
        "longitude": coords["lon"],
        "start_date": data_inicio,
        "end_date": data_fim,
        "daily": [
            "temperature_2m_max",
            "temperature_2m_min",
            "temperature_2m_mean",
            "precipitation_sum",
            "weather_code",
        ],
        "timezone": "Europe/Lisbon",
    }
    data = baixar_com_retentativa(url, params)
    if not data or "daily" not in data:
        return pd.DataFrame()

    d = data["daily"]
    n = len(d.get("time", []))
    linhas = []
    for i in range(n):
        code = d["weather_code"][i]
        linhas.append({
            "Cidade": cidade,
            "Data": d["time"][i],
            "Temp. Máxima (°C)": d["temperature_2m_max"][i],
            "Temp. Mínima (°C)": d["temperature_2m_min"][i],
            "Temp. Média (°C)": d["temperature_2m_mean"][i],
            "Precipitação (mm)": d["precipitation_sum"][i],
            "Clima Simplificado": clima_simplificado(code),
            "Condição do Clima": WMO_CODES.get(code, f"Outro ({code})"),
            "Código WMO": code,
        })
    return pd.DataFrame(linhas)


def git(*args):
    """Corre um comando git dentro do repo e devolve (ok, output)."""
    result = subprocess.run(
        ["git", *args], cwd=REPO_DIR, capture_output=True, text=True
    )
    return result.returncode == 0, (result.stdout + result.stderr).strip()


def main():
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    hoje = date.today()
    ontem = (hoje - timedelta(days=1)).isoformat()  # a API só tem dados fechados até ontem

    if DATA_FILE.exists():
        df_existente = pd.read_csv(DATA_FILE, parse_dates=["Data"])
    else:
        df_existente = pd.DataFrame()

    novos_blocos = []
    for cidade, coords in CIDADES.items():
        if not df_existente.empty and cidade in df_existente["Cidade"].values:
            ultima_data = df_existente.loc[df_existente["Cidade"] == cidade, "Data"].max()
            inicio = (ultima_data + timedelta(days=1)).strftime("%Y-%m-%d")
        else:
            inicio = DATA_INICIO_BACKFILL

        if inicio > ontem:
            print(f"-> {cidade}: já atualizado.")
            continue

        print(f"-> {cidade}: a baixar {inicio} até {ontem}...")
        bloco = baixar_cidade(cidade, coords, inicio, ontem)
        if not bloco.empty:
            print(f"   {len(bloco)} novos registos.")
            novos_blocos.append(bloco)
        else:
            print("   sem dados novos / falha.")
        time.sleep(1.5)

    if not novos_blocos:
        print("\nNada para atualizar hoje.")
        return

    df_novo = pd.concat(novos_blocos, ignore_index=True)
    df_novo["Data"] = pd.to_datetime(df_novo["Data"])

    df_final = pd.concat([df_existente, df_novo], ignore_index=True)
    df_final = df_final.drop_duplicates(subset=["Cidade", "Data"]).sort_values(["Cidade", "Data"])
    df_final.to_csv(DATA_FILE, index=False)
    print(f"\nGuardado: {DATA_FILE} ({len(df_final)} linhas totais, +{len(df_novo)} novas).")

    # --- commit + push ---
    ok, out = git("add", str(DATA_FILE.relative_to(REPO_DIR)))
    if not ok:
        print("git add falhou:", out)
        sys.exit(1)

    msg = f"Atualização de dados: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    ok, out = git("commit", "-m", msg)
    if not ok:
        # nada para commitar não é erro fatal
        print("git commit:", out)
        return

    ok, out = git("push")
    if not ok:
        print("git push falhou:", out)
        sys.exit(1)
    print("Push feito com sucesso. O site vai atualizar automaticamente.")


if __name__ == "__main__":
    main()
