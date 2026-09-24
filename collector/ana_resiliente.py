import time

import ana


MAX_TENTATIVAS_401 = 3

ESPERAS_SEGUNDOS = [
    15,
    30,
]


def is_unauthorized(error):

    text = str(
        error
    ).lower()

    return (
        "http 401" in text
        or "unauthorized" in text
    )


def main():

    for tentativa in range(
        1,
        MAX_TENTATIVAS_401 + 1
    ):

        print()
        print(
            "======================================"
        )

        print(
            "COLETA ANA"
        )

        print(
            "Tentativa:",
            tentativa,
            "de",
            MAX_TENTATIVAS_401
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

            if not is_unauthorized(
                error
            ):

                print()
                print(
                    "Erro não relacionado "
                    "à autenticação."
                )

                print(
                    "O erro será mantido "
                    "para diagnóstico."
                )

                raise

            print()
            print(
                "ANA retornou 401 / Unauthorized."
            )

            if (
                tentativa
                >= MAX_TENTATIVAS_401
            ):

                print()
                print(
                    "A ANA recusou a autenticação "
                    "em todas as tentativas."
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

            print(
                "Um novo token será solicitado "
                "na próxima tentativa."
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
