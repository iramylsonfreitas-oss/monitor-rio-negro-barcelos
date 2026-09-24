import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

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


def request_json(url, headers, attempts=3, timeout=60):
    last_error = None

    for attempt in range(1, attempts + 1):
        req = urllib.request.Request(url, headers=headers)

        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return json.loads(
                    response.read().decode("utf-8", errors="replace")
                )

        except urllib.error.HTTPError as error:
            last_error = error

            if error.code not in (429, 502, 503, 504) or attempt == attempts:
                body = error.read().decode("utf-8", errors="replace")
                raise RuntimeError(
                    f"ANA retornou HTTP {error.code}: {body[:1000]}"
                ) from error

        except urllib.error.URLError as error:
            last_error = error

            if attempt == attempts:
                raise

        time.sleep(5 * attempt)

    raise RuntimeError(f"Falha ao consultar a ANA: {last_error}")


def parse_measurement_time(value):
    return datetime.fromisoformat(value.replace(" ", "T"))


def main():
    auth = request_json(
        AUTH_URL,
        headers={
            "Identificador": ANA_IDENTIFIER,
            "Senha": ANA_PASSWORD,
            "Accept": "application/json",
            "User-Agent": "Monitor-Rio-Negro/1.0",
        },
    )

    token = (auth.get("items") or {}).get("tokenautenticacao")

    if not token:
        raise RuntimeError("Token de autenticação não encontrado.")

    query = urllib.parse.urlencode(
        {
            "Codigos_Estacoes": STATION,
            "Tipo Filtro Data": "DATA_LEITURA",
            "Range Intervalo de busca": "DIAS_30",
        }
    )

    response = request_json(
        f"{DATA_URL}?{query}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": "Monitor-Rio-Negro/1.0",
        },
    )

    items = response.get("items") or []

    if not items:
        raise RuntimeError("A ANA respondeu sem registros para Barcelos.")

    valid = [
        row
        for row in items
        if str(row.get("codigoestacao")) == STATION
        and row.get("Data_Hora_Medicao")
        and row.get("Cota_Adotada") not in (None, "")
    ]

    if not valid:
        raise RuntimeError(
            "Foram recebidos registros, mas nenhum possui cota adotada válida."
        )

    # Remove duplicidades por data/hora.
    by_time = {
        row["Data_Hora_Medicao"]: row
        for row in valid
    }

    series = sorted(
        by_time.values(),
        key=lambda row: parse_measurement_time(
            row["Data_Hora_Medicao"]
        ),
    )

    latest = series[-1]

    level_cm = float(
        str(latest["Cota_Adotada"]).replace(",", ".")
    )

    level_m = round(level_cm / 100, 2)

    output_latest = {
        "estacao": STATION,
        "nome": "Rio Negro em Barcelos",
        "nivel_cm": level_cm,
        "nivel_m": level_m,
        "data_medicao": latest["Data_Hora_Medicao"],
        "data_atualizacao_ana": latest.get(
            "Data_Atualizacao"
        ),
        "status_cota": latest.get(
            "Cota_Adotada_Status"
        ),
        "fonte": "ANA - HidroWebService",
        "coletado_em_utc": datetime.now(
            timezone.utc
        ).isoformat(),
    }

    output_series = [
        {
            "data_medicao": row["Data_Hora_Medicao"],
            "nivel_cm": float(
                str(row["Cota_Adotada"]).replace(",", ".")
            ),
            "status_cota": row.get(
                "Cota_Adotada_Status"
            ),
            "data_atualizacao_ana": row.get(
                "Data_Atualizacao"
            ),
        }
        for row in series
    ]

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

    print("Coleta concluída.")

    print(
        f"Última leitura: "
        f"{output_latest['nivel_m']:.2f} m "
        f"em {output_latest['data_medicao']}"
    )

    print(
        f"Registros na série: "
        f"{len(output_series)}"
    )


if __name__ == "__main__":
    main()
