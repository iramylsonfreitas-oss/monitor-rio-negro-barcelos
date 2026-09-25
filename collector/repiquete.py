import csv
import json

from datetime import datetime, timedelta, timezone
from pathlib import Path


# ==========================================================
# ARQUIVOS
# ==========================================================

HISTORY_FILE = Path("data/history/hourly.csv")
STATIONS_FILE = Path("data/estacoes.json")
ALERT_FILE = Path("data/alerta.json")
OUTPUT_FILE = Path("data/repiquete.json")


# ==========================================================
# ESTAÇÕES
# ==========================================================

TARACUA = "14280001"
CURICURIARI = "14330000"
SERRINHA = "14420000"
BARCELOS = "14480002"


# ==========================================================
# CRITÉRIOS
# ==========================================================

# Para dizer que Barcelos vinha de uma vazante relevante.
PREVIOUS_DROP_7D_CM = -10.0

# Alternativa para detectar queda recente mesmo quando
# o acumulado de 7 dias já estiver começando a se recuperar.
PREVIOUS_DROP_72H_CM = -3.0

# Alta mínima de 24 horas para confirmação do repiquete.
CONFIRMED_RISE_24H_CM = 3.0

# Pontos consecutivos necessários.
CONFIRMATION_POINTS = 3

# Espaçamento dos pontos.
SAMPLE_INTERVAL_HOURS = 6

# Além das três confirmações de +3 cm/24 h, o nível no
# terceiro checkpoint precisa estar pelo menos 1 cm acima
# do nível no primeiro checkpoint do sinal.
MIN_NET_GAIN_CONFIRMATION_CM = 1.0

# Critério para considerar o evento encerrado.
RESET_RISE_24H_CM = 1.0

# Número de pontos fracos necessários para encerrar.
END_CONFIRMATION_POINTS = 4


# ==========================================================
# FUNÇÕES BÁSICAS
# ==========================================================

def number(value):

    if value is None:
        return None

    try:
        return float(value)

    except (
        TypeError,
        ValueError
    ):
        return None


def parse_datetime(value):

    return datetime.strptime(
        value,
        "%Y-%m-%d %H:%M:%S"
    )


def format_datetime(value):

    if value is None:
        return None

    return value.strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def load_json(path):

    if not path.exists():
        return {}

    with path.open(
        "r",
        encoding="utf-8"
    ) as file:

        return json.load(file)


# ==========================================================
# ESTAÇÕES ATUAIS
# ==========================================================

def load_stations():

    data = load_json(
        STATIONS_FILE
    )

    return {
        station["estacao"]: station

        for station
        in data.get(
            "estacoes",
            []
        )
    }


def station_snapshot(station):

    if not station:
        return None

    return {
        "nome":
            station.get(
                "nome"
            ),

        "nivel_m":
            station.get(
                "nivel_m"
            ),

        "variacao_6h_cm":
            station.get(
                "variacao_6h_cm"
            ),

        "variacao_24h_cm":
            station.get(
                "variacao_24h_cm"
            ),

        "variacao_72h_cm":
            station.get(
                "variacao_72h_cm"
            ),

        "variacao_7d_cm":
            station.get(
                "variacao_7d_cm"
            ),

        "tendencia":
            station.get(
                "tendencia"
            ),

        "data_medicao_manaus":
            station.get(
                "data_medicao_manaus"
            ),
    }


# ==========================================================
# HISTÓRICO DE BARCELOS
# ==========================================================

def load_barcelos_history():

    if not HISTORY_FILE.exists():

        raise RuntimeError(
            "data/history/hourly.csv "
            "não encontrado."
        )

    series = {}

    with HISTORY_FILE.open(
        "r",
        encoding="utf-8",
        newline=""
    ) as file:

        reader = csv.DictReader(
            file
        )

        for row in reader:

            if (
                row.get(
                    "estacao"
                )
                != BARCELOS
            ):

                continue

            timestamp_text = (
                row.get(
                    "hora_manaus"
                )
            )

            level_text = (
                row.get(
                    "nivel_cm"
                )
            )

            if (
                not timestamp_text
                or level_text in (
                    None,
                    ""
                )
            ):

                continue

            try:

                timestamp = (
                    parse_datetime(
                        timestamp_text
                    )
                )

                level = float(
                    level_text
                )

            except (
                ValueError,
                TypeError
            ):

                continue

            series[
                timestamp
            ] = level

    if not series:

        raise RuntimeError(
            "Histórico de Barcelos vazio."
        )

    return series


