import time

import ana


# ==========================================================
# CONFIGURAÇÃO DE RETENTATIVAS
# ==========================================================

MAX_TENTATIVAS = 3

ESPERAS_SEGUNDOS = [
    20,
    40,
]


# ==========================================================
# IDENTIFICA ERROS TRANSITÓRIOS
# ==========================================================

def erro_transitorio(error):

    text = str(
        error
    ).lower()

    sinais_transitorios = [

        # ----------------------------------------------
        # Respostas HTTP temporárias
        # ----------------------------------------------

        "http 401",
        "unauthorized",
        "http 429",
        "http 502",
        "http 503",
        "http 504",

        # ----------------------------------------------
        # Timeout
        # ----------------------------------------------

        "timed out",
        "timeout",

        # ----------------------------------------------
        # Serviço temporariamente indisponível
        # ----------------------------------------------

        "temporarily unavailable",
        "service unavailable",

        # ----------------------------------------------
        # Falhas de conexão
        # ----------------------------------------------

        "connection reset",
        "remote end closed connection",
        "connection refused",

        # ----------------------------------------------
        # Falhas de rede
        # ----------------------------------------------

        "network is unreachable",
        "[errno 101]",
        "no route to host",

        # ----------------------------------------------
        # Falhas temporárias de DNS
        # ----------------------------------------------

        "temporary failure in name resolution",
        "name or service not known",
    ]

    return any(
        sinal in text
        for sinal in sinais_transitorios
    )


# ==========================================================
# EXECUÇÃO RESILIENTE
# ==========================================================

def main():

    for tentativa in range(
        1,
        MAX_TENTATIVAS + 1
    ):

        print()
        print(
            "======================================"
        )

        print(
            "COLETA ANA RESILIENTE"
        )

        print(
            "Tentativa:",
            tentativa,
            "de",
            MAX_TENTATIVAS
        )

        print(
            "======================================"
        )

        print()

        try:

            ana.main()

            print()
            print(
                "======================================"
            )

            print(
                "COLETA CONCLUÍDA COM SUCESSO"
            )

            print(
                "======================================"
            )

            return

        except Exception as error:

            if not erro_transitorio(
                error
            ):

                print()

                print(
                    "Erro não considerado "
                    "transitório."
                )

                print(
                    "A execução será interrompida "
                    "para diagnóstico."
                )

                print()

                print(
                    "Erro detectado:"
                )

                print(
                    str(error)[:500]
                )

                raise

            print()

            print(
                "Falha temporária na consulta "
                "à ANA."
            )

            print(
                "Erro detectado:"
            )

            print(
                str(error)[:500]
            )

            if (
                tentativa
                >= MAX_TENTATIVAS
            ):

                print()

                print(
                    "Todas as tentativas "
                    "foram utilizadas."
                )

                print(
                    "O workflow será marcado "
                    "como falha."
                )

                raise

            espera = (
                ESPERAS_SEGUNDOS[
                    tentativa - 1
                ]
            )

            print()

            print(
                "O processo inteiro será "
                "repetido."
            )

            print(
                "Isso inclui uma nova "
                "autenticação na ANA."
            )

            print(
                "Aguardando",
                espera,
                "segundos..."
            )

            time.sleep(
                espera
            )


if __name__ == "__main__":
    main()
