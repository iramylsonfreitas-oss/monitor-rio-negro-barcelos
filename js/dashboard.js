const LATEST_URL = "data/latest.json";
const SERIES_URL = "data/series_30d.json";
const STATIONS_URL = "data/estacoes.json";
const ALERT_URL = "data/alerta.json";
const ANNUAL_URL = "data/barcelos_anual.json";

let riverChart = null;
let annualChart = null;
let latestData = null;


function formatLevel(value) {
  if (
    value === null ||
    value === undefined ||
    Number.isNaN(Number(value))
  ) {
    return "—";
  }

  return Number(value)
    .toFixed(2)
    .replace(".", ",");
}


function formatNumber(
  value,
  decimals = 2
) {
  if (
    value === null ||
    value === undefined ||
    Number.isNaN(Number(value))
  ) {
    return "—";
  }

  return Number(value)
    .toFixed(decimals)
    .replace(".", ",");
}


function formatVariation(value) {
  if (
    value === null ||
    value === undefined ||
    Number.isNaN(Number(value))
  ) {
    return "—";
  }

  const n = Number(value);

  const abs =
    Number.isInteger(n)
      ? Math.abs(n).toFixed(0)
      : Math.abs(n).toFixed(1);

  if (n > 0) {
    return `+${abs} cm`;
  }

  if (n < 0) {
    return `-${abs} cm`;
  }

  return "0 cm";
}


function variationClass(value) {
  const n = Number(value);

  if (
    !Number.isFinite(n) ||
    n === 0
  ) {
    return "neutral";
  }

  return n > 0
    ? "positive"
    : "negative";
}


function formatDateTime(value) {
  if (!value) {
    return "—";
  }

  const [
    datePart,
    timePart = ""
  ] = String(value).split(" ");

  const p =
    datePart.split("-");

  if (p.length !== 3) {
    return String(value);
  }

  return (
    `${p[2]}/${p[1]}/${p[0]} ` +
    `${timePart.slice(0, 5)}`
  ).trim();
}


function formatShortDateTime(value) {
  if (!value) {
    return "—";
  }

  const [
    datePart,
    timePart = ""
  ] = String(value).split(" ");

  const p =
    datePart.split("-");

  if (p.length !== 3) {
    return String(value);
  }

  return (
    `${p[2]}/${p[1]} ` +
    `${timePart.slice(0, 5)}`
  ).trim();
}


function formatAnaUpdate(value) {
  if (!value) {
    return "—";
  }

  const [
    datePart,
    timePart = ""
  ] = String(value).split(" ");

  const p =
    datePart.split("-");

  if (p.length !== 3) {
    return String(value);
  }

  return (
    `${p[2]}/${p[1]} às ` +
    `${timePart.slice(0, 5)}`
  );
}


function formatChartLabel(value) {
  if (!value) {
    return "";
  }

  const [
    datePart,
    timePart = ""
  ] = String(value).split(" ");

  const p =
    datePart.split("-");

  if (p.length !== 3) {
    return String(value);
  }

  return (
    `${p[2]}/${p[1]} ` +
    `${timePart.slice(0, 5)}`
  );
}


function formatUtcToManaus(value) {
  if (!value) {
    return "—";
  }

  const normalized =
    String(value).replace(
      /(\.\d{3})\d+(?=[+-]\d{2}:\d{2}$|Z$)/,
      "$1"
    );

  const date =
    new Date(normalized);

  if (
    Number.isNaN(
      date.getTime()
    )
  ) {
    return String(value);
  }

  return new Intl.DateTimeFormat(
    "pt-BR",
    {
      timeZone:
        "America/Manaus",

      day:
        "2-digit",

      month:
        "2-digit",

      year:
        "numeric",

      hour:
        "2-digit",

      minute:
        "2-digit",

      hour12:
        false
    }
  ).format(date);
}


function parseManausDateTime(value) {
  if (!value) {
    return null;
  }

  let text =
    String(value)
      .trim()
      .replace(
        " ",
        "T"
      );

  text =
    text.replace(
      /\.\d+$/,
      ""
    );

  const hasZone =
    /(?:Z|[+-]\d{2}:\d{2})$/i
      .test(text);

  const date =
    new Date(
      hasZone
        ? text
        : `${text}-04:00`
    );

  return Number.isNaN(
    date.getTime()
  )
    ? null
    : date;
}


function trendInfo(trend) {
  if (
    trend === "subindo"
  ) {
    return {
      icon: "↑",
      label: "Subindo",
      css: "up"
    };
  }

  if (
    trend === "descendo"
  ) {
    return {
      icon: "↓",
      label: "Descendo",
      css: "down"
    };
  }

  if (
    trend === "estavel"
  ) {
    return {
      icon: "→",
      label: "Estável",
      css: "stable"
    };
  }

  return {
    icon: "—",
    label: "Indisponível",
    css: "stable"
  };
}


