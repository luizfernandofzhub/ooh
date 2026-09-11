"""
Extrator de dados do INE (Portugal): população residente (anual) e
turismo - dormidas/hóspedes em alojamento turístico (mensal).

Fluxo:
  1) Baixa o catálogo completo de indicadores do INE (XML, ~10.000 indicadores).
  2) Filtra os indicadores candidatos por tema/descrição/periodicidade.
  3) Mostra os candidatos encontrados (título, varcd, nível geográfico,
     periodicidade, último período disponível) para validares manualmente
     qual usar — a etapa mais importante para garantir qualidade.
  4) Extrai os dados do(s) indicador(es) escolhido(s) via API JSON do INE
     e grava em CSV.

Uso:
  python ine_extrator_populacao_turismo.py descobrir
      -> lista candidatos de indicadores (população e turismo)

  python ine_extrator_populacao_turismo.py extrair --populacao 0008273 --turismo-dormidas 0010415 --turismo-hospedes <varcd>
      -> extrai os indicadores escolhidos (varcd obtido no passo "descobrir")

Requisitos: pip install requests pandas
"""

import argparse
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET
from dataclasses import dataclass

import pandas as pd
import requests

CATALOGO_URL = "https://www.ine.pt/ine/xml_indic.jsp?opc=2&lang=PT"
INDICADOR_URL = "https://www.ine.pt/ine/json_indicador/pindica.jsp?op=2&varcd={varcd}&lang=PT"

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; data-extraction-script/1.0)"}