# ==========================================================
# VARIAÇÕES HISTÓRICAS
# ==========================================================

def change_at(
    series,
    timestamp,
    hours
):

    current = series.get(
        timestamp
    )

    previous = series.get(
        timestamp
        - timedelta(
            hours=hours
        )
    )

    if (
        current is None
        or previous is None
    ):

        return None

    return (
        current
        - previous
    )


def build_checkpoints(series):

    checkpoints = []

    for timestamp in sorted(
        series.keys()
    ):

        if (
            timestamp.minute != 0
            or timestamp.second != 0
        ):

            continue

        if (
            timestamp.hour
            % SAMPLE_INTERVAL_HOURS
            != 0
        ):

            continue

        checkpoints.append(
            {
                "timestamp":
                    timestamp,

                "nivel_cm":
                    series[
                        timestamp
                    ],

                "variacao_6h_cm":
                    change_at(
                        series,
                        timestamp,
                        6
                    ),

                "variacao_24h_cm":
                    change_at(
                        series,
                        timestamp,
                        24
                    ),

                "variacao_72h_cm":
                    change_at(
                        series,
                        timestamp,
                        72
                    ),

                "variacao_7d_cm":
                    change_at(
                        series,
                        timestamp,
                        168
                    ),
            }
        )

    return checkpoints


# ==========================================================
# CONTEXTO DE QUEDA
# ==========================================================

def had_previous_drop(record):

    variation_7d = number(
        record.get(
            "variacao_7d_cm"
        )
    )

    variation_72h = number(
        record.get(
            "variacao_72h_cm"
        )
    )

    condition_7d = (
        variation_7d is not None
        and variation_7d
        <= PREVIOUS_DROP_7D_CM
    )

    condition_72h = (
        variation_72h is not None
        and variation_72h
        <= PREVIOUS_DROP_72H_CM
    )

    return (
        condition_7d
        or condition_72h
    )


# ==========================================================
# REPIQUETE CONFIRMADO NO HISTÓRICO HORÁRIO
# ==========================================================