function getCurrentAgeMinutes() {
  if (!latestData) {
    return null;
  }

  const measurement =
    parseManausDateTime(
      latestData
        .data_medicao_manaus
    );

  if (measurement) {
    return Math.max(
      0,
      Math.floor(
        (
          Date.now() -
          measurement.getTime()
        ) / 60000
      )
    );
  }

  const fallback =
    Number(
      latestData
        .idade_dado_min
    );

  return Number.isFinite(
    fallback
  )
    ? Math.max(
        0,
        Math.floor(fallback)
      )
    : null;
}


function ageText(minutes) {
  if (
    minutes === null ||
    minutes === undefined
  ) {
    return "Horário indisponível";
  }

  const value =
    Math.max(
      0,
      Math.floor(
        Number(minutes)
      )
    );

  if (value < 60) {
    return (
      `Atualizado há ` +
      `${value} min`
    );
  }

  const hours =
    Math.floor(
      value / 60
    );

  const mins =
    value % 60;

  if (hours < 24) {
    return mins
      ? (
          `Atualizado há ` +
          `${hours} h ` +
          `${mins} min`
        )
      : (
          `Atualizado há ` +
          `${hours} h`
        );
  }

  const days =
    Math.floor(
      hours / 24
    );

  return (
    `Atualizado há ` +
    `${days} dia(s)`
  );
}


function updateLiveStatus() {
  if (!latestData) {
    return;
  }

  const dot =
    document.getElementById(
      "status-dot"
    );

  const text =
    document.getElementById(
      "status-text"
    );

  const time =
    document.getElementById(
      "last-update"
    );

  if (
    !dot ||
    !text ||
    !time
  ) {
    return;
  }

  const age =
    getCurrentAgeMinutes();

  const stale =
    age !== null &&
    age > 180;

  dot.classList.remove(
    "ok",
    "warning"
  );

  dot.classList.add(
    stale
      ? "warning"
      : "ok"
  );

  text.textContent =
    stale
      ? "Dado desatualizado"
      : "Dados atualizados";

  time.textContent =
    ageText(age);
}


function updateTrend(data) {
  const icon =
    document.getElementById(
      "trend-icon"
    );

  const text =
    document.getElementById(
      "trend-text"
    );

  if (
    !icon ||
    !text
  ) {
    return;
  }

  const info =
    trendInfo(
      data.tendencia
    );

  icon.classList.remove(
    "up",
    "down"
  );

  if (
    info.css === "up"
  ) {
    icon.classList.add(
      "up"
    );
  }

  if (
    info.css === "down"
  ) {
    icon.classList.add(
      "down"
    );
  }

  icon.textContent =
    info.icon;

  text.textContent =
    info.label;
}


function updateDashboard(data) {
  const level =
    document.getElementById(
      "level"
    );

  const measurement =
    document.getElementById(
      "measurement-time"
    );

  const anaUpdate =
    document.getElementById(
      "ana-update-time"
    );

  const collector =
    document.getElementById(
      "collector-update-time"
    );

  if (level) {
    level.textContent =
      formatLevel(
        data.nivel_m
      );
  }

  if (measurement) {
    measurement.textContent =
      (
        "Última medição ANA: " +
        formatDateTime(
          data
            .data_medicao_manaus ||
          data
            .data_medicao
        )
      );
  }

  if (anaUpdate) {
    anaUpdate.textContent =
      (
        "ANA atualizou o registro: " +
        formatAnaUpdate(
          data
            .data_atualizacao_manaus ||
          data
            .data_atualizacao_ana
        )
      );
  }

  if (collector) {
    collector.textContent =
      (
        "Nosso sistema consultou a ANA: " +
        formatUtcToManaus(
          data.coletado_em_utc
        )
      );
  }

  const metrics = [
    [
      "variation-6h",
      data.variacao_6h_cm
    ],
    [
      "variation-24h",
      data.variacao_24h_cm
    ],
    [
      "variation-7d",
      data.variacao_7d_cm
    ]
  ];

  metrics.forEach(
    ([id, value]) => {
      const el =
        document.getElementById(
          id
        );

      if (!el) {
        return;
      }

      el.textContent =
        formatVariation(value);

      el.className =
        (
          "metric-value " +
          variationClass(value)
        );
    }
  );

  const records =
    document.getElementById(
      "records-count"
    );

  if (records) {
    records.textContent =
      data.registros_30d ??
      "—";
  }

  updateTrend(data);
  updateLiveStatus();
}