# Tabela estática distrito -> concelhos (Carta Administrativa Oficial de
# Portugal). Embutida diretamente no script para não depender de nenhuma
# API externa (evita falhas de SSL/rate-limit como as já encontradas).
# Confere: 278 concelhos no Continente (18 distritos) + 19 Açores + 11
# Madeira = 308 municípios no total.
DISTRITOS_CONCELHOS = {
    "Aveiro": [
        "Águeda", "Albergaria-a-Velha", "Anadia", "Arouca", "Aveiro",
        "Castelo de Paiva", "Espinho", "Estarreja", "Ílhavo", "Mealhada",
        "Murtosa", "Oliveira de Azeméis", "Oliveira do Bairro", "Ovar",
        "Santa Maria da Feira", "São João da Madeira", "Sever do Vouga",
        "Vagos", "Vale de Cambra",
    ],
    "Beja": [
        "Aljustrel", "Almodôvar", "Alvito", "Barrancos", "Beja",
        "Castro Verde", "Cuba", "Ferreira do Alentejo", "Mértola", "Moura",
        "Odemira", "Ourique", "Serpa", "Vidigueira",
    ],
    "Braga": [
        "Amares", "Barcelos", "Braga", "Cabeceiras de Basto",
        "Celorico de Basto", "Esposende", "Fafe", "Guimarães",
        "Póvoa de Lanhoso", "Terras de Bouro", "Vieira do Minho",
        "Vila Nova de Famalicão", "Vila Verde", "Vizela",
    ],
    "Bragança": [
        "Alfândega da Fé", "Bragança", "Carrazeda de Ansiães",
        "Freixo de Espada à Cinta", "Macedo de Cavaleiros",
        "Miranda do Douro", "Mirandela", "Mogadouro", "Torre de Moncorvo",
        "Vila Flor", "Vimioso", "Vinhais",
    ],
    "Castelo Branco": [
        "Belmonte", "Castelo Branco", "Covilhã", "Fundão", "Idanha-a-Nova",
        "Oleiros", "Penamacor", "Proença-a-Nova", "Sertã", "Vila de Rei",
        "Vila Velha de Ródão",
    ],
    "Coimbra": [
        "Arganil", "Cantanhede", "Coimbra", "Condeixa-a-Nova",
        "Figueira da Foz", "Góis", "Lousã", "Mira", "Miranda do Corvo",
        "Montemor-o-Velho", "Oliveira do Hospital", "Pampilhosa da Serra",
        "Penacova", "Penela", "Soure", "Tábua", "Vila Nova de Poiares",
    ],
    "Évora": [
        "Alandroal", "Arraiolos", "Borba", "Estremoz", "Évora",
        "Montemor-o-Novo", "Mora", "Mourão", "Portel", "Redondo",
        "Reguengos de Monsaraz", "Vendas Novas", "Viana do Alentejo",
        "Vila Viçosa",
    ],
    "Faro": [
        "Albufeira", "Alcoutim", "Aljezur", "Castro Marim", "Faro",
        "Lagoa", "Lagos", "Loulé", "Monchique", "Olhão", "Portimão",
        "São Brás de Alportel", "Silves", "Tavira", "Vila do Bispo",
        "Vila Real de Santo António",
    ],
    "Guarda": [
        "Aguiar da Beira", "Almeida", "Celorico da Beira",
        "Figueira de Castelo Rodrigo", "Fornos de Algodres", "Gouveia",
        "Guarda", "Manteigas", "Mêda", "Pinhel", "Sabugal", "Seia",
        "Trancoso", "Vila Nova de Foz Côa",
    ],
    "Leiria": [
        "Alcobaça", "Alvaiázere", "Ansião", "Batalha", "Bombarral",
        "Caldas da Rainha", "Castanheira de Pêra", "Figueiró dos Vinhos",
        "Leiria", "Marinha Grande", "Nazaré", "Óbidos", "Pedrógão Grande",
        "Peniche", "Pombal", "Porto de Mós",
    ],
    "Lisboa": [
        "Alenquer", "Amadora", "Arruda dos Vinhos", "Azambuja", "Cadaval",
        "Cascais", "Lisboa", "Loures", "Lourinhã", "Mafra", "Odivelas",
        "Oeiras", "Sintra", "Sobral de Monte Agraço", "Torres Vedras",
        "Vila Franca de Xira",
    ],
    "Portalegre": [
        "Alter do Chão", "Arronches", "Avis", "Campo Maior",
        "Castelo de Vide", "Crato", "Elvas", "Fronteira", "Gavião",
        "Marvão", "Monforte", "Nisa", "Ponte de Sor", "Portalegre",
        "Sousel",
    ],
    "Porto": [
        "Amarante", "Baião", "Felgueiras", "Gondomar", "Lousada", "Maia",
        "Marco de Canaveses", "Matosinhos", "Paços de Ferreira", "Paredes",
        "Penafiel", "Porto", "Póvoa de Varzim", "Santo Tirso", "Trofa",
        "Valongo", "Vila do Conde", "Vila Nova de Gaia",
    ],
    "Santarém": [
        "Abrantes", "Alcanena", "Almeirim", "Alpiarça", "Benavente",
        "Cartaxo", "Chamusca", "Constância", "Coruche", "Entroncamento",
        "Ferreira do Zêzere", "Golegã", "Mação", "Ourém", "Rio Maior",
        "Salvaterra de Magos", "Santarém", "Sardoal", "Tomar",
        "Torres Novas", "Vila Nova da Barquinha",
    ],
    "Setúbal": [
        "Alcácer do Sal", "Alcochete", "Almada", "Barreiro", "Grândola",
        "Moita", "Montijo", "Palmela", "Santiago do Cacém", "Seixal",
        "Sesimbra", "Setúbal", "Sines",
    ],
    "Viana do Castelo": [
        "Arcos de Valdevez", "Caminha", "Melgaço", "Monção",
        "Paredes de Coura", "Ponte da Barca", "Ponte de Lima", "Valença",
        "Viana do Castelo", "Vila Nova de Cerveira",
    ],
    "Vila Real": [
        "Alijó", "Boticas", "Chaves", "Mesão Frio", "Mondim de Basto",
        "Montalegre", "Murça", "Peso da Régua", "Ribeira de Pena",
        "Sabrosa", "Santa Marta de Penaguião", "Valpaços",
        "Vila Pouca de Aguiar", "Vila Real",
    ],
    "Viseu": [
        "Armamar", "Carregal do Sal", "Castro Daire", "Cinfães", "Lamego",
        "Mangualde", "Moimenta da Beira", "Mortágua", "Nelas",
        "Oliveira de Frades", "Penalva do Castelo", "Penedono", "Resende",
        "Santa Comba Dão", "São João da Pesqueira", "São Pedro do Sul",
        "Sátão", "Sernancelhe", "Tabuaço", "Tarouca", "Tondela",
        "Vila Nova de Paiva", "Viseu", "Vouzela",
    ],
}