def detect_current_confirmed_event(
    checkpoints
):

    by_time = {
        record[
            "timestamp"
        ]: record

        for record
        in checkpoints
    }

    active = False

    current_event = None

    end_counter = 0

    for record in checkpoints:

        timestamp = record[
            "timestamp"
        ]

        rise_24h = number(
            record.get(
                "variacao_24h_cm"
            )
        )

        if rise_24h is None:

            continue

        # ==================================================
        # FORA DE EVENTO
        # ==================================================

        if not active:

            if (
                rise_24h
                < CONFIRMED_RISE_24H_CM
            ):

                continue

            if not had_previous_drop(
                record
            ):

                continue

            confirmation_records = []

            valid = True

            for offset in range(
                CONFIRMATION_POINTS
            ):

                expected_time = (
                    timestamp
                    + timedelta(
                        hours=(
                            SAMPLE_INTERVAL_HOURS
                            * offset
                        )
                    )
                )

                expected = (
                    by_time.get(
                        expected_time
                    )
                )

                if not expected:

                    valid = False
                    break

                expected_rise = number(
                    expected.get(
                        "variacao_24h_cm"
                    )
                )

                if (
                    expected_rise is None
                    or expected_rise
                    < CONFIRMED_RISE_24H_CM
                ):

                    valid = False
                    break

                confirmation_records.append(
                    expected
                )

            if not valid:

                continue

            signal_level = number(
                record.get(
                    "nivel_cm"
                )
            )

            confirmation_record = (
                confirmation_records[
                    -1
                ]
            )

            confirmation_level = number(
                confirmation_record.get(
                    "nivel_cm"
                )
            )

            if (
                signal_level is None
                or confirmation_level is None
            ):

                continue

            net_gain = (
                confirmation_level
                - signal_level
            )

            # A janela móvel de 24 h não basta sozinha.
            # Barcelos precisa ter avançado de fato
            # entre o primeiro e o terceiro checkpoint.
            if (
                net_gain
                < MIN_NET_GAIN_CONFIRMATION_CM
            ):

                continue

            active = True

            end_counter = 0

            current_event = {
                "inicio":
                    timestamp,

                "confirmado_em":
                    confirmation_record[
                        "timestamp"
                    ],

                "nivel_inicio_cm":
                    signal_level,

                "nivel_confirmacao_cm":
                    confirmation_level,

                "ganho_liquido_confirmacao_cm":
                    net_gain,

                "queda_72h_inicio_cm":
                    record.get(
                        "variacao_72h_cm"
                    ),

                "queda_7d_inicio_cm":
                    record.get(
                        "variacao_7d_cm"
                    ),

                "variacao_maxima_24h_cm":
                    max(
                        number(
                            item.get(
                                "variacao_24h_cm"
                            )
                        )

                        for item
                        in confirmation_records
                    ),

                "confirmacoes_inicio":
                    [
                        {
                            "hora_manaus":
                                format_datetime(
                                    item[
                                        "timestamp"
                                    ]
                                ),

                            "nivel_m":
                                round(
                                    number(
                                        item.get(
                                            "nivel_cm"
                                        )
                                    )
                                    / 100,
                                    2
                                ),

                            "variacao_24h_cm":
                                round(
                                    number(
                                        item.get(
                                            "variacao_24h_cm"
                                        )
                                    ),
                                    1
                                ),
                        }

                        for item
                        in confirmation_records
                    ],
            }

        # ==================================================
        # EVENTO ATIVO
        # ==================================================

        else:

            current_event[
                "variacao_maxima_24h_cm"
            ] = max(
                current_event[
                    "variacao_maxima_24h_cm"
                ],
                rise_24h
            )

            if (
                rise_24h
                <= RESET_RISE_24H_CM
            ):

                end_counter += 1

            else:

                end_counter = 0

            if (
                end_counter
                >= END_CONFIRMATION_POINTS
            ):

                active = False

                current_event = None

                end_counter = 0

    return (
        active,
        current_event
    )


# ==========================================================
# ÚLTIMOS CHECKPOINTS
# ==========================================================

def latest_checkpoints(
    checkpoints,
    quantity=8
):

    selected = (
        checkpoints[
            -quantity:
        ]
    )

    output = []

    for record in selected:

        item = {
            "hora_manaus":
                format_datetime(
                    record[
                        "timestamp"
                    ]
                ),

            "nivel_m":
                round(
                    record[
                        "nivel_cm"
                    ] / 100,
                    2
                ),
        }

        for field in (
            "variacao_6h_cm",
            "variacao_24h_cm",
            "variacao_72h_cm",
            "variacao_7d_cm"
        ):

            value = number(
                record.get(
                    field
                )
            )

            item[
                field
            ] = (
                round(
                    value,
                    1
                )
                if value is not None
                else None
            )

        output.append(
            item
        )

    return output


# ==========================================================
# CONTEXTO A MONTANTE
# ==========================================================