function renderAlert(data) {
  const card =
    document.getElementById(
      "alert-card"
    );

  const badge =
    document.getElementById(
      "alert-badge"
    );

  const icon =
    document.getElementById(
      "alert-icon"
    );

  const title =
    document.getElementById(
      "alert-title"
    );

  const message =
    document.getElementById(
      "alert-message"
    );

  const reasons =
    document.getElementById(
      "alert-reasons"
    );

  const eventStatus =
    document.getElementById(
      "alert-event-status"
    );

  const eventDetail =
    document.getElementById(
      "alert-event-detail"
    );

  const windowValue =
    document.getElementById(
      "alert-window"
    );

  const windowDetail =
    document.getElementById(
      "alert-window-detail"
    );

  const historyValue =
    document.getElementById(
      "alert-history"
    );

  const historyDetail =
    document.getElementById(
      "alert-history-detail"
    );

  if (!card) {
    return;
  }

  const level =
    Number(
      data.nivel ?? 0
    );

  card.classList.remove(
    "loading",
    "level-0",
    "level-1",
    "level-2"
  );

  card.classList.add(
    `level-${level}`
  );

  if (badge) {
    badge.textContent =
      data.rotulo ||
      "SEM INFORMAÇÃO";
  }

  if (icon) {
    icon.textContent =
      level === 0
        ? "✓"
        : level === 1
          ? "!"
          : level === 2
            ? "↑"
            : "•";
  }

  if (title) {
    title.textContent =
      data.titulo ||
      "Situação indisponível";
  }

  if (message) {
    message.textContent =
      data.mensagem ||
      (
        "Não foi possível " +
        "interpretar o alerta atual."
      );
  }

  if (reasons) {
    reasons.innerHTML =
      (
        data.motivos ||
        []
      )
        .map(
          motivo =>
            (
              `<div class="alert-reason">` +
              `${motivo}` +
              `</div>`
            )
        )
        .join("");
  }

  const evento =
    data.evento_serrinha ||
    {};

  if (eventStatus) {
    eventStatus.textContent =
      evento.confirmado
        ? "CONFIRMADO"
        : "NÃO CONFIRMADO";
  }

  if (eventDetail) {
    eventDetail.textContent =
      evento.confirmado
        ? (
            evento.inicio_manaus
              ? (
                  "Início detectado: " +
                  formatDateTime(
                    evento
                      .inicio_manaus
                  )
                )
              : "Evento ativo"
          )
        : (
            "Aguardando alta ≥ " +
            "+3 cm/24 h sustentada"
          );
  }

  const janela =
    data.janela_historica ||
    {};

  if (janela.aplicavel) {
    const inicio =
      formatNumber(
        janela.inicio_dias,
        2
      );

    const fim =
      formatNumber(
        janela.fim_dias,
        2
      );

    const mediana =
      formatNumber(
        janela.mediana_dias,
        2
      );

    if (windowValue) {
      windowValue.textContent =
        `${inicio}–${fim} dias`;
    }

    if (windowDetail) {
      windowDetail.textContent =
        (
          janela.inicio_janela_manaus &&
          janela.fim_janela_manaus
        )
          ? (
              `Mediana histórica: ` +
              `${mediana} dias. ` +
              `Janela: ` +
              `${formatDateTime(
                janela
                  .inicio_janela_manaus
              )} até ` +
              `${formatDateTime(
                janela
                  .fim_janela_manaus
              )}.`
            )
          : (
              `Mediana histórica: ` +
              `${mediana} dias`
            );
    }
  } else {
    if (windowValue) {
      windowValue.textContent =
        "NÃO APLICÁVEL";
    }

    if (windowDetail) {
      windowDetail.textContent =
        (
          "Só é calculada após " +
          "um evento confirmado " +
          "em Serrinha"
        );
    }
  }

  const hist =
    data
      .historico_serrinha_barcelos ||
    {};

  if (hist.disponivel) {
    if (historyValue) {
      historyValue.textContent =
        (
          `${hist
            .eventos_correspondentes ?? 0} ` +
          `de ` +
          `${hist
            .eventos_serrinha ?? 0} ` +
          `eventos`
        );
    }

    if (historyDetail) {
      historyDetail.textContent =
        (
          `Mediana ` +
          `${formatNumber(
            hist.mediana_dias,
            2
          )} dias • ` +
          `faixa central ` +
          `${formatNumber(
            hist.q25_dias,
            2
          )}–` +
          `${formatNumber(
            hist.q75_dias,
            2
          )} dias`
        );
    }
  } else {
    if (historyValue) {
      historyValue.textContent =
        "INDISPONÍVEL";
    }

    if (historyDetail) {
      historyDetail.textContent =
        (
          "Estatística histórica " +
          "não encontrada"
        );
    }
  }
}


function renderAlertUnavailable() {
  const card =
    document.getElementById(
      "alert-card"
    );

  if (card) {
    card.classList.remove(
      "level-0",
      "level-1",
      "level-2"
    );

    card.classList.add(
      "loading"
    );
  }

  const badge =
    document.getElementById(
      "alert-badge"
    );

  const icon =
    document.getElementById(
      "alert-icon"
    );

  const title =
    document.getElementById(
      "alert-title"
    );

  const message =
    document.getElementById(
      "alert-message"
    );

  if (badge) {
    badge.textContent =
      "INDISPONÍVEL";
  }

  if (icon) {
    icon.textContent =
      "?";
  }

  if (title) {
    title.textContent =
      (
        "Alerta temporariamente " +
        "indisponível"
      );
  }

  if (message) {
    message.textContent =
      (
        "Os dados hidrológicos continuam " +
        "sendo exibidos, mas o motor de " +
        "alerta não pôde ser carregado."
      );
  }
}


