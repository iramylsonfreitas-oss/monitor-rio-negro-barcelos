from datetime import datetime

import backfill_3anos as base


MOURA_CODE = "14840000"
MOURA_NAME = "Moura"


def main():
    # Reutiliza o backfill já validado no projeto,
    # mas restringe a consulta exclusivamente a Moura.
    base.ESTACOES = {
        MOURA_CODE: MOURA_NAME
    }

    print()
    print("====================================")
    print("BACKFILL MOURA - 3 ANOS")
    print("====================================")
    print()
    print(
        "Estação:",
        MOURA_CODE,
        "-",
        MOURA_NAME
    )
    print(
        "Início alvo:",
        base.TARGET_START
    )
    print(
        "Fim:",
        datetime.now(
            base.MANAUS_TIMEZONE
        ).date()
    )
    print()
    print(
        "Somente data/history/hourly.csv "
        "será atualizado."
    )
    print(
        "Nenhum JSON do painel será alterado."
    )
    print()

    base.main()


if __name__ == "__main__":
    main()
