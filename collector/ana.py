import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from datetime import datetime, timezone, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


ANA_IDENTIFIER = os.environ["ANA_IDENTIFIER"]
ANA_PASSWORD = os.environ["ANA_PASSWORD"]

AUTH_URL = (
    "https://www.ana.gov.br/hidrowebservice/"
    "EstacoesTelemetricas/OAUth/v1"
)

DATA_URL = (
    "https://www.ana.gov.br/hidrowebservice/"
    "EstacoesTelemetricas/"
    "HidroinfoanaSerieTelemetricaAdotada/v2"
)

STATION = "14480002"

# As datas retornadas pela ANA estão sendo tratadas
# como horário de Brasília.
ANA_TIMEZONE = ZoneInfo("America/Sao_Paulo")


def request_json(url, headers, attempts=3, timeout=90):
    last_error = None

    for attempt in range(1, attempts + 1):

        req = urllib.request.Request(
            url,
            headers=headers
        )

        try:

            with urllib.request.urlopen(
                req,
                timeout=timeout
            ) as response:

                return json.loads(
                    response.read().decode(
                        "utf-8",
                        errors="replace"
                    )
                )

        except urllib.error.HTTPError as error:

            last_error = error

            if (
                error.code not in
                (429, 502, 503, 504)
                or attempt == attempts
            ):

                body = error.read().decode(
                    "utf-8",
                    errors="replace"
                )

                raise RuntimeError(
                    f"ANA retornou HTTP "
                    f"{error.code}: "
                    f"{body[:1000]}"
                ) from error

        except urllib.error.URLError as error:

            last_error = error

            if attempt == attempts:
                raise

        time.sleep(5 * attempt)

    raise RuntimeError(
        f"Falha ao consultar a ANA: "
        f"{last_error}"
    )


def parse_measurement_time(value):
    return datetime.fromisoformat(
        value.replace(" ", "T")
    )


def level_cm(row):
    return float(
        str(row["Cota_Adotada"])
        .replace(",", ".")
    )


def find_nearest_previous(series, target):
    """
    Retorna a medição mais próxima do horário-alvo,
    preferindo registros anteriores ao alvo.
    """

    anteriores = [
        row
        for row in series
        if parse_measurement_time(
            row["Data_Hora_Medicao"]
        ) <= target
    ]

    if not anteriores:
        return None

    return max(
        anteriores,
        key=lambda row: parse_measurement_time(
            row["Data_Hora_Medicao"]
        )
    )


def variation(latest, reference):
    if reference is None:
        return None

    return round(
        level_cm(latest)
        - level_cm(reference),
        1
    )