function createVariationBlock(
  label,
  value
) {
  return `
    <div class="upstream-variation">
      <div class="upstream-variation-label">
        ${label}
      </div>

      <div
        class="
          upstream-variation-value
          ${variationClass(value)}
        "
      >
        ${formatVariation(value)}
      </div>
    </div>
  `;
}


function renderStations(data) {
  const container =
    document.getElementById(
      "upstream-grid"
    );

  if (!container) {
    return;
  }

  const stations =
    data.estacoes ||
    [];

  if (!stations.length) {
    container.innerHTML = `
      <div class="upstream-loading">
        Nenhuma estação disponível.
      </div>
    `;

    return;
  }

  container.innerHTML =
    stations
      .map(
        station => {
          const trend =
            trendInfo(
              station.tendencia
            );

          const barcelosClass =
            station.estacao ===
            "14480002"
              ? "barcelos"
              : "";

          const measurement =
            station
              .data_medicao_manaus ||
            station
              .data_medicao;

          return `
            <article
              class="
                upstream-card
                ${trend.css}
                ${barcelosClass}
              "
            >

              <div class="upstream-name">
                ${station.nome}
              </div>

              <div class="upstream-code">
                ANA ${station.estacao}
              </div>

              <div class="upstream-level">
                ${formatLevel(
                  station.nivel_m
                )}
                <span>m</span>
              </div>

              <div
                class="
                  upstream-trend
                  ${trend.css}
                "
              >
                <span>
                  ${trend.icon}
                </span>

                <span>
                  ${trend.label}
                </span>
              </div>

              <div class="upstream-variations">

                ${createVariationBlock(
                  "6 HORAS",
                  station
                    .variacao_6h_cm
                )}

                ${createVariationBlock(
                  "24 HORAS",
                  station
                    .variacao_24h_cm
                )}

                ${createVariationBlock(
                  "72 HORAS",
                  station
                    .variacao_72h_cm
                )}

                ${createVariationBlock(
                  "7 DIAS",
                  station
                    .variacao_7d_cm
                )}

              </div>

              <div class="upstream-time">
                Medição:
                ${formatShortDateTime(
                  measurement
                )}
              </div>

            </article>
          `;
        }
      )
      .join("");
}