# Açores e Madeira não têm "distrito" (têm Região Autónoma). Inclui as
# grafias com sufixo observadas nos indicadores do INE (R.A.A./R.A.M.)
# além das formas por extenso, para robustez do match.
MUNICIPIOS_ACORES = [
    "Angra do Heroísmo", "Calheta (Açores)", "Calheta (R.A.A.)", "Corvo", "Horta",
    "Lagoa (Açores)", "Lagoa (R.A.A.)", "Lajes das Flores", "Lajes do Pico", "Madalena",
    "Nordeste", "Ponta Delgada", "Povoação", "Praia da Vitória",
    "Vila da Praia da Vitória", "Ribeira Grande",
    "Santa Cruz da Graciosa", "Santa Cruz das Flores", "São Roque do Pico", "Velas",
    "Vila do Porto", "Vila Franca do Campo",
]
MUNICIPIOS_MADEIRA = [
    "Funchal", "Câmara de Lobos", "Santa Cruz", "Machico", "Santana",
    "São Vicente", "Porto Moniz", "Calheta (Madeira)", "Calheta (R.A.M.)",
    "Ponta do Sol", "Ribeira Brava", "Porto Santo",
]

# Designações de níveis geográficos agregados (NUTS I/II/III — versões
# antiga NUTS-2013 e atual NUTS-2024 — e "Continente") que aparecem na
# mesma coluna geo_dsg de vários indicadores do INE junto com os
# municípios. Não são município, por isso é esperado não terem distrito —
# servem só para não poluir o aviso de "não encontrados" com casos que
# não são erro.
NIVEIS_AGREGADOS_CONHECIDOS = {
    "portugal", "continente",
    "norte", "centro", "algarve", "alentejo",
    "regiao autonoma dos acores", "regiao autonoma da madeira",
    "area metropolitana de lisboa", "area metropolitana do porto",
    "alto minho", "cavado", "ave", "tamega e sousa", "douro",
    "terras de tras os montes", "alto tamega e barroso",
    "oeste", "oeste e vale do tejo", "regiao de aveiro", "regiao de coimbra",
    "regiao de leiria", "viseu dao lafoes", "beira baixa",
    "beiras e serra da estrela", "medio tejo", "leziria do tejo",
    "alentejo litoral", "alto alentejo", "alentejo central", "baixo alentejo",
    "grande lisboa", "peninsula de setubal", "alto tamega",
}


def normalizar(nome: str) -> str:
    """Normaliza um nome de localidade para permitir match robusto entre
    fontes (remove acentos, hífens, espaços extra, texto de hierarquia
    geográfica tipo 'Portugal > ... > Sintra' -> 'sintra')."""
    if not nome:
        return ""
    nome = str(nome).strip()
    nome = nome.split(">")[-1].strip()
    nome = nome.replace("-", " ")
    nfkd = unicodedata.normalize("NFKD", nome)
    sem_acentos = "".join(c for c in nfkd if not unicodedata.combining(c))
    sem_acentos = " ".join(sem_acentos.split())  # colapsa espaços múltiplos
    return sem_acentos.lower().strip()