def main():

    # ==============================
    # AUTENTICAÇÃO
    # ==============================

    auth = request_json(
        AUTH_URL,
        headers={
            "Identificador": ANA_IDENTIFIER,
            "Senha": ANA_PASSWORD,
            "Accept": "application/json",
            "User-Agent": "Monitor-Rio-Negro/1.0",
        },
    )

    token = (
        auth.get("items") or {}
    ).get("tokenautenticacao")

    if not token:
        raise RuntimeError(
            "Token de autenticação "
            "não encontrado."
        )

    # ==============================
    # CONSULTA DOS ÚLTIMOS 30 DIAS
    # ==============================

    query = urllib.parse.urlencode(
        {
            "Codigos_Estacoes": STATION,
            "Tipo Filtro Data":
                "DATA_LEITURA",
            "Range Intervalo de busca":
                "DIAS_30",
        }
    )

    response = request_json(
        f"{DATA_URL}?{query}",
        headers={
            "Authorization":
                f"Bearer {token}",
            "Accept":
                "application/json",
            "User-Agent":
                "Monitor-Rio-Negro/1.0",
        },
    )

    items = response.get("items") or []

    if not items:
        raise RuntimeError(
            "A ANA respondeu sem registros "
            "para Barcelos."
        )

    # ==============================
    # FILTRAGEM
    # ==============================

    valid = [
        row
        for row in items

        if str(
            row.get("codigoestacao")
        ) == STATION

        and row.get(
            "Data_Hora_Medicao"
        )

        and row.get(
            "Cota_Adotada"
        ) not in (None, "")
    ]

    if not valid:
        raise RuntimeError(
            "Nenhum registro possui "
            "cota adotada válida."
        )

    # Remove duplicidades.
    by_time = {
        row["Data_Hora_Medicao"]: row
        for row in valid
    }

    series = sorted(
        by_time.values(),
        key=lambda row:
            parse_measurement_time(
                row["Data_Hora_Medicao"]
            )
    )

    latest = series[-1]

    latest_time = parse_measurement_time(
        latest["Data_Hora_Medicao"]
    )

    current_level_cm = level_cm(latest)

    # ==============================
    # PONTOS DE REFERÊNCIA
    # ==============================

    ref_6h = find_nearest_previous(
        series,
        latest_time - timedelta(hours=6)
    )

    ref_24h = find_nearest_previous(
        series,
        latest_time - timedelta(hours=24)
    )

    ref_7d = find_nearest_previous(
        series,
        latest_time - timedelta(days=7)
    )

    var_6h = variation(
        latest,
        ref_6h
    )

    var_24h = variation(
        latest,
        ref_24h
    )

    var_7d = variation(
        latest,
        ref_7d
    )

    # ==============================
    # TENDÊNCIA
    # ==============================

    if var_6h is None:
        tendencia = "indisponivel"

    elif var_6h > 0:
        tendencia = "subindo"

    elif var_6h < 0:
        tendencia = "descendo"

    else:
        tendencia = "estavel"

    # ==============================
    # IDADE DO DADO
    # ==============================

    latest_with_timezone = (
        latest_time.replace(
            tzinfo=ANA_TIMEZONE
        )
    )

    now_utc = datetime.now(
        timezone.utc
    )

    age_minutes = int(
        (
            now_utc
            - latest_with_timezone.astimezone(
                timezone.utc
            )
        ).total_seconds() / 60
    )

    # Evita valor negativo por
    # pequenas diferenças de relógio.
    age_minutes = max(
        age_minutes,
        0
    )

    stale = age_minutes > 180

    # ==============================
    # ARQUIVO LATEST
    # ==============================

    output_latest = {

        "estacao":
            STATION,

        "nome":
            "Rio Negro em Barcelos",

        "nivel_cm":
            current_level_cm,

        "nivel_m":
            round(
                current_level_cm / 100,
                2
            ),

        "data_medicao":
            latest[
                "Data_Hora_Medicao"
            ],

        "data_atualizacao_ana":
            latest.get(
                "Data_Atualizacao"
            ),

        "status_cota":
            latest.get(
                "Cota_Adotada_Status"
            ),

        "variacao_6h_cm":
            var_6h,

        "variacao_24h_cm":
            var_24h,

        "variacao_7d_cm":
            var_7d,

        "tendencia":
            tendencia,

        "idade_dado_min":
            age_minutes,

        "dado_desatualizado":
            stale,

        "registros_30d":
            len(series),

        "fonte":
            "ANA - HidroWebService",

        "coletado_em_utc":
            datetime.now(
                timezone.utc
            ).isoformat(),
    }

    # ==============================
    # SÉRIE PARA GRÁFICO
    # ==============================

    output_series = [

        {
            "data_medicao":
                row[
                    "Data_Hora_Medicao"
                ],

            "nivel_cm":
                level_cm(row),

            "nivel_m":
                round(
                    level_cm(row) / 100,
                    2
                ),

            "status_cota":
                row.get(
                    "Cota_Adotada_Status"
                ),

            "data_atualizacao_ana":
                row.get(
                    "Data_Atualizacao"
                ),
        }

        for row in series
    ]

    # ==============================
    # GRAVAÇÃO
    # ==============================

    data_dir = Path("data")

    data_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    with (
        data_dir / "latest.json"
    ).open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            output_latest,
            file,
            ensure_ascii=False,
            indent=2,
        )

        file.write("\n")

    with (
        data_dir / "series_30d.json"
    ).open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            output_series,
            file,
            ensure_ascii=False,
            indent=2,
        )

        file.write("\n")

    # ==============================
    # LOG
    # ==============================

    print("Coleta concluída.")

    print(
        f"Nível atual: "
        f"{output_latest['nivel_m']:.2f} m"
    )

    print(
        f"Medição: "
        f"{output_latest['data_medicao']}"
    )

    print(
        f"Variação 6h: "
        f"{var_6h} cm"
    )

    print(
        f"Variação 24h: "
        f"{var_24h} cm"
    )

    print(
        f"Variação 7d: "
        f"{var_7d} cm"
    )

    print(
        f"Tendência: "
        f"{tendencia}"
    )

    print(
        f"Idade do dado: "
        f"{age_minutes} minutos"
    )

    print(
        f"Registros disponíveis: "
        f"{len(series)}"
    )


if __name__ == "__main__":
    main()