function updatePropagation(data) {
  const title =
    document.getElementById(
      "propagation-title"
    );

  const text =
    document.getElementById(
      "propagation-text"
    );

  const icon =
    document.getElementById(
      "propagation-icon"
    );

  if (
    !title ||
    !text ||
    !icon
  ) {
    return;
  }

  const byCode =
    Object.fromEntries(
      (
        data.estacoes ||
        []
      ).map(
        station => [
          station.estacao,
          station
        ]
      )
    );

  const cucui =
    byCode["14110000"];

  const taracua =
    byCode["14280001"];

  const curicuriari =
    byCode["14330000"];

  const serrinha =
    byCode["14420000"];

  const barcelos =
    byCode["14480002"];

  icon.classList.remove(
    "upstream-rise"
  );

  if (
    serrinha &&
    barcelos &&
    Number(
      serrinha
        .variacao_24h_cm
    ) > 0 &&
    Number(
      barcelos
        .variacao_24h_cm
    ) <= 0
  ) {
    title.textContent =
      (
        "Mudança de comportamento " +
        "próxima de Barcelos"
      );

    let msg =
      (
        `Serrinha registra ` +
        `${formatVariation(
          serrinha
            .variacao_24h_cm
        )} em 24 h e ` +
        `${formatVariation(
          serrinha
            .variacao_72h_cm
        )} em 72 h, enquanto ` +
        `Barcelos registra ` +
        `${formatVariation(
          barcelos
            .variacao_24h_cm
        )} em 24 h e ` +
        `${formatVariation(
          barcelos
            .variacao_72h_cm
        )} em 72 h.`
      );

    if (
      curicuriari &&
      Number(
        curicuriari
          .variacao_72h_cm
      ) > 0
    ) {
      msg +=
        (
          ` Curicuriari também ` +
          `acumula ` +
          `${formatVariation(
            curicuriari
              .variacao_72h_cm
          )} em 72 h.`
        );
    }

    msg +=
      (
        " O painel registra essa " +
        "diferença para acompanhamento. " +
        "Ainda não confirma repiquete."
      );

    text.textContent =
      msg;

    icon.textContent =
      "↑";

    icon.classList.add(
      "upstream-rise"
    );

    return;
  }

  if (
    serrinha &&
    barcelos &&
    Number(
      serrinha
        .variacao_24h_cm
    ) > 0 &&
    Number(
      barcelos
        .variacao_24h_cm
    ) > 0
  ) {
    title.textContent =
      (
        "Alta observada em " +
        "Serrinha e Barcelos"
      );

    text.textContent =
      (
        `Serrinha registra ` +
        `${formatVariation(
          serrinha
            .variacao_24h_cm
        )} em 24 h e Barcelos ` +
        `${formatVariation(
          barcelos
            .variacao_24h_cm
        )}. O movimento já aparece ` +
        `nas duas estações.`
      );

    icon.textContent =
      "↑";

    icon.classList.add(
      "upstream-rise"
    );

    return;
  }

  const upstream =
    [
      cucui,
      taracua,
      curicuriari,
      serrinha
    ].filter(Boolean);

  const rising72h =
    upstream.filter(
      station =>
        Number(
          station
            .variacao_72h_cm
        ) > 0
    );

  if (
    rising72h.length >= 2 &&
    barcelos &&
    Number(
      barcelos
        .variacao_72h_cm
    ) < 0
  ) {
    title.textContent =
      (
        "Alta ainda concentrada " +
        "a montante"
      );

    text.textContent =
      (
        `${rising72h.length} das 4 ` +
        `estações a montante acumulam ` +
        `alta nas últimas 72 h, ` +
        `enquanto Barcelos registra ` +
        `${formatVariation(
          barcelos
            .variacao_72h_cm
        )} no mesmo período. ` +
        `O comportamento será acompanhado ` +
        `nas próximas atualizações.`
      );

    icon.textContent =
      "↑";

    icon.classList.add(
      "upstream-rise"
    );

    return;
  }

  if (
    rising72h.length === 0
  ) {
    title.textContent =
      (
        "Sem alta consistente " +
        "a montante"
      );

    text.textContent =
      (
        "As quatro estações a montante " +
        "não apresentam alta acumulada " +
        "nas últimas 72 horas."
      );

    icon.textContent =
      "↓";

    return;
  }

  title.textContent =
    (
      "Comportamento misto " +
      "a montante"
    );

  text.textContent =
    (
      "As estações apresentam movimentos " +
      "diferentes. O sistema continuará " +
      "comparando as variações de 6 h, " +
      "24 h, 72 h e 7 dias."
    );

  icon.textContent =
    "→";
}


function downsampleSeries(
  series,
  maxPoints = 420
) {
  if (
    !Array.isArray(series)
  ) {
    return [];
  }

  if (
    series.length <=
    maxPoints
  ) {
    return series;
  }

  const step =
    series.length /
    maxPoints;

  const reduced =
    [];

  for (
    let i = 0;
    i < maxPoints;
    i++
  ) {
    reduced.push(
      series[
        Math.floor(
          i * step
        )
      ]
    );
  }

  const last =
    series[
      series.length - 1
    ];

  const reducedLast =
    reduced[
      reduced.length - 1
    ];

  if (
    (
      reducedLast
        .data_medicao_manaus ||
      reducedLast
        .data_medicao
    ) !==
    (
      last
        .data_medicao_manaus ||
      last
        .data_medicao
    )
  ) {
    reduced.push(last);
  }

  return reduced;
}


function createChart(series) {
  const canvas =
    document.getElementById(
      "river-chart"
    );

  if (
    !canvas ||
    typeof Chart === "undefined"
  ) {
    return;
  }

  const reduced =
    downsampleSeries(
      series
    );

  const labels =
    reduced.map(
      item =>
        formatChartLabel(
          item
            .data_medicao_manaus ||
          item
            .data_medicao
        )
    );

  const values =
    reduced.map(
      item =>
        Number(
          item.nivel_m
        )
    );

  if (riverChart) {
    riverChart.destroy();
  }

  riverChart =
    new Chart(
      canvas,
      {
        type:
          "line",

        data: {
          labels,

          datasets: [
            {
              label:
                "Nível do Rio Negro",

              data:
                values,

              borderColor:
                "#43a5ff",

              backgroundColor:
                "rgba(67,165,255,0.10)",

              borderWidth:
                2,

              pointRadius:
                0,

              pointHoverRadius:
                4,

              tension:
                0.22,

              fill:
                true
            }
          ]
        },

        options: {
          responsive:
            true,

          maintainAspectRatio:
            false,

          animation:
            false,

          interaction: {
            mode:
              "index",

            intersect:
              false
          },

          plugins: {
            legend: {
              display:
                false
            },

            tooltip: {
              callbacks: {
                label:
                  context =>
                    (
                      `Nível: ` +
                      `${context
                        .parsed
                        .y
                        .toFixed(2)
                        .replace(
                          ".",
                          ","
                        )} m`
                    )
              }
            }
          },

          scales: {
            x: {
              grid: {
                display:
                  false
              },

              ticks: {
                color:
                  "#8fa7bc",

                maxTicksLimit:
                  8,

                maxRotation:
                  0,

                autoSkip:
                  true
              },

              border: {
                color:
                  "rgba(255,255,255,0.08)"
              }
            },

            y: {
              beginAtZero:
                false,

              grid: {
                color:
                  "rgba(255,255,255,0.055)"
              },

              ticks: {
                color:
                  "#8fa7bc",

                callback:
                  value =>
                    (
                      `${Number(value)
                        .toFixed(2)
                        .replace(
                          ".",
                          ","
                        )} m`
                    )
              },

              border: {
                display:
                  false
              }
            }
          }
        }
      }
    );
}