def build_upstream_context(
    stations,
    alert_data
):

    taracua = stations.get(
        TARACUA,
        {}
    )

    curicuriari = stations.get(
        CURICURIARI,
        {}
    )

    serrinha = stations.get(
        SERRINHA,
        {}
    )

    t72 = number(
        taracua.get(
            "variacao_72h_cm"
        )
    )

    c72 = number(
        curicuriari.get(
            "variacao_72h_cm"
        )
    )

    s72 = number(
        serrinha.get(
            "variacao_72h_cm"
        )
    )

    positive_72h = sum(
        1

        for value
        in (
            t72,
            c72,
            s72
        )

        if (
            value is not None
            and value > 0
        )
    )

    alert_level = number(
        alert_data.get(
            "nivel"
        )
    )

    serrinha_event = (
        alert_data.get(
            "evento_serrinha",
            {}
        ).get(
            "confirmado",
            False
        )
    )

    signal = (
        serrinha_event
        or (
            alert_level is not None
            and alert_level >= 1
        )
        or positive_72h >= 2
    )

    reasons = []

    if (
        s72 is not None
        and s72 > 0
    ):

        reasons.append(
            (
                "Serrinha acumula "
                f"{s72:+.1f} cm em 72 h."
            )
        )

    if (
        c72 is not None
        and c72 > 0
    ):

        reasons.append(
            (
                "Curicuriari acumula "
                f"{c72:+.1f} cm em 72 h."
            )
        )

    if (
        t72 is not None
        and t72 > 0
    ):

        reasons.append(
            (
                "Taracuá acumula "
                f"{t72:+.1f} cm em 72 h."
            )
        )

    if serrinha_event:

        reasons.append(
            (
                "O detector principal registra "
                "alta sustentada em Serrinha."
            )
        )

    return {
        "sinal":
            signal,

        "estacoes_positivas_72h":
            positive_72h,

        "evento_serrinha_confirmado":
            bool(
                serrinha_event
            ),

        "nivel_alerta_existente":
            (
                int(
                    alert_level
                )
                if alert_level is not None
                else None
            ),

        "motivos":
            reasons,
    }


# ==========================================================
# CLASSIFICAÇÃO DO DETECTOR
# ==========================================================

