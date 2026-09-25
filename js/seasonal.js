const SEASONAL_DATA_URL =
  "data/barcelos_anual.json";

let seasonalChartInstance =
  null;


/* =========================
   ESTATÍSTICA
========================= */

function seasonalQuantile(
  values,
  q
) {
  const sorted =
    values
      .filter(
        Number.isFinite
      )
      .slice()
      .sort(
        (a, b) =>
          a - b
      );

  if (!sorted.length) {
    return null;
  }

  if (
    sorted.length === 1
  ) {
    return sorted[0];
  }

  const pos =
    (
      sorted.length - 1
    ) * q;

  const base =
    Math.floor(pos);

  const rest =
    pos - base;

  const next =
    sorted[
      base + 1
    ];

  return (
    next === undefined
      ? sorted[base]
      : (
          sorted[base] +
          rest *
          (
            next -
            sorted[base]
          )
        )
  );
}


/* =========================
   CALENDÁRIO
========================= */

function seasonalDayIndex(
  dayMonth
) {
  if (!dayMonth) {
    return null;
  }

  const [
    month,
    day
  ] =
    dayMonth
      .split("-")
      .map(Number);

  const date =
    new Date(
      Date.UTC(
        2024,
        month - 1,
        day
      )
    );

  if (
    Number.isNaN(
      date.getTime()
    )
  ) {
    return null;
  }

  const start =
    new Date(
      Date.UTC(
        2024,
        0,
        1
      )
    );

  return Math.round(
    (
      date -
      start
    ) /
    86400000
  );
}


function seasonalCircularDistance(
  a,
  b
) {
  const diff =
    Math.abs(
      a - b
    );

  return Math.min(
    diff,
    366 - diff
  );
}


function seasonalCalendar() {
  const keys = [];
  const labels = [];

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
      cursor
        .getUTCDate() +
      1
    );
  }

  return {
    keys,
    labels
  };
}


/* =========================
   FORMATAÇÃO
========================= */

function seasonalFormatLevel(
  value
) {
  return Number(value)
    .toFixed(2)
    .replace(
      ".",
      ","
    );
}


function seasonalFormatDate(
  dateText
) {
  if (!dateText) {
    return "—";
  }

  const [
    year,
    month,
    day
  ] =
    dateText.split("-");

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

  return (
    `${Number(day)} de ` +
    `${months[
      Number(month) - 1
    ] || month}`
  );
}


function seasonalPositionLabel(
  percentile
) {
  if (
    percentile <= 10
  ) {
    return "Muito baixo";
  }

  if (
    percentile <= 25
  ) {
    return "Baixo";
  }

  if (
    percentile < 75
  ) {
    return (
      "Dentro da faixa típica"
    );
  }

  if (
    percentile < 90
  ) {
    return "Alto";
  }

  return "Muito alto";
}


/* =========================
   REFERÊNCIA ±7 DIAS
========================= */

function seasonalReferenceValues(
  referencePoints,
  targetIndex,
  windowDays = 7
) {
  return referencePoints
    .filter(
      point => {
        const index =
          seasonalDayIndex(
            point.dia_mes
          );

        return (
          index !== null &&
          seasonalCircularDistance(
            index,
            targetIndex
          ) <= windowDays
        );
      }
    )
    .map(
      point =>
        Number(
          point.nivel_m
        )
    )
    .filter(
      Number.isFinite
    );
}


function seasonalBuildReference(
  data,
  latestYear,
  keys
) {
  const referenceYears =
    (
      data.anos ||
      Object.keys(
        data.series ||
        {}
      )
    )
      .map(String)
      .filter(
        year =>
          year !==
          latestYear
      )
      .sort();

  const referencePoints =
    referenceYears
      .flatMap(
        year =>
          (
            data.series?.[
              year
            ] || []
          ).map(
            point => ({
              dia_mes:
                point.dia_mes,

              nivel_m:
                Number(
                  point.nivel_m
                ),

              year
            })
          )
      );

  const p25 = [];
  const median = [];
  const p75 = [];
  const counts = [];

  keys.forEach(
    key => {
      const targetIndex =
        seasonalDayIndex(
          key
        );

      const values =
        seasonalReferenceValues(
          referencePoints,
          targetIndex,
          7
        );

      counts.push(
        values.length
      );

      p25.push(
        values.length >= 6
          ? seasonalQuantile(
              values,
              0.25
            )
          : null
      );

      median.push(
        values.length >= 6
          ? seasonalQuantile(
              values,
              0.50
            )
          : null
      );

      p75.push(
        values.length >= 6
          ? seasonalQuantile(
              values,
              0.75
            )
          : null
      );
    }
  );

  return {
    referenceYears,
    referencePoints,
    p25,
    median,
    p75,
    counts
  };
}


/* =========================
   CRIAÇÃO DO CARD
========================= */