function buildAnnualCalendar() {
  const labels = [];
  const keys = [];

  const cursor =
    new Date(
      Date.UTC(
        2024,
        0,
        1
      )
    );

  const end =
    new Date(
      Date.UTC(
        2024,
        11,
        31
      )
    );

  while (
    cursor <= end
  ) {
    const month =
      String(
        cursor
          .getUTCMonth() +
        1
      ).padStart(
        2,
        "0"
      );

    const day =
      String(
        cursor
          .getUTCDate()
      ).padStart(
        2,
        "0"
      );

    keys.push(
      `${month}-${day}`
    );

    labels.push(
      `${day}/${month}`
    );

    cursor.setUTCDate(
      cursor.getUTCDate() +
      1
    );
  }

  return {
    labels,
    keys
  };
}


function annualDatasetStyle(
  year,
  latestYear
) {
  if (
    year === latestYear
  ) {
    return {
      borderColor:
        "#58d6ff",

      backgroundColor:
        "rgba(88,214,255,0.08)",

      borderWidth:
        3,

      pointRadius:
        0,

      pointHoverRadius:
        5
    };
  }

  const styles = {
    "2025":
      "#43a5ff",

    "2024":
      "#f5c451",

    "2023":
      "rgba(190,205,220,0.55)"
  };

  return {
    borderColor:
      styles[year] ||
      "rgba(255,255,255,0.45)",

    backgroundColor:
      "transparent",

    borderWidth:
      1.8,

    pointRadius:
      0,

    pointHoverRadius:
      4
  };
}


function formatSameDayDate(value) {
  if (!value) {
    return "—";
  }

  const p =
    String(value)
      .split("-");

  if (
    p.length !== 3
  ) {
    return String(value);
  }

  const months = [
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro"
  ];

  const m =
    Number(p[1]);

  if (
    m < 1 ||
    m > 12
  ) {
    return String(value);
  }

  return (
    `${Number(p[2])} de ` +
    `${months[m - 1]}`
  );
}


function sameDayDifferenceInfo(
  differenceCm
) {
  const rounded =
    Math.round(
      differenceCm
    );

  if (
    Math.abs(
      rounded
    ) < 1
  ) {
    return {
      css:
        "same",

      text:
        "mesmo nível"
    };
  }

  if (rounded > 0) {
    return {
      css:
        "above",

      text:
        `${rounded} cm acima`
    };
  }

  return {
    css:
      "below",

    text:
      (
        `${Math.abs(
          rounded
        )} cm abaixo`
      )
  };
}


function renderSameDayComparison(
  data,
  years,
  latestYear
) {
  const title =
    document.getElementById(
      "same-day-title"
    );

  const reference =
    document.getElementById(
      "same-day-reference"
    );

  const grid =
    document.getElementById(
      "same-day-grid"
    );

  const summary =
    document.getElementById(
      "same-day-summary"
    );

  if (!grid) {
    return;
  }

  const latestSeries =
    data.series?.[
      latestYear
    ] || [];

  if (
    !latestSeries.length
  ) {
    grid.innerHTML = `
      <div class="same-day-loading">
        Não há dados suficientes
        para a comparação.
      </div>
    `;

    return;
  }

  const refPoint =
    latestSeries[
      latestSeries.length - 1
    ];

  const refKey =
    refPoint.dia_mes;

  const refLevel =
    Number(
      refPoint.nivel_m
    );

  const dateText =
    formatSameDayDate(
      refPoint.data
    );

  if (title) {
    title.textContent =
      `Nível em ${dateText}`;
  }

  if (reference) {
    reference.textContent =
      (
        `Mediana diária • ` +
        `${latestYear}`
      );
  }

  const comparisons = [];

  grid.innerHTML =
    [...years]
      .sort(
        (a, b) =>
          Number(b) -
          Number(a)
      )
      .map(
        year => {
          const point =
            (
              data.series?.[
                year
              ] || []
            ).find(
              item =>
                item.dia_mes ===
                refKey
            );

          if (!point) {
            return `
              <article
                class="
                  same-day-card
                  unavailable
                "
              >
                <div class="same-day-year">
                  ${year}
                </div>

                <div class="same-day-level">
                  —
                </div>

                <div class="same-day-difference">
                  sem dado nesta data
                </div>
              </article>
            `;
          }

          const level =
            Number(
              point.nivel_m
            );

          if (
            year === latestYear
          ) {
            return `
              <article
                class="
                  same-day-card
                  current
                "
              >
                <div class="same-day-year">
                  ${year}
                </div>

                <div class="same-day-level">
                  ${formatLevel(
                    level
                  )} m
                </div>

                <div
                  class="
                    same-day-difference
                    reference
                  "
                >
                  ano de referência
                </div>
              </article>
            `;
          }

          const diff =
            sameDayDifferenceInfo(
              (
                refLevel -
                level
              ) * 100
            );

          comparisons.push({
            year,
            text:
              diff.text
          });

          return `
            <article
              class="
                same-day-card
                ${diff.css}
              "
            >
              <div class="same-day-year">
                ${year}
              </div>

              <div class="same-day-level">
                ${formatLevel(
                  level
                )} m
              </div>

              <div
                class="
                  same-day-difference
                  ${diff.css}
                "
              >
                ${latestYear}
                está
                ${diff.text}
              </div>
            </article>
          `;
        }
      )
      .join("");

  if (summary) {
    summary.textContent =
      comparisons.length
        ? (
            `Em ${dateText}, ` +
            comparisons
              .map(
                item =>
                  (
                    `${latestYear} está ` +
                    `${item.text} de ` +
                    `${item.year}`
                  )
              )
              .join(" • ") +
            "."
          )
        : (
            "Não há anos anteriores " +
            "com dados disponíveis " +
            "para esta mesma data."
          );
  }
}