def carregar_mapa_distritos() -> dict:
    """Constrói {concelho_normalizado: distrito} a partir da tabela estática
    DISTRITOS_CONCELHOS (Continente) + Açores/Madeira. 100% offline —
    nenhuma chamada de rede, imune a falhas de SSL/rate-limit."""
    mapa = {}
    for distrito, concelhos in DISTRITOS_CONCELHOS.items():
        for c in concelhos:
            mapa[normalizar(c)] = distrito

    for m in MUNICIPIOS_ACORES:
        mapa[normalizar(m)] = "Região Autónoma dos Açores"
    for m in MUNICIPIOS_MADEIRA:
        mapa[normalizar(m)] = "Região Autónoma da Madeira"

    print(f"Mapa de distritos carregado (offline): {len(mapa)} entradas.", file=sys.stderr)
    return mapa


def resolver_distrito(nome, geo_cod, mapa_distritos: dict):
    """Resolve o distrito de uma linha, com regra especial para nomes
    ambíguos que se repetem entre regiões (ex.: 'Calheta' existe em Açores
    e Madeira com o mesmo nome). Nesses casos usa o geo_cod do INE, cujo
    primeiro dígito indica a região (1=Continente, 2=Açores, 3=Madeira)."""
    n = normalizar(nome)
    if n == "calheta" and pd.notna(geo_cod):
        primeiro_digito = str(int(geo_cod))[0] if str(geo_cod).strip() else ""
        if primeiro_digito == "2":
            return "Região Autónoma dos Açores"
        if primeiro_digito == "3":
            return "Região Autónoma da Madeira"
    return mapa_distritos.get(n)


def adicionar_distrito_concelho(df: pd.DataFrame, mapa_distritos: dict) -> pd.DataFrame:
    """Adiciona colunas 'concelho' (nome tal como veio do INE), 'distrito' e
    'nivel_geo' ('Município' ou 'Agregado'/'Desconhecido')."""
    if df.empty or "geo_dsg" not in df.columns:
        return df
    df = df.copy()
    df["concelho"] = df["geo_dsg"]
    geo_cod_col = df["geo_cod"] if "geo_cod" in df.columns else pd.Series([None] * len(df))
    df["distrito"] = [
        resolver_distrito(n, c, mapa_distritos) for n, c in zip(df["geo_dsg"], geo_cod_col)
    ]

    def classificar(nome, distrito):
        if pd.notna(distrito):
            return "Município"
        if normalizar(nome) in NIVEIS_AGREGADOS_CONHECIDOS:
            return "Agregado (NUTS/Continente)"
        return "Desconhecido"

    df["nivel_geo"] = [classificar(n, d) for n, d in zip(df["geo_dsg"], df["distrito"])]

    desconhecidos = sorted(
        df.loc[df["nivel_geo"] == "Desconhecido", "geo_dsg"].dropna().unique()
    )
    if desconhecidos:
        amostra = desconhecidos[:15]
        sufixo = " ..." if len(desconhecidos) > 15 else ""
        print(
            f"[aviso] {len(desconhecidos)} valor(es) de 'geo_dsg' realmente não "
            f"reconhecidos (nem município nem agregado NUTS conhecido — vale a "
            f"pena confirmar a grafia): {amostra}{sufixo}",
            file=sys.stderr,
        )
    return df


@dataclass
class Indicador:
    varcd: str
    title: str
    description: str
    theme: str
    subtheme: str
    geo_lastlevel: str
    periodicity: str
    last_period: str


def baixar_catalogo() -> list[Indicador]:
    """Baixa e faz parsing do catálogo completo de indicadores do INE.
    Isto é um ficheiro grande (pode demorar 1-2 minutos)."""
    print("A descarregar catálogo completo do INE (pode demorar)...", file=sys.stderr)
    resp = requests.get(CATALOGO_URL, headers=HEADERS, timeout=180)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)

    indicadores = []
    for ind in root.findall("indicator"):
        def txt(tag, default=""):
            el = ind.find(tag)
            return el.text.strip() if el is not None and el.text else default

        dates = ind.find("dates")
        last_period = ""
        if dates is not None:
            lp = dates.find("last_period_available")
            last_period = lp.text.strip() if lp is not None and lp.text else ""

        indicadores.append(
            Indicador(
                varcd=txt("varcd"),
                title=txt("title"),
                description=txt("description"),
                theme=txt("theme"),
                subtheme=txt("subtheme"),
                geo_lastlevel=txt("geo_lastlevel"),
                periodicity=txt("periodicity"),
                last_period=last_period,
            )
        )
    print(f"Catálogo carregado: {len(indicadores)} indicadores.", file=sys.stderr)
    return indicadores


