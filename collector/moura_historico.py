import urllib.parse

import ana


MOURA_CODE = "14840000"
MOURA_NAME = "Moura"


def main():
    auth = ana.request_json(
        ana.AUTH_URL,
        headers={
            "Identificador": ana.ANA_IDENTIFIER,
            "Senha": ana.ANA_PASSWORD,
            "Accept": "application/json",
            "User-Agent": "Monitor-Rio-Negro/1.0",
        },
    )

    token = (
        auth.get("items") or {}
    ).get(
        "tokenautenticacao"
    )

    if not token:
        raise RuntimeError(
            "Token ANA não encontrado."
        )

    query = urllib.parse.urlencode(
        {
            "Codigos_Estacoes": MOURA_CODE,
            "Tipo Filtro Data": "DATA_LEITURA",
            "Range Intervalo de busca": "DIAS_30",
        }
    )

    response = ana.request_json(
        f"{ana.DATA_URL}?{query}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": "Monitor-Rio-Negro/1.0",
        },
    )

    items = (
        response.get("items")
        or []
    )

    if not items:
        raise RuntimeError(
            "ANA retornou zero registros para Moura."
        )

    metrics, series = ana.station_metrics(
        MOURA_CODE,
        MOURA_NAME,
        items,
    )

    if metrics is None or not series:
        raise RuntimeError(
            "Série válida de Moura não encontrada."
        )

    original_stations = ana.ESTACOES

    try:
        ana.ESTACOES = {
            MOURA_CODE: MOURA_NAME
        }

        before, total = ana.update_history(
            {
                MOURA_CODE: series
            }
        )

    finally:
        ana.ESTACOES = original_stations

    print()
    print("======================================")
    print("HISTÓRICO DE MOURA - ANA 14840000")
    print("======================================")
    print()

    print(
        "Última medição:",
        metrics.get("data_medicao_manaus")
    )

    print(
        "Nível local:",
        metrics.get("nivel_m"),
        "m"
    )

    print(
        "6 h:",
        metrics.get("variacao_6h_cm"),
        "cm"
    )

    print(
        "24 h:",
        metrics.get("variacao_24h_cm"),
        "cm"
    )

    print(
        "72 h:",
        metrics.get("variacao_72h_cm"),
        "cm"
    )

    print(
        "7 dias:",
        metrics.get("variacao_7d_cm"),
        "cm"
    )

    print(
        "Idade do dado:",
        metrics.get("idade_dado_min"),
        "min"
    )

    print(
        "Registros brutos:",
        len(series)
    )

    print(
        "Histórico horário antes:",
        before
    )

    print(
        "Histórico horário depois:",
        total
    )

    print()
    print(
        "Moura foi adicionada somente ao histórico horário."
    )

    print(
        "Nenhum JSON do painel foi alterado por este coletor."
    )


if __name__ == "__main__":
    main()