function renderAnnualChart(data) {
  const canvas =
    document.getElementById(
      "annual-chart"
    );

  const status =
    document.getElementById(
      "annual-chart-status"
    );

  const years =
    (
      data.anos ||
      Object.keys(
        data.series ||
        {}
      )
    )
      .map(String)
      .sort();

  if (!years.length) {
    if (status) {
      status.textContent =
        (
          "Nenhum ano disponível " +
          "para comparação."
        );
    }

    return;
  }

  const latestYear =
    years[
      years.length - 1
    ];

  renderSameDayComparison(
    data,
    years,
    latestYear
  );

  if (
    !canvas ||
    typeof Chart === "undefined"
  ) {
    return;
  }

  const {
    labels,
    keys
  } =
    buildAnnualCalendar();

  const datasets =
    years.map(
      year => {
        const byDay =
          Object.fromEntries(
            (
              data.series?.[
                year
              ] || []
            ).map(
              point => [
                point.dia_mes,
                Number(
                  point.nivel_m
                )
              ]
            )
          );

        const style =
          annualDatasetStyle(
            year,
            latestYear
          );

        return {
          label:
            year,

          data:
            keys.map(
              key =>
                Object.prototype
                  .hasOwnProperty
                  .call(
                    byDay,
                    key
                  )
                  ? byDay[key]
                  : null
            ),

          borderColor:
            style.borderColor,

          backgroundColor:
            style.backgroundColor,

          borderWidth:
            style.borderWidth,

          pointRadius:
            style.pointRadius,

          pointHoverRadius:
            style.pointHoverRadius,

          tension:
            0.18,

          spanGaps:
            false,

          fill:
            false
        };
      }
    );

  if (annualChart) {
    annualChart.destroy();
  }

  annualChart =
    new Chart(
      canvas,
      {
        type:
          "line",

        data: {
          labels,
          datasets
        },

        options: {
          responsive:
            true,

          maintainAspectRatio:
            false,

          animation:
            false,

          interaction: {
            mode:
              "index",

            intersect:
              false
          },

          plugins: {
            legend: {
              display:
                true,

              position:
                "top",

              align:
                "start",

              labels: {
                color:
                  "#d6e1eb",

                usePointStyle:
                  true,

                pointStyle:
                  "line",

                boxWidth:
                  28,

                boxHeight:
                  4,

                padding:
                  18,

                font: {
                  size:
                    11,

                  weight:
                    "600"
                }
              }
            },

            tooltip: {
              filter:
                item =>
                  item.raw !== null,

              callbacks: {
                title:
                  items =>
                    (
                      items.length
                        ? items[0].label
                        : ""
                    ),

                label:
                  context =>
                    (
                      context.raw ===
                      null
                        ? ""
                        : (
                            `${context
                              .dataset
                              .label}: ` +
                            `${Number(
                              context.raw
                            )
                              .toFixed(2)
                              .replace(
                                ".",
                                ","
                              )} m`
                          )
                    )
              }
            }
          },

          scales: {
            x: {
              grid: {
                display:
                  false
              },

              border: {
                color:
                  "rgba(255,255,255,0.08)"
              },

              ticks: {
                color:
                  "#8fa7bc",

                maxRotation:
                  0,

                autoSkip:
                  false,

                callback:
                  (
                    value,
                    index
                  ) =>
                    (
                      {
                        "01-01":
                          "JAN",

                        "02-01":
                          "FEV",

                        "03-01":
                          "MAR",

                        "04-01":
                          "ABR",

                        "05-01":
                          "MAI",

                        "06-01":
                          "JUN",

                        "07-01":
                          "JUL",

                        "08-01":
                          "AGO",

                        "09-01":
                          "SET",

                        "10-01":
                          "OUT",

                        "11-01":
                          "NOV",

                        "12-01":
                          "DEZ"
                      }[
                        keys[index]
                      ] || ""
                    )
              }
            },

            y: {
              beginAtZero:
                false,

              grid: {
                color:
                  "rgba(255,255,255,0.055)"
              },

              border: {
                display:
                  false
              },

              ticks: {
                color:
                  "#8fa7bc",

                callback:
                  value =>
                    (
                      `${Number(value)
                        .toFixed(1)
                        .replace(
                          ".",
                          ","
                        )} m`
                    )
              },

              title: {
                display:
                  true,

                text:
                  "Nível do rio (m)",

                color:
                  "#8fa7bc",

                font: {
                  size:
                    11
                }
              }
            }
          }
        }
      }
    );

  if (status) {
    const latestInfo =
      data.resumo?.[
        latestYear
      ];

    status.textContent =
      latestInfo
        ? (
            `${years.length} anos disponíveis • ` +
            `${latestYear}: ` +
            `${latestInfo
              .dias_disponiveis} dias de dados`
          )
        : (
            `${years.length} anos disponíveis`
          );
  }
}