def filtrar(indicadores: list[Indicador], termos: list[str], periodicidade: str = "") -> list[Indicador]:
    termos_lower = [t.lower() for t in termos]
    out = []
    for ind in indicadores:
        blob = f"{ind.title} {ind.description} {ind.subtheme}".lower()
        if all(t in blob for t in termos_lower):
            if not periodicidade or ind.periodicity.lower() == periodicidade.lower():
                out.append(ind)
    return out


def mostrar(indicadores: list[Indicador], titulo: str):
    print(f"\n=== {titulo} ({len(indicadores)} candidatos) ===")
    for ind in indicadores:
        print(f"- varcd={ind.varcd} | geo={ind.geo_lastlevel} | period={ind.periodicity} "
              f"| último={ind.last_period}")
        print(f"    título: {ind.title}")
        print(f"    descrição: {ind.description}")


def descobrir():
    indicadores = baixar_catalogo()

    populacao = filtrar(
        indicadores,
        termos=["população residente", "estimativas anuais"],
        periodicidade="Anual",
    )
    mostrar(populacao, "POPULAÇÃO RESIDENTE (candidatos)")

    dormidas = filtrar(
        indicadores,
        termos=["dormidas", "alojamento turístico"],
    )
    mostrar(dormidas, "DORMIDAS - alojamento turístico (candidatos)")

    hospedes = filtrar(
        indicadores,
        termos=["hóspedes", "alojamento turístico"],
    )
    mostrar(hospedes, "HÓSPEDES - alojamento turístico (candidatos)")

    print(
        "\nEscolhe o varcd mais adequado de cada lista (idealmente geo=Município "
        "ou geo=Distrito, conforme a tua necessidade, e o maior período histórico "
        "disponível) e usa o modo 'extrair'."
    )


def extrair_periodo_ano_mes(periodo: str):
    """Extrai (ano, mes) de um código de período do INE, ex.:
    'S7A2023' -> (2023, None); 'S3A202512' -> (2025, 12)."""
    digitos = re.sub(r"[^0-9]", "", periodo or "")
    if len(digitos) == 4:
        return int(digitos), None
    if len(digitos) == 6:
        return int(digitos[:4]), int(digitos[4:])
    return None, None