def classify(
    stations,
    upstream,
    event_active,
    event
):

    barcelos = stations.get(
        BARCELOS,
        {}
    )

    b6 = number(
        barcelos.get(
            "variacao_6h_cm"
        )
    )

    b24 = number(
        barcelos.get(
            "variacao_24h_cm"
        )
    )

    b72 = number(
        barcelos.get(
            "variacao_72h_cm"
        )
    )

    b7d = number(
        barcelos.get(
            "variacao_7d_cm"
        )
    )

    previous_drop = (
        (
            b7d is not None
            and b7d
            <= PREVIOUS_DROP_7D_CM
        )
        or (
            b72 is not None
            and b72
            <= PREVIOUS_DROP_72H_CM
        )
    )

    reasons = []

    if (
        b7d is not None
        and b7d < 0
    ):

        reasons.append(
            (
                "Barcelos ainda acumula "
                f"{b7d:+.1f} cm em 7 dias."
            )
        )

    if (
        b72 is not None
        and b72 < 0
    ):

        reasons.append(
            (
                "Barcelos ainda acumula "
                f"{b72:+.1f} cm em 72 h."
            )
        )

    if (
        b6 is not None
        and b6 > 0
    ):

        reasons.append(
            (
                "Nas últimas 6 h Barcelos "
                f"subiu {b6:+.1f} cm."
            )
        )

    if (
        b24 is not None
        and b24 > 0
    ):

        reasons.append(
            (
                "Barcelos já apresenta "
                f"{b24:+.1f} cm em 24 h."
            )
        )

    reasons.extend(
        upstream.get(
            "motivos",
            []
        )
    )

    # ======================================================
    # NÍVEL 4 — CONFIRMADO
    # ======================================================

    if event_active:

        net_gain = number(
            event.get(
                "ganho_liquido_confirmacao_cm"
            )
        )

        if net_gain is not None:

            reasons.append(
                (
                    "Entre o primeiro e o terceiro "
                    "checkpoint do sinal, Barcelos "
                    f"avançou {net_gain:+.1f} cm."
                )
            )

        return {
            "nivel":
                4,

            "status":
                "repiquete_confirmado",

            "rotulo":
                "REPIQUETE CONFIRMADO",

            "titulo":
                (
                    "Reversão de alta confirmada "
                    "em Barcelos"
                ),

            "mensagem":
                (
                    "Após um período de queda, "
                    "Barcelos atingiu os critérios "
                    "do detector: pelo menos +3 cm "
                    "em 24 h em três verificações "
                    "consecutivas separadas por "
                    "6 horas e ganho líquido mínimo "
                    "de +1 cm entre a primeira e a "
                    "terceira verificação."
                ),

            "motivos":
                reasons,
        }

    # ======================================================
    # NÍVEL 3 — EM FORMAÇÃO
    # ======================================================

    formation = (
        previous_drop
        and b24 is not None
        and b24 > 0
        and b6 is not None
        and b6 >= 0
    )

    if formation:

        return {
            "nivel":
                3,

            "status":
                "repiquete_em_formacao",

            "rotulo":
                "REPIQUETE EM FORMAÇÃO",

            "titulo":
                (
                    "Barcelos já apresenta "
                    "variação positiva em 24 h"
                ),

            "mensagem":
                (
                    "O rio vinha em queda e "
                    "passou a apresentar alta "
                    "em 24 horas. Ainda não há "
                    "evidência suficiente para "
                    "classificar o movimento como "
                    "repiquete confirmado."
                ),

            "motivos":
                reasons,
        }

    # ======================================================
    # NÍVEL 2 — POSSÍVEL REVERSÃO
    # ======================================================

    possible_reversal = (
        previous_drop
        and b6 is not None
        and b6 > 0
        and b24 is not None
        and b24 <= 0
    )

    if possible_reversal:

        return {
            "nivel":
                2,

            "status":
                "possivel_reversao",

            "rotulo":
                "POSSÍVEL REVERSÃO",

            "titulo":
                (
                    "A queda de Barcelos "
                    "perdeu força"
                ),

            "mensagem":
                (
                    "Barcelos ainda não acumula "
                    "alta em 24 horas, mas a "
                    "variação das últimas 6 horas "
                    "já ficou positiva após um "
                    "período de vazante. O movimento "
                    "precisa persistir antes de ser "
                    "tratado como repiquete."
                ),

            "motivos":
                reasons,
        }

    # ======================================================
    # NÍVEL 1 — SOMENTE A MONTANTE
    # ======================================================

    upstream_signal = (
        previous_drop
        and upstream.get(
            "sinal",
            False
        )
    )

    if upstream_signal:

        return {
            "nivel":
                1,

            "status":
                "sinal_montante",

            "rotulo":
                "SINAL A MONTANTE",

            "titulo":
                (
                    "Movimento a montante "
                    "em acompanhamento"
                ),

            "mensagem":
                (
                    "Há sinais positivos em "
                    "estações acima de Barcelos, "
                    "enquanto Barcelos ainda está "
                    "em contexto de queda. Isso "
                    "não confirma uma reversão local."
                ),

            "motivos":
                reasons,
        }

    # ======================================================
    # NÍVEL 0
    # ======================================================

    return {
        "nivel":
            0,

        "status":
            "sem_sinal_reversao",

        "rotulo":
            "SEM SINAL DE REPIQUETE",

        "titulo":
            (
                "Sem reversão confirmada "
                "em Barcelos"
            ),

        "mensagem":
            (
                "Os critérios atuais não "
                "identificam uma reversão "
                "consistente da tendência "
                "em Barcelos."
            ),

        "motivos":
            reasons,
    }


# ==========================================================
# EXECUÇÃO
# ==========================================================