function seasonalInsertPanel() {
  if (
    document.getElementById(
      "seasonal-card"
    )
  ) {
    return;
  }

  const annualCard =
    document.querySelector(
      ".annual-chart-card"
    );

  if (!annualCard) {
    return;
  }

  annualCard.insertAdjacentHTML(
    "beforebegin",
    `
      <section
        id="seasonal-card"
        class="chart-card seasonal-card"
      >

        <div class="chart-header">

          <div>

            <div class="section-label">
              POSIÇÃO SAZONAL
            </div>

            <h2>
              Barcelos nesta época do ano
            </h2>

            <div class="chart-subtitle">
              Nível atual comparado à referência
              histórica móvel de ±7 dias.
            </div>

          </div>


          <div
            class="chart-info"
            id="seasonal-reference-years"
          >
            —
          </div>

        </div>


        <div class="seasonal-summary-grid">


          <div class="seasonal-gauge-card">

            <div class="seasonal-gauge-top">

              <div>

                <div class="seasonal-mini-label">
                  POSIÇÃO ATUAL
                </div>

                <div
                  id="seasonal-position-label"
                  class="seasonal-position-label"
                >
                  Calculando...
                </div>

              </div>


              <div
                id="seasonal-percentile"
                class="seasonal-percentile"
              >
                —
              </div>

            </div>


            <div class="seasonal-gauge">

              <div class="seasonal-gauge-scale">

                <span>
                  Muito baixo
                </span>

                <span>
                  Baixo
                </span>

                <span>
                  Típico
                </span>

                <span>
                  Alto
                </span>

                <span>
                  Muito alto
                </span>

              </div>


              <div class="seasonal-gauge-track">

                <div
                  id="seasonal-gauge-marker"
                  class="seasonal-gauge-marker"
                ></div>

              </div>

            </div>

          </div>


          <div class="seasonal-stat-card">

            <div class="seasonal-mini-label">
              NÍVEL DO DIA
            </div>

            <div
              id="seasonal-current-level"
              class="seasonal-stat-value"
            >
              —
            </div>

            <div
              id="seasonal-current-date"
              class="seasonal-stat-detail"
            >
              —
            </div>

          </div>


          <div class="seasonal-stat-card">

            <div class="seasonal-mini-label">
              MEDIANA SAZONAL
            </div>

            <div
              id="seasonal-median-level"
              class="seasonal-stat-value"
            >
              —
            </div>

            <div
              id="seasonal-difference"
              class="seasonal-stat-detail"
            >
              —
            </div>

          </div>

        </div>


        <div
          id="seasonal-status"
          class="seasonal-status"
        >
          Calculando referência sazonal...
        </div>


        <div
          class="
            chart-container
            seasonal-chart-container
          "
        >

          <canvas
            id="seasonal-chart"
          ></canvas>

        </div>


        <div class="seasonal-note">

          Faixa típica = percentis 25–75
          da referência móvel.

          A referência exclui o ano atual
          e usa os anos históricos disponíveis;
          por isso deve ser lida como comparação
          exploratória, não como climatologia
          de longo prazo.

        </div>

      </section>
    `
  );
}


/* =========================
   RESUMO DO DIA
========================= */

function seasonalRenderSummary(
  data,
  latestYear,
  reference
) {
  const latestSeries =
    data.series?.[
      latestYear
    ] || [];

  if (
    !latestSeries.length
  ) {
    return null;
  }

  const currentPoint =
    latestSeries[
      latestSeries.length - 1
    ];

  const targetIndex =
    seasonalDayIndex(
      currentPoint.dia_mes
    );

  const values =
    seasonalReferenceValues(
      reference
        .referencePoints,

      targetIndex,

      7
    );

  if (!values.length) {
    return null;
  }

  const currentLevel =
    Number(
      currentPoint.nivel_m
    );

  const median =
    seasonalQuantile(
      values,
      0.50
    );

  const less =
    values.filter(
      value =>
        value <
        currentLevel
    ).length;

  const equal =
    values.filter(
      value =>
        value ===
        currentLevel
    ).length;

  const percentile =
    Math.round(
      (
        (
          less +
          0.5 * equal
        ) /
        values.length
      ) *
      100
    );

  const differenceCm =
    Math.round(
      (
        currentLevel -
        median
      ) *
      100
    );

  document.getElementById(
    "seasonal-position-label"
  ).textContent =
    seasonalPositionLabel(
      percentile
    );

  document.getElementById(
    "seasonal-percentile"
  ).textContent =
    `P${percentile}`;

  document.getElementById(
    "seasonal-gauge-marker"
  ).style.left =
    (
      `${Math.max(
        0,
        Math.min(
          100,
          percentile
        )
      )}%`
    );

  document.getElementById(
    "seasonal-current-level"
  ).textContent =
    (
      `${seasonalFormatLevel(
        currentLevel
      )} m`
    );

  document.getElementById(
    "seasonal-current-date"
  ).textContent =
    seasonalFormatDate(
      currentPoint.data
    );

  document.getElementById(
    "seasonal-median-level"
  ).textContent =
    (
      `${seasonalFormatLevel(
        median
      )} m`
    );

  const differenceText =
    differenceCm === 0
      ? (
          "igual à mediana sazonal"
        )
      : differenceCm > 0
        ? (
            `${differenceCm} cm ` +
            `acima da mediana`
          )
        : (
            `${Math.abs(
              differenceCm
            )} cm ` +
            `abaixo da mediana`
          );

  document.getElementById(
    "seasonal-difference"
  ).textContent =
    differenceText;

  document.getElementById(
    "seasonal-status"
  ).textContent =
    (
      `${seasonalFormatDate(
        currentPoint.data
      )} • ` +
      `${values.length} valores históricos ` +
      `na janela ±7 dias`
    );

  return {
    currentPoint,
    percentile,
    median,
    values
  };
}


