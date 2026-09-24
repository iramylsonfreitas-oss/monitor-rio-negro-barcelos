const LATEST_URL = "data/latest.json";
const SERIES_URL = "data/series_30d.json";

let riverChart = null;

let latestData = null;
let latestLoadedAt = null;


/* =========================
   FORMATAÇÃO
========================= */

function formatLevel(value) {
  if (value === null || value === undefined) {
    return "—";
  }

  return Number(value)
    .toFixed(2)
    .replace(".", ",");
}


function formatVariation(value) {
  if (
    value === null ||
    value === undefined
  ) {
    return "—";
  }

  const number = Number(value);

  if (number > 0) {
    return `+${number.toFixed(0)} cm`;
  }

  if (number < 0) {
    return `${number.toFixed(0)} cm`;
  }

  return "0 cm";
}


function formatDateTime(value) {
  if (!value) {
    return "—";
  }

  const parts = value.split(" ");

  if (parts.length < 2) {
    return value;
  }

  const date = parts[0].split("-");
  const time = parts[1].substring(0, 5);

  if (date.length !== 3) {
    return value;
  }

  return (
    `${date[2]}/${date[1]}/${date[0]} ` +
    `${time}`
  );
}


function formatAnaUpdate(value) {
  if (!value) {
    return "—";
  }

  const parts = value.split(" ");

  if (parts.length < 2) {
    return value;
  }

  const date = parts[0].split("-");
  const time = parts[1].substring(0, 5);

  if (date.length !== 3) {
    return value;
  }

  return (
    `${date[2]}/${date[1]} às ${time}`
  );
}


function formatChartLabel(value) {
  if (!value) {
    return "";
  }

  const parts = value.split(" ");

  if (parts.length < 2) {
    return value;
  }

  const date = parts[0].split("-");
  const time = parts[1].substring(0, 5);

  if (date.length !== 3) {
    return value;
  }

  return `${date[2]}/${date[1]} ${time}`;
}


/* =========================
   IDADE DO DADO
========================= */

function getCurrentAgeMinutes() {
  if (!latestData) {
    return null;
  }

  const baseAge =
    Number(latestData.idade_dado_min);

  if (!Number.isFinite(baseAge)) {
    return null;
  }

  if (!latestLoadedAt) {
    return baseAge;
  }

  const elapsedMinutes =
    Math.floor(
      (Date.now() - latestLoadedAt) /
      60000
    );

  return baseAge + elapsedMinutes;
}


function ageText(minutes) {
  if (
    minutes === null ||
    minutes === undefined
  ) {
    return "Horário indisponível";
  }

  const value = Number(minutes);

  if (value < 60) {
    return `Atualizado há ${value} min`;
  }

  const hours =
    Math.floor(value / 60);

  const remainingMinutes =
    value % 60;

  if (hours < 24) {
    if (remainingMinutes === 0) {
      return `Atualizado há ${hours} h`;
    }

    return (
      `Atualizado há ${hours} h ` +
      `${remainingMinutes} min`
    );
  }

  const days =
    Math.floor(hours / 24);

  return `Atualizado há ${days} dia(s)`;
}


/* =========================
   CORES DAS VARIAÇÕES
========================= */

function applyVariationClass(
  element,
  value
) {
  element.classList.remove(
    "positive",
    "negative",
    "neutral"
  );

  if (
    value === null ||
    value === undefined ||
    Number(value) === 0
  ) {
    element.classList.add("neutral");
    return;
  }

  if (Number(value) > 0) {
    element.classList.add("positive");
  } else {
    element.classList.add("negative");
  }
}


/* =========================
   STATUS
========================= */

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

  const currentAge =
    getCurrentAgeMinutes();

  const stale =
    currentAge !== null &&
    currentAge > 180;

  dot.classList.remove(
    "ok",
    "warning"
  );

  if (stale) {
    dot.classList.add("warning");

    text.textContent =
      "Dado desatualizado";
  } else {
    dot.classList.add("ok");

    text.textContent =
      "Dados atualizados";
  }

  time.textContent =
    ageText(currentAge);
}


/* =========================
   TENDÊNCIA
========================= */

function updateTrend(data) {
  const icon =
    document.getElementById(
      "trend-icon"
    );

  const text =
    document.getElementById(
      "trend-text"
    );

  icon.classList.remove(
    "up",
    "down"
  );

  const trend =
    data.tendencia ||
    "indisponivel";

  if (trend === "subindo") {
    icon.textContent = "↑";
    icon.classList.add("up");

    text.textContent =
      "Subindo";
  }

  else if (trend === "descendo") {
    icon.textContent = "↓";
    icon.classList.add("down");

    text.textContent =
      "Descendo";
  }

  else if (trend === "estavel") {
    icon.textContent = "→";

    text.textContent =
      "Estável";
  }

  else {
    icon.textContent = "—";

    text.textContent =
      "Indisponível";
  }
}


/* =========================
   PAINEL
========================= */

