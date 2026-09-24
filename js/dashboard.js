const LATEST_URL = "data/latest.json";
const SERIES_URL = "data/series_30d.json";
const STATIONS_URL = "data/estacoes.json";
const ALERT_URL = "data/alerta.json";

let riverChart = null;

let latestData = null;
let latestLoadedAt = null;


/* =========================
   FUNÇÕES AUXILIARES
========================= */

function formatLevel(value) {
  if (
    value === null ||
    value === undefined
  ) {
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

  const formatted =
    Number.isInteger(number)
      ? Math.abs(number).toFixed(0)
      : Math.abs(number).toFixed(1);

  if (number > 0) {
    return `+${formatted} cm`;
  }

  if (number < 0) {
    return `-${formatted} cm`;
  }

  return "0 cm";
}


function formatNumber(value, decimals = 2) {
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


function formatShortDateTime(value) {
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
    `${date[2]}/${date[1]} ${time}`
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


function variationClass(value) {
  if (
    value === null ||
    value === undefined ||
    Number(value) === 0
  ) {
    return "neutral";
  }

  if (Number(value) > 0) {
    return "positive";
  }

  return "negative";
}


function trendInfo(trend) {
  if (trend === "subindo") {
    return {
      icon: "↑",
      label: "Subindo",
      css: "up"
    };
  }

  if (trend === "descendo") {
    return {
      icon: "↓",
      label: "Descendo",
      css: "down"
    };
  }

  if (trend === "estavel") {
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


/* =========================
   IDADE DO DADO
========================= */

function getCurrentAgeMinutes() {
  if (!latestData) {
    return null;
  }

  const baseAge =
    Number(
      latestData.idade_dado_min
    );

  if (!Number.isFinite(baseAge)) {
    return null;
  }

  if (!latestLoadedAt) {
    return baseAge;
  }

  const elapsedMinutes =
    Math.floor(
      (
        Date.now() -
        latestLoadedAt
      ) / 60000
    );

  return (
    baseAge +
    elapsedMinutes
  );
}


function ageText(minutes) {
  if (
    minutes === null ||
    minutes === undefined
  ) {
    return "Horário indisponível";
  }

  const value =
    Number(minutes);

  if (value < 60) {
    return (
      `Atualizado há ${value} min`
    );
  }

  const hours =
    Math.floor(
      value / 60
    );

  const remainingMinutes =
    value % 60;

  if (hours < 24) {
    if (
      remainingMinutes === 0
    ) {
      return (
        `Atualizado há ${hours} h`
      );
    }

    return (
      `Atualizado há ${hours} h ` +
      `${remainingMinutes} min`
    );
  }

  const days =
    Math.floor(
      hours / 24
    );

  return (
    `Atualizado há ${days} dia(s)`
  );
}


/* =========================
   STATUS PRINCIPAL
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
    dot.classList.add(
      "warning"
    );

    text.textContent =
      "Dado desatualizado";
  } else {
    dot.classList.add(
      "ok"
    );

    text.textContent =
      "Dados atualizados";
  }

  time.textContent =
    ageText(
      currentAge
    );
}


/* =========================
   TENDÊNCIA DE BARCELOS
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

  const info =
    trendInfo(
      data.tendencia
    );

  icon.textContent =
    info.icon;

  text.textContent =
    info.label;

  if (info.css === "up") {
    icon.classList.add(
      "up"
    );
  }

  if (info.css === "down") {
    icon.classList.add(
      "down"
    );
  }
}


/* =========================
   BARCELOS
========================= */

function updateDashboard(data) {
  document.getElementById(
    "level"
  ).textContent =
    formatLevel(
      data.nivel_m
    );


  document.getElementById(
    "measurement-time"
  ).textContent =
    "Última medição: " +
    formatDateTime(
      data.data_medicao_manaus ||
      data.data_medicao
    );


  document.getElementById(
    "ana-update-time"
  ).textContent =
    "ANA: última atualização " +
    formatAnaUpdate(
      data.data_atualizacao_manaus ||
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


  variation6h.className =
    "metric-value " +
    variationClass(
      data.variacao_6h_cm
    );

  variation24h.className =
    "metric-value " +
    variationClass(
      data.variacao_24h_cm
    );

  variation7d.className =
    "metric-value " +
    variationClass(
      data.variacao_7d_cm
    );


  document.getElementById(
    "records-count"
  ).textContent =
    data.registros_30d ??
    "—";


  updateTrend(
    data
  );

  updateLiveStatus();
}


/* =========================
   ALERTA ANTECIPADO
========================= */

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


  badge.textContent =
    data.rotulo ||
    "SEM INFORMAÇÃO";


  title.textContent =
    data.titulo ||
    "Situação indisponível";


  message.textContent =
    data.mensagem ||
    "Não foi possível interpretar o alerta atual.";


  if (level === 0) {
    icon.textContent =
      "✓";
  }

  else if (level === 1) {
    icon.textContent =
      "!";
  }

  else if (level === 2) {
    icon.textContent =
      "↑";
  }

  else {
    icon.textContent =
      "•";
  }


  const motivos =
    data.motivos || [];


  if (motivos.length) {
    reasons.innerHTML =
      motivos.map(
        motivo => `
          <div class="alert-reason">
            ${motivo}
          </div>
        `
      ).join("");
  } else {
    reasons.innerHTML = "";
  }


  const evento =
    data.evento_serrinha || {};


  if (evento.confirmado) {
    eventStatus.textContent =
      "CONFIRMADO";

    eventDetail.textContent =
      evento.inicio_manaus
        ? (
            "Início detectado: " +
            formatDateTime(
              evento.inicio_manaus
            )
          )
        : (
            "Evento ativo"
          );
  } else {
    eventStatus.textContent =
      "NÃO CONFIRMADO";

    eventDetail.textContent =
      "Aguardando alta ≥ +3 cm/24 h sustentada";
  }


  const janela =
    data.janela_historica || {};


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


    windowValue.textContent =
      `${inicio}–${fim} dias`;


    if (
      janela.inicio_janela_manaus &&
      janela.fim_janela_manaus
    ) {
      windowDetail.textContent =
        (
          `Mediana histórica: ${mediana} dias. ` +
          `Janela: ${formatDateTime(
            janela.inicio_janela_manaus
          )} até ${formatDateTime(
            janela.fim_janela_manaus
          )}.`
        );
    } else {
      windowDetail.textContent =
        (
          `Mediana histórica: ` +
          `${mediana} dias`
        );
    }
  } else {
    windowValue.textContent =
      "NÃO APLICÁVEL";

    windowDetail.textContent =
      (
        "Só é calculada após um evento " +
        "confirmado em Serrinha"
      );
  }


  const historico =
    data.historico_serrinha_barcelos ||
    {};


  if (historico.disponivel) {
    const total =
      historico.eventos_serrinha ??
      0;

    const correspondentes =
      historico.eventos_correspondentes ??
      0;

    const mediana =
      formatNumber(
        historico.mediana_dias,
        2
      );

    const q25 =
      formatNumber(
        historico.q25_dias,
        2
      );

    const q75 =
      formatNumber(
        historico.q75_dias,
        2
      );


    historyValue.textContent =
      `${correspondentes} de ${total} eventos`;


    historyDetail.textContent =
      (
        `Mediana ${mediana} dias • ` +
        `faixa central ${q25}–${q75} dias`
      );
  } else {
    historyValue.textContent =
      "INDISPONÍVEL";

    historyDetail.textContent =
      "Estatística histórica não encontrada";
  }
}


/* =========================
   ALERTA INDISPONÍVEL
========================= */

function renderAlertUnavailable() {
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

  card.classList.remove(
    "level-0",
    "level-1",
    "level-2"
  );

  card.classList.add(
    "loading"
  );

  badge.textContent =
    "INDISPONÍVEL";

  icon.textContent =
    "?";

  title.textContent =
    "Alerta temporariamente indisponível";

  message.textContent =
    (
      "Os dados hidrológicos continuam sendo exibidos, " +
      "mas o motor de alerta não pôde ser carregado."
    );
}


/* =========================
   CARDS DAS ESTAÇÕES
========================= */

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

  const stations =
    data.estacoes || [];

  if (!stations.length) {
    container.innerHTML = `
      <div class="upstream-loading">
        Nenhuma estação disponível.
      </div>
    `;

    return;
  }


  const cards =
    stations.map(
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
          station.data_medicao_manaus ||
          station.data_medicao;


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
                station.variacao_6h_cm
              )}

              ${createVariationBlock(
                "24 HORAS",
                station.variacao_24h_cm
              )}

              ${createVariationBlock(
                "72 HORAS",
                station.variacao_72h_cm
              )}

              ${createVariationBlock(
                "7 DIAS",
                station.variacao_7d_cm
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


  container.innerHTML =
    cards;
}


/* =========================
   ANÁLISE DE PROPAGAÇÃO
========================= */

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


  const stations =
    data.estacoes || [];


  const byCode =
    Object.fromEntries(
      stations.map(
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
      serrinha.variacao_24h_cm
    ) > 0 &&
    Number(
      barcelos.variacao_24h_cm
    ) <= 0
  ) {

    title.textContent =
      (
        "Mudança de comportamento " +
        "próxima de Barcelos"
      );


    let message =
      `Serrinha registra ` +
      `${formatVariation(
        serrinha.variacao_24h_cm
      )} em 24 h e ` +
      `${formatVariation(
        serrinha.variacao_72h_cm
      )} em 72 h, enquanto Barcelos ` +
      `registra ${formatVariation(
        barcelos.variacao_24h_cm
      )} em 24 h e ` +
      `${formatVariation(
        barcelos.variacao_72h_cm
      )} em 72 h.`;


    if (
      curicuriari &&
      Number(
        curicuriari.variacao_72h_cm
      ) > 0
    ) {

      message +=
        (
          ` Curicuriari também acumula ` +
          `${formatVariation(
            curicuriari.variacao_72h_cm
          )} em 72 h.`
        );
    }


    message +=
      (
        " O painel registra essa diferença " +
        "para acompanhamento. Ainda não " +
        "confirma repiquete."
      );


    text.textContent =
      message;

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
      serrinha.variacao_24h_cm
    ) > 0 &&
    Number(
      barcelos.variacao_24h_cm
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
          serrinha.variacao_24h_cm
        )} em 24 h e Barcelos ` +
        `${formatVariation(
          barcelos.variacao_24h_cm
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
          station.variacao_72h_cm
        ) > 0
    );


  if (
    rising72h.length >= 2 &&
    barcelos &&
    Number(
      barcelos.variacao_72h_cm
    ) < 0
  ) {

    title.textContent =
      (
        "Alta ainda concentrada " +
        "a montante"
      );


    text.textContent =
      (
        `${rising72h.length} das 4 estações ` +
        `a montante acumulam alta nas últimas ` +
        `72 h, enquanto Barcelos registra ` +
        `${formatVariation(
          barcelos.variacao_72h_cm
        )} no mesmo período. O comportamento ` +
        `será acompanhado nas próximas atualizações.`
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
    "Comportamento misto a montante";


  text.textContent =
    (
      "As estações apresentam movimentos diferentes. " +
      "O sistema continuará comparando as variações " +
      "de 6 h, 24 h, 72 h e 7 dias."
    );


  icon.textContent =
    "→";
}


/* =========================
   REDUÇÃO DA SÉRIE
========================= */

function downsampleSeries(
  series,
  maxPoints = 420
) {
  if (
    series.length <=
    maxPoints
  ) {
    return series;
  }


  const step =
    series.length /
    maxPoints;


  const reduced = [];


  for (
    let i = 0;
    i < maxPoints;
    i++
  ) {

    const index =
      Math.floor(
        i * step
      );


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

    reduced.push(
      last
    );
  }


  return reduced;
}


/* =========================
   GRÁFICO DE BARCELOS
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
    downsampleSeries(
      series
    );


  const labels =
    reduced.map(
      item =>
        formatChartLabel(
          item.data_medicao_manaus ||
          item.data_medicao
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
                label:
                  function(
                    context
                  ) {

                    return (
                      "Nível: " +
                      context.parsed.y
                        .toFixed(2)
                        .replace(
                          ".",
                          ","
                        ) +
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

                callback:
                  function(
                    value
                  ) {

                    return (
                      Number(value)
                        .toFixed(2)
                        .replace(
                          ".",
                          ","
                        ) +
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
   CARREGAMENTO JSON
========================= */

async function fetchJson(
  url,
  cacheKey
) {

  const response =
    await fetch(
      `${url}?v=${cacheKey}`,
      {
        cache: "no-store"
      }
    );


  if (!response.ok) {
    throw new Error(
      `Erro ao carregar ${url}`
    );
  }


  return response.json();
}


/* =========================
   CARREGAR ALERTA
========================= */

async function loadAlert(
  cacheKey
) {

  try {

    const alertData =
      await fetchJson(
        ALERT_URL,
        cacheKey
      );


    renderAlert(
      alertData
    );

  }

  catch (error) {

    console.error(
      "Erro no alerta:",
      error
    );


    renderAlertUnavailable();
  }
}


/* =========================
   CARREGAMENTO PRINCIPAL
========================= */

async function loadData() {
  try {

    const cacheKey =
      Date.now();


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

    latestLoadedAt =
      Date.now();


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


    await loadAlert(
      cacheKey
    );

  }

  catch (error) {

    console.error(
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


    statusText.textContent =
      "Erro ao carregar dados";


    statusTime.textContent =
      "Tente novamente em instantes";


    dot.classList.remove(
      "ok"
    );


    dot.classList.add(
      "warning"
    );


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


    renderAlertUnavailable();
  }
}


/* =========================
   INICIALIZAÇÃO
========================= */

document.addEventListener(
  "DOMContentLoaded",
  () => {

    loadData();


    /*
      Busca novos arquivos no GitHub
      a cada 5 minutos.
    */

    setInterval(
      loadData,
      5 * 60 * 1000
    );


    /*
      Atualiza somente o texto
      "Atualizado há..."
      a cada minuto.
    */

    setInterval(
      updateLiveStatus,
      60 * 1000
    );

  }
);