def main():

    stations = load_stations()

    if BARCELOS not in stations:

        raise RuntimeError(
            "Estação de Barcelos "
            "não encontrada."
        )

    alert_data = load_json(
        ALERT_FILE
    )

    history = (
        load_barcelos_history()
    )

    checkpoints = (
        build_checkpoints(
            history
        )
    )

    event_active, event = (
        detect_current_confirmed_event(
            checkpoints
        )
    )

    upstream = (
        build_upstream_context(
            stations,
            alert_data
        )
    )

    classification = (
        classify(
            stations,
            upstream,
            event_active,
            event
        )
    )

    output = {
        "gerado_em_utc":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "timezone":
            "America/Manaus",

        "nivel":
            classification[
                "nivel"
            ],

        "status":
            classification[
                "status"
            ],

        "rotulo":
            classification[
                "rotulo"
            ],

        "titulo":
            classification[
                "titulo"
            ],

        "mensagem":
            classification[
                "mensagem"
            ],

        "motivos":
            classification[
                "motivos"
            ],

        "criterios": {
            "queda_previa_7d_cm":
                PREVIOUS_DROP_7D_CM,

            "queda_previa_72h_cm":
                PREVIOUS_DROP_72H_CM,

            "alta_confirmacao_24h_cm":
                CONFIRMED_RISE_24H_CM,

            "confirmacoes":
                CONFIRMATION_POINTS,

            "intervalo_confirmacoes_h":
                SAMPLE_INTERVAL_HOURS,

            "ganho_liquido_minimo_confirmacao_cm":
                MIN_NET_GAIN_CONFIRMATION_CM,

            "criterio_encerramento_24h_cm":
                RESET_RISE_24H_CM,

            "confirmacoes_encerramento":
                END_CONFIRMATION_POINTS,
        },

        "evento_barcelos": {
            "confirmado":
                event_active,

            "inicio_manaus":
                (
                    format_datetime(
                        event[
                            "inicio"
                        ]
                    )
                    if event_active
                    else None
                ),

            "confirmado_em_manaus":
                (
                    format_datetime(
                        event.get(
                            "confirmado_em"
                        )
                    )
                    if event_active
                    else None
                ),

            "nivel_inicio_m":
                (
                    round(
                        event[
                            "nivel_inicio_cm"
                        ] / 100,
                        2
                    )
                    if event_active
                    else None
                ),

            "nivel_confirmacao_m":
                (
                    round(
                        event[
                            "nivel_confirmacao_cm"
                        ] / 100,
                        2
                    )
                    if event_active
                    else None
                ),

            "ganho_liquido_confirmacao_cm":
                (
                    round(
                        event[
                            "ganho_liquido_confirmacao_cm"
                        ],
                        1
                    )
                    if event_active
                    else None
                ),

            "queda_72h_inicio_cm":
                (
                    round(
                        number(
                            event.get(
                                "queda_72h_inicio_cm"
                            )
                        ),
                        1
                    )
                    if (
                        event_active
                        and number(
                            event.get(
                                "queda_72h_inicio_cm"
                            )
                        ) is not None
                    )
                    else None
                ),

            "queda_7d_inicio_cm":
                (
                    round(
                        number(
                            event.get(
                                "queda_7d_inicio_cm"
                            )
                        ),
                        1
                    )
                    if (
                        event_active
                        and number(
                            event.get(
                                "queda_7d_inicio_cm"
                            )
                        ) is not None
                    )
                    else None
                ),

            "variacao_maxima_24h_cm":
                (
                    round(
                        event[
                            "variacao_maxima_24h_cm"
                        ],
                        1
                    )
                    if event_active
                    else None
                ),

            "confirmacoes_inicio":
                (
                    event.get(
                        "confirmacoes_inicio",
                        []
                    )
                    if event_active
                    else []
                ),
        },

        "ultimos_checkpoints_barcelos":
            latest_checkpoints(
                checkpoints
            ),

        "contexto_montante":
            upstream,

        "situacao_atual": {
            "taracua":
                station_snapshot(
                    stations.get(
                        TARACUA
                    )
                ),

            "curicuriari":
                station_snapshot(
                    stations.get(
                        CURICURIARI
                    )
                ),

            "serrinha":
                station_snapshot(
                    stations.get(
                        SERRINHA
                    )
                ),

            "barcelos":
                station_snapshot(
                    stations.get(
                        BARCELOS
                    )
                ),
        },

        "aviso":
            (
                "Detector experimental de mudança "
                "de tendência. 'Possível reversão' "
                "e 'repiquete em formação' não são "
                "confirmações. O estado confirmado "
                "exige três verificações consecutivas "
                "de alta mínima de +3 cm em 24 h e "
                "ganho líquido mínimo de +1 cm entre "
                "o primeiro e o terceiro checkpoint. "
                "O estado confirmado descreve um "
                "movimento já observado, não uma "
                "previsão."
            ),
    }

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            output,
            file,
            ensure_ascii=False,
            indent=2
        )

        file.write(
            "\n"
        )

    print(
        "Detector de repiquete:"
    )

    print(
        (
            f"nível={output['nivel']} | "
            f"{output['rotulo']}"
        )
    )

    print(
        (
            "Arquivo gerado: "
            f"{OUTPUT_FILE}"
        )
    )


if __name__ == "__main__":
    main()