/* =========================
   GRÁFICO SAZONAL
========================= */

function seasonalRenderChart(
  data,
  latestYear,
  calendar,
  reference
) {
  const canvas =
    document.getElementById(
      "seasonal-chart"
    );

  if (
    !canvas ||
    typeof Chart ===
    "undefined"
  ) {
    return;
  }

  const currentByDay =
    Object.fromEntries(
      (
        data.series?.[
          latestYear
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

  const currentValues =
    calendar.keys.map(
      key =>
        Object.prototype
          .hasOwnProperty
          .call(
            currentByDay,
            key
          )
          ? currentByDay[key]
          : null
    );

  if (
    seasonalChartInstance
  ) {
    seasonalChartInstance
      .destroy();
  }

  seasonalChartInstance =
    new Chart(
      canvas,
      {

        type:
          "line",

        data: {

          labels:
            calendar.labels,

          datasets: [

            {
              label:
                "__p25",

              data:
                reference.p25,

              borderColor:
                "rgba(0,0,0,0)",

              backgroundColor:
                "rgba(0,0,0,0)",

              pointRadius:
                0,

              borderWidth:
                0,

              tension:
                0.22
            },


            {
              label:
                "Faixa típica (P25–P75)",

              data:
                reference.p75,

              borderColor:
                "rgba(0,0,0,0)",

              backgroundColor:
                "rgba(88,214,255,0.12)",

              pointRadius:
                0,

              borderWidth:
                0,

              fill:
                "-1",

              tension:
                0.22
            },


            {
              label:
                "Mediana sazonal",

              data:
                reference.median,

              borderColor:
                "rgba(190,205,220,0.75)",

              backgroundColor:
                "transparent",

              borderWidth:
                1.7,

              borderDash:
                [
                  6,
                  5
                ],

              pointRadius:
                0,

              tension:
                0.22,

              spanGaps:
                true
            },


            {
              label:
                latestYear,

              data:
                currentValues,

              borderColor:
                "#58d6ff",

              backgroundColor:
                "transparent",

              borderWidth:
                3,

              pointRadius:
                0,

              pointHoverRadius:
                5,

              tension:
                0.18,

              spanGaps:
                false
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

                padding:
                  18,

                filter:
                  item =>
                    (
                      item.text !==
                      "__p25"
                    )
              }
            },


            tooltip: {

              filter:
                item =>
                  (
                    item.dataset.label !==
                    "__p25" &&
                    item.raw !==
                    null
                  ),

              callbacks: {

                label:
                  context => {

                    if (
                      context.raw ===
                      null
                    ) {
                      return "";
                    }

                    return (
                      `${context.dataset.label}: ` +
                      `${seasonalFormatLevel(
                        context.raw
                      )} m`
                    );
                  }
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
                        calendar
                          .keys[
                            index
                          ]
                      ] ||
                      ""
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
                  "#8fa7bc"
              }
            }
          }
        }
      }
    );
}


/* =========================
   INICIALIZAÇÃO
========================= */

async function seasonalInit() {
  seasonalInsertPanel();

  const status =
    document.getElementById(
      "seasonal-status"
    );

  if (!status) {
    return;
  }

  try {

    const response =
      await fetch(
        (
          `${SEASONAL_DATA_URL}` +
          `?v=${Date.now()}`
        ),
        {
          cache:
            "no-store"
        }
      );

    if (!response.ok) {
      throw new Error(
        `HTTP ${response.status}`
      );
    }

    const data =
      await response.json();

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

    const latestYear =
      years[
        years.length - 1
      ];

    if (!latestYear) {
      throw new Error(
        "Nenhum ano disponível"
      );
    }

    const calendar =
      seasonalCalendar();

    const reference =
      seasonalBuildReference(
        data,
        latestYear,
        calendar.keys
      );

    const refLabel =
      document.getElementById(
        "seasonal-reference-years"
      );

    if (refLabel) {

      refLabel.textContent =
        reference
          .referenceYears
          .length

          ? (
              `Referência ` +
              `${reference
                .referenceYears[
                  0
                ]}–` +
              `${reference
                .referenceYears[
                  reference
                    .referenceYears
                    .length -
                  1
                ]}`
            )

          : (
              "Sem referência histórica"
            );
    }

    seasonalRenderSummary(
      data,
      latestYear,
      reference
    );

    seasonalRenderChart(
      data,
      latestYear,
      calendar,
      reference
    );

  } catch (error) {

    console.error(
      "Erro na posição sazonal:",
      error
    );

    status.textContent =
      (
        "Posição sazonal " +
        "temporariamente indisponível."
      );
  }
}


document.addEventListener(
  "DOMContentLoaded",
  seasonalInit
);