def extrair_indicador(varcd: str) -> pd.DataFrame:
    """Extrai os dados de um indicador do INE via API JSON e devolve um
    DataFrame com: varcd, periodo, ano, mes, geo_cod, geo_dsg, valor,
    unidade + QUALQUER outra dimensão que o indicador tenha (sexo, grupo
    etário, tipo de alojamento, país de residência, etc.) capturada tal
    como o INE a devolve, sem assumir nomes de campos fixos — importante
    porque vários indicadores têm mais do que uma linha por concelho+ano
    (uma por combinação de dimensões), e sem essas colunas não dá para
    distinguir o Total das quebras."""
    url = INDICADOR_URL.format(varcd=varcd)
    resp = requests.get(url, headers=HEADERS, timeout=120)
    resp.raise_for_status()
    data = resp.json()

    registos = []
    if isinstance(data, list) and data:
        bloco = data[0]
        dados = bloco.get("Dados", {})
        unidade = bloco.get("UnidadeMedida", "")
        for periodo, valores in dados.items():
            ano, mes = extrair_periodo_ano_mes(periodo)
            for v in valores:
                registo = {
                    "varcd": varcd,
                    "periodo": periodo,
                    "ano": ano,
                    "mes": mes,
                    "geo_cod": v.get("geocod"),
                    "geo_dsg": v.get("geodsg"),
                    "valor": v.get("valor"),
                    "unidade": unidade,
                }
                for k, val in v.items():
                    if k in ("geocod", "geodsg", "valor"):
                        continue
                    registo[k] = val
                registos.append(registo)
    df = pd.DataFrame(registos)

    extras = [
        c for c in df.columns
        if c not in ("varcd", "periodo", "ano", "mes", "geo_cod", "geo_dsg", "valor", "unidade")
    ]
    if extras:
        print(f"[info] {varcd}: dimensões extra encontradas: {extras}", file=sys.stderr)
        for col in extras:
            valores_unicos = sorted(df[col].dropna().unique().tolist())[:20]
            print(f"        {col}: {valores_unicos}", file=sys.stderr)
    n_linhas_por_geo_ano = len(df) / max(df[["geo_dsg", "periodo"]].drop_duplicates().shape[0], 1)
    if n_linhas_por_geo_ano > 1.01:
        print(
            f"[aviso] {varcd}: há em média {n_linhas_por_geo_ano:.1f} linhas por "
            f"concelho+período — este indicador tem quebras (dimensões extra "
            f"acima). Filtra pela categoria 'Total' dessas colunas antes de "
            f"somar/comparar valores entre concelhos.",
            file=sys.stderr,
        )
    return df


def extrair(args):
    algum_varcd = any(
        [
            args.populacao,
            args.turismo_dormidas,
            args.turismo_hospedes,
            args.turismo_dormidas_origem,
            args.turismo_hospedes_origem,
        ]
    )
    if not algum_varcd:
        print(
            "Nenhum varcd fornecido. Usa --populacao / --turismo-dormidas / "
            "--turismo-hospedes / --turismo-dormidas-origem / --turismo-hospedes-origem."
        )
        return

    mapa_distritos = carregar_mapa_distritos()

    def processar(varcd: str, nome_ficheiro: str):
        df = extrair_indicador(varcd)
        df = adicionar_distrito_concelho(df, mapa_distritos)
        df.to_csv(nome_ficheiro, index=False, encoding="utf-8-sig")
        print(f"Gravado {nome_ficheiro} ({len(df)} linhas)")
        return df

    if args.populacao:
        processar(args.populacao, "populacao_residente_anual.csv")

    if args.turismo_dormidas:
        processar(args.turismo_dormidas, "turismo_dormidas.csv")

    if args.turismo_hospedes:
        processar(args.turismo_hospedes, "turismo_hospedes.csv")

    if args.turismo_dormidas_origem:
        processar(args.turismo_dormidas_origem, "turismo_dormidas_origem.csv")

    if args.turismo_hospedes_origem:
        processar(args.turismo_hospedes_origem, "turismo_hospedes_origem.csv")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="modo", required=True)

    sub.add_parser("descobrir", help="Lista indicadores candidatos no catálogo do INE")

    p_extrair = sub.add_parser("extrair", help="Extrai dados de indicadores específicos (varcd)")
    p_extrair.add_argument("--populacao", help="varcd do indicador de população residente")
    p_extrair.add_argument("--turismo-dormidas", help="varcd do indicador de dormidas")
    p_extrair.add_argument("--turismo-hospedes", help="varcd do indicador de hóspedes")
    p_extrair.add_argument(
        "--turismo-dormidas-origem",
        help="varcd do indicador de dormidas por Local de residência (Portugal/Estrangeiro)",
    )
    p_extrair.add_argument(
        "--turismo-hospedes-origem",
        help="varcd do indicador de hóspedes por Local de residência (Portugal/Estrangeiro)",
    )

    args = parser.parse_args()

    if args.modo == "descobrir":
        descobrir()
    elif args.modo == "extrair":
        extrair(args)


if __name__ == "__main__":
    main()