function updateDashboard(data) {
  document.getElementById(
    "level"
  ).textContent =
    formatLevel(data.nivel_m);


  document.getElementById(
    "measurement-time"
  ).textContent =
    "Última medição: " +
    formatDateTime(
      data.data_medicao
    );


  document.getElementById(
    "ana-update-time"
  ).textContent =
    "ANA: última atualização " +
    formatAnaUpdate(
      data.data_atualizacao_ana
    );


  const variation6h =
    document.getElementById(
      "variation-6h"
    );

  const variation24h =
    document.getElementById(
      "variation-24h"
    );

  const variation7d =
    document.getElementById(
      "variation-7d"
    );


  variation6h.textContent =
    formatVariation(
      data.variacao_6h_cm
    );

  variation24h.textContent =
    formatVariation(
      data.variacao_24h_cm
    );

  variation7d.textContent =
    formatVariation(
      data.variacao_7d_cm
    );


  applyVariationClass(
    variation6h,
    data.variacao_6h_cm
  );

  applyVariationClass(
    variation24h,
    data.variacao_24h_cm
  );

  applyVariationClass(
    variation7d,
    data.variacao_7d_cm
  );


  document.getElementById(
    "records-count"
  ).textContent =
    data.registros_30d ?? "—";


  updateTrend(data);

  updateLiveStatus();
}


/* =========================
   REDUZIR PONTOS DO GRÁFICO
========================= */

function downsampleSeries(
  series,
  maxPoints = 420
) {
  if (series.length <= maxPoints) {
    return series;
  }

  const step =
    series.length / maxPoints;

  const reduced = [];

  for (
    let i = 0;
    i < maxPoints;
    i++
  ) {
    const index =
      Math.floor(i * step);

    reduced.push(
      series[index]
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
    reducedLast.data_medicao !==
    last.data_medicao
  ) {
    reduced.push(last);
  }

  return reduced;
}


/* =========================
   GRÁFICO
========================= */

function createChart(series) {
  const canvas =
    document.getElementById(
      "river-chart"
    );

  if (!canvas) {
    return;
  }

  const reduced =
    downsampleSeries(series);

  const labels =
    reduced.map(
      item =>
        formatChartLabel(
          item.data_medicao
        )
    );

  const values =
    reduced.map(
      item =>
        Number(item.nivel_m)
    );


  if (riverChart) {
    riverChart.destroy();
  }


  riverChart = new Chart(
    canvas,
    {
      type: "line",

      data: {
        labels,

        datasets: [
          {
            label:
              "Nível do Rio Negro",

            data: values,

            borderColor:
              "#43a5ff",

            backgroundColor:
              "rgba(67,165,255,0.10)",

            borderWidth: 2,

            pointRadius: 0,

            pointHoverRadius: 4,

            tension: 0.22,

            fill: true
          }
        ]
      },

      options: {
        responsive: true,

        maintainAspectRatio:
          false,

        animation: false,

        interaction: {
          mode: "index",
          intersect: false
        },

        plugins: {
          legend: {
            display: false
          },

          tooltip: {
            callbacks: {
              label: function(
                context
              ) {
                return (
                  "Nível: " +
                  context.parsed.y
                    .toFixed(2)
                    .replace(".", ",") +
                  " m"
                );
              }
            }
          }
        },

        scales: {
          x: {
            grid: {
              display: false
            },

            ticks: {
              color:
                "#8fa7bc",

              maxTicksLimit: 8,

              maxRotation: 0,

              autoSkip: true
            },

            border: {
              color:
                "rgba(255,255,255,0.08)"
            }
          },

          y: {
            beginAtZero: false,

            grid: {
              color:
                "rgba(255,255,255,0.055)"
            },

            ticks: {
              color:
                "#8fa7bc",

              callback: function(
                value
              ) {
                return (
                  Number(value)
                    .toFixed(2)
                    .replace(".", ",") +
                  " m"
                );
              }
            },

            border: {
              display: false
            }
          }
        }
      }
    }
  );
}


/* =========================
   CARREGAMENTO
========================= */

async function loadData() {
  try {
    const cacheKey =
      Date.now();

    const [
      latestResponse,
      seriesResponse
    ] = await Promise.all([
      fetch(
        `${LATEST_URL}?v=${cacheKey}`,
        {
          cache: "no-store"
        }
      ),

      fetch(
        `${SERIES_URL}?v=${cacheKey}`,
        {
          cache: "no-store"
        }
      )
    ]);


    if (!latestResponse.ok) {
      throw new Error(
        "Erro ao carregar latest.json"
      );
    }


    if (!seriesResponse.ok) {
      throw new Error(
        "Erro ao carregar series_30d.json"
      );
    }


    const latest =
      await latestResponse.json();

    const series =
      await seriesResponse.json();


    latestData = latest;

    latestLoadedAt =
      Date.now();


    updateDashboard(
      latest
    );

    createChart(
      series
    );
  }

  catch (error) {
    console.error(error);

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


    statusText.textContent =
      "Erro ao carregar dados";

    statusTime.textContent =
      "Tente novamente em instantes";

    dot.classList.remove("ok");

    dot.classList.add(
      "warning"
    );
  }
}


/* =========================
   INICIALIZAÇÃO
========================= */

document.addEventListener(
  "DOMContentLoaded",
  () => {

    loadData();


    // Busca novos dados no GitHub
    // a cada 5 minutos.
    setInterval(
      loadData,
      5 * 60 * 1000
    );


    // Atualiza apenas o texto
    // "Atualizado há..."
    // a cada minuto.
    setInterval(
      updateLiveStatus,
      60 * 1000
    );

  }
);