function renderAnnualUnavailable() {
  const status =
    document.getElementById(
      "annual-chart-status"
    );

  const grid =
    document.getElementById(
      "same-day-grid"
    );

  if (status) {
    status.textContent =
      (
        "Comparativo histórico " +
        "temporariamente indisponível."
      );
  }

  if (grid) {
    grid.innerHTML = `
      <div class="same-day-loading">
        Comparação da mesma data
        indisponível.
      </div>
    `;
  }
}


async function fetchJson(
  url,
  cacheKey
) {
  const response =
    await fetch(
      `${url}?v=${cacheKey}`,
      {
        cache:
          "no-store"
      }
    );

  if (!response.ok) {
    throw new Error(
      (
        `Erro ao carregar ` +
        `${url}: HTTP ` +
        `${response.status}`
      )
    );
  }

  return response.json();
}


async function loadAlert(
  cacheKey
) {
  try {
    const data =
      await fetchJson(
        ALERT_URL,
        cacheKey
      );

    renderAlert(data);

  } catch (error) {
    console.error(
      "Erro no alerta:",
      error
    );

    renderAlertUnavailable();
  }
}


async function loadAnnual(
  cacheKey
) {
  try {
    const data =
      await fetchJson(
        ANNUAL_URL,
        cacheKey
      );

    renderAnnualChart(data);

  } catch (error) {
    console.error(
      "Erro no comparativo anual:",
      error
    );

    renderAnnualUnavailable();
  }
}


async function loadData() {
  const cacheKey =
    Date.now();

  try {
    const [
      latest,
      series,
      stations
    ] =
      await Promise.all([
        fetchJson(
          LATEST_URL,
          cacheKey
        ),

        fetchJson(
          SERIES_URL,
          cacheKey
        ),

        fetchJson(
          STATIONS_URL,
          cacheKey
        )
      ]);

    latestData =
      latest;

    updateDashboard(
      latest
    );

    renderStations(
      stations
    );

    updatePropagation(
      stations
    );

    createChart(
      series
    );

  } catch (error) {
    console.error(
      "Erro nos dados principais:",
      error
    );

    const statusText =
      document.getElementById(
        "status-text"
      );

    const statusTime =
      document.getElementById(
        "last-update"
      );

    const dot =
      document.getElementById(
        "status-dot"
      );

    if (statusText) {
      statusText.textContent =
        "Erro ao carregar dados";
    }

    if (statusTime) {
      statusTime.textContent =
        (
          "Tente novamente " +
          "em instantes"
        );
    }

    if (dot) {
      dot.classList.remove(
        "ok"
      );

      dot.classList.add(
        "warning"
      );
    }

    const upstream =
      document.getElementById(
        "upstream-grid"
      );

    if (upstream) {
      upstream.innerHTML = `
        <div class="upstream-loading">
          Não foi possível carregar
          as estações neste momento.
        </div>
      `;
    }
  }

  await Promise.all([
    loadAlert(
      cacheKey
    ),

    loadAnnual(
      cacheKey
    )
  ]);
}


document.addEventListener(
  "DOMContentLoaded",
  () => {
    loadData();

    setInterval(
      loadData,
      5 * 60 * 1000
    );

    setInterval(
      updateLiveStatus,
      60 * 1000
    );
  }
);
