(() => {
  "use strict";

  const DATA_URL = "data/estacoes.json";
  const REFRESH_MS = 5 * 60 * 1000;

  const STATION_ORDER = [
    "14110000",
    "14280001",
    "14330000",
    "14420000",
    "14480002"
  ];

  const STATION_LABELS = {
    "14110000": "Cucuí",
    "14280001": "Taracuá",
    "14330000": "Curicuriari",
    "14420000": "Serrinha",
    "14480002": "Barcelos"
  };


  // ========================================================
  // ESTILO
  // ========================================================

  function installStyles() {
    if (document.getElementById("river-radar-styles")) {
      return;
    }

    const style = document.createElement("style");

    style.id = "river-radar-styles";

    style.textContent = `
      .river-radar-section {
        margin-top: 24px;
        padding: 28px;
        border-radius: 24px;
        background:
          linear-gradient(
            145deg,
            rgba(8, 26, 45, 0.98),
            rgba(10, 38, 61, 0.96)
          );
        border: 1px solid rgba(255,255,255,0.08);
        box-shadow: 0 18px 45px rgba(0,0,0,0.18);
        overflow: hidden;
        position: relative;
      }

      .river-radar-section::before {
        content: "";
        position: absolute;
        width: 340px;
        height: 340px;
        border-radius: 50%;
        right: -160px;
        top: -180px;
        background:
          radial-gradient(
            circle,
            rgba(54,174,224,0.14),
            transparent 68%
          );
        pointer-events: none;
      }

      .river-radar-header {
        display: flex;
        justify-content: space-between;
        gap: 24px;
        align-items: flex-start;
        position: relative;
        z-index: 1;
      }

      .river-radar-kicker {
        margin-bottom: 7px;
        font-size: 11px;
        font-weight: 800;
        letter-spacing: 0.16em;
        color: rgba(255,255,255,0.55);
      }

      .river-radar-title {
        margin: 0;
        color: #ffffff;
        font-size: 24px;
        line-height: 1.15;
        letter-spacing: -0.02em;
      }

      .river-radar-subtitle {
        margin-top: 8px;
        max-width: 640px;
        color: rgba(255,255,255,0.62);
        font-size: 13px;
        line-height: 1.5;
      }

      .river-radar-live {
        flex: 0 0 auto;
        display: inline-flex;
        align-items: center;
        gap: 7px;
        padding: 8px 11px;
        border-radius: 999px;
        background: rgba(255,255,255,0.07);
        color: rgba(255,255,255,0.72);
        font-size: 11px;
        font-weight: 700;
        white-space: nowrap;
      }

      .river-radar-live-dot {
        width: 7px;
        height: 7px;
        border-radius: 50%;
        background: #5bd18b;
        box-shadow: 0 0 0 5px rgba(91,209,139,0.10);
      }

      .river-radar-summary {
        margin-top: 22px;
        padding: 16px 18px;
        border-radius: 16px;
        background: rgba(255,255,255,0.055);
        border: 1px solid rgba(255,255,255,0.07);
        color: rgba(255,255,255,0.86);
        font-size: 14px;
        line-height: 1.55;
        position: relative;
        z-index: 1;
      }

      .river-radar-summary strong {
        color: #ffffff;
      }

      .river-radar-direction {
        margin-top: 24px;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 10px;
        color: rgba(255,255,255,0.43);
        font-size: 9px;
        font-weight: 800;
        letter-spacing: 0.14em;
        text-transform: uppercase;
        position: relative;
        z-index: 2;
      }

      .river-radar-direction-arrow {
        width: 78px;
        height: 1px;
        position: relative;
        background: rgba(100,190,222,0.44);
      }

      .river-radar-direction-arrow::after {
        content: "";
        position: absolute;
        right: -1px;
        top: -3px;
        width: 6px;
        height: 6px;
        border-top: 1px solid rgba(100,190,222,0.70);
        border-right: 1px solid rgba(100,190,222,0.70);
        transform: rotate(45deg);
      }

      .river-radar-track {
        position: relative;
        display: grid;
        grid-template-columns: repeat(5, minmax(0, 1fr));
        gap: 12px;
        margin-top: 8px;
        padding-top: 18px;
        z-index: 1;
      }

      .river-radar-line {
        position: absolute;
        left: 9%;
        right: 9%;
        top: 34px;
        height: 3px;
        border-radius: 999px;
        background:
          linear-gradient(
            90deg,
            rgba(101,174,214,0.26),
            rgba(83,190,215,0.65),
            rgba(101,174,214,0.26)
          );
      }

      .river-radar-flow {
        position: absolute;
        left: 9%;
        right: 9%;
        top: 28px;
        display: flex;
        justify-content: space-around;
        color: rgba(255,255,255,0.30);
        font-size: 14px;
        pointer-events: none;
      }

      .river-radar-station {
        position: relative;
        text-align: center;
        min-width: 0;
      }

      .river-radar-node-wrap {
        height: 34px;
        display: flex;
        justify-content: center;
        align-items: center;
        position: relative;
        z-index: 2;
      }

      .river-radar-node {
        width: 18px;
        height: 18px;
        border-radius: 50%;
        background: #718090;
        border: 4px solid #102b43;
        box-shadow: 0 0 0 3px rgba(255,255,255,0.10);
      }

      .river-radar-station.up .river-radar-node {
        background: #4dd58a;
        box-shadow:
          0 0 0 3px rgba(77,213,138,0.15),
          0 0 18px rgba(77,213,138,0.30);
      }

      .river-radar-station.down .river-radar-node {
        background: #ef6b72;
        box-shadow:
          0 0 0 3px rgba(239,107,114,0.14),
          0 0 18px rgba(239,107,114,0.20);
      }

      .river-radar-station.stable .river-radar-node {
        background: #eab85a;
        box-shadow:
          0 0 0 3px rgba(234,184,90,0.14),
          0 0 18px rgba(234,184,90,0.20);
      }

      .river-radar-card {
        margin-top: 9px;
        padding: 15px 10px 13px;
        min-height: 177px;
        border-radius: 16px;
        background: rgba(255,255,255,0.045);
        border: 1px solid rgba(255,255,255,0.065);
        position: relative;
      }

      .river-radar-station.barcelos .river-radar-card {
        background: rgba(74,164,214,0.10);
        border-color: rgba(91,183,231,0.30);
        box-shadow:
          inset 0 0 0 1px rgba(91,183,231,0.04);
      }

      .river-radar-destination {
        position: absolute;
        top: 9px;
        right: 9px;
        padding: 4px 7px;
        border-radius: 999px;
        background: rgba(74,164,214,0.18);
        border: 1px solid rgba(91,183,231,0.25);
        color: rgba(190,230,250,0.90);
        font-size: 8px;
        font-weight: 800;
        letter-spacing: 0.10em;
        text-transform: uppercase;
      }

      .river-radar-name {
        color: #ffffff;
        font-size: 13px;
        font-weight: 800;
        line-height: 1.2;
      }

      .river-radar-code {
        margin-top: 3px;
        color: rgba(255,255,255,0.36);
        font-size: 9px;
        font-weight: 600;
      }

      .river-radar-time {
        margin-top: 6px;
        color: rgba(255,255,255,0.48);
        font-size: 9px;
        font-weight: 600;
      }

      .river-radar-time strong {
        color: rgba(255,255,255,0.73);
        font-weight: 700;
      }

      .river-radar-main-value {
        margin-top: 13px;
        color: #ffffff;
        font-size: 23px;
        line-height: 1;
        font-weight: 800;
        letter-spacing: -0.04em;
      }

      .river-radar-main-label {
        margin-top: 5px;
        color: rgba(255,255,255,0.45);
        font-size: 9px;
        font-weight: 700;
        letter-spacing: 0.06em;
        text-transform: uppercase;
      }

      .river-radar-mini {
        display: flex;
        justify-content: center;
        gap: 8px;
        margin-top: 12px;
        color: rgba(255,255,255,0.62);
        font-size: 10px;
      }

      .river-radar-mini span {
        white-space: nowrap;
      }

      .river-radar-status {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        margin-top: 10px;
        padding: 5px 8px;
        border-radius: 999px;
        background: rgba(255,255,255,0.06);
        color: rgba(255,255,255,0.72);
        font-size: 9px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.04em;
      }

      .river-radar-footer {
        margin-top: 20px;
        padding-top: 16px;
        border-top: 1px solid rgba(255,255,255,0.07);
        display: flex;
        justify-content: space-between;
        gap: 20px;
        color: rgba(255,255,255,0.44);
        font-size: 10px;
        line-height: 1.45;
      }

      .river-radar-footer strong {
        color: rgba(255,255,255,0.65);
      }

      .river-radar-loading {
        padding: 36px 10px 20px;
        text-align: center;
        color: rgba(255,255,255,0.55);
        font-size: 13px;
      }

      @media (max-width: 760px) {
        .river-radar-section {
          padding: 22px 16px;
          border-radius: 20px;
        }

        .river-radar-header {
          display: block;
        }

        .river-radar-live {
          margin-top: 13px;
        }

        .river-radar-title {
          font-size: 21px;
        }

        .river-radar-direction {
          justify-content: flex-start;
          margin: 22px 0 11px 8px;
          gap: 7px;
        }

        .river-radar-direction-arrow {
          width: 34px;
        }

        .river-radar-track {
          display: block;
          margin-top: 0;
          padding-top: 0;
          padding-left: 4px;
        }

        .river-radar-line {
          left: 15px;
          right: auto;
          top: 16px;
          bottom: 16px;
          width: 3px;
          height: auto;
        }

        .river-radar-flow {
          display: none;
        }

        .river-radar-station {
          display: grid;
          grid-template-columns: 32px minmax(0, 1fr);
          gap: 10px;
          text-align: left;
          margin-bottom: 11px;
        }

        .river-radar-node-wrap {
          height: 100%;
          min-height: 100px;
          justify-content: flex-start;
          align-items: flex-start;
          padding-top: 18px;
          z-index: 2;
        }

        .river-radar-node {
          margin-left: 3px;
        }

        .river-radar-card {
          margin-top: 0;
          min-height: auto;
          padding: 14px 15px;
        }

        .river-radar-main-value {
          margin-top: 11px;
          font-size: 22px;
        }

        .river-radar-mini {
          justify-content: flex-start;
          flex-wrap: wrap;
        }

        .river-radar-footer {
          display: block;
        }

        .river-radar-footer > div + div {
          margin-top: 7px;
        }
      }
    `;

    document.head.appendChild(style);
  }


  // ========================================================
  // AUXILIARES
  // ========================================================

  function number(value) {
    const parsed = Number(value);

    return Number.isFinite(parsed)
      ? parsed
      : null;
  }


  function formatSigned(value, decimals = 0) {
    const n = number(value);

    if (n === null) {
      return "—";
    }

    const formatted = n.toFixed(decimals);

    if (n > 0) {
      return `+${formatted} cm`;
    }

    return `${formatted} cm`;
  }


  function formatMeasurementTime(value) {
    if (!value || typeof value !== "string") {
      return "—";
    }

    const parts = value.trim().split(" ");

    if (parts.length < 2) {
      return value;
    }

    return parts[1].slice(0, 5) || "—";
  }


  function getDirection(station) {
    const variation72 = number(
      station.variacao_72h_cm
    );

    if (variation72 === null) {
      return {
        css: "stable",
        label: "sem leitura",
        icon: "•"
      };
    }

    if (variation72 >= 2) {
      return {
        css: "up",
        label: "alta em 72 h",
        icon: "↑"
      };
    }

    if (variation72 <= -2) {
      return {
        css: "down",
        label: "queda em 72 h",
        icon: "↓"
      };
    }

    return {
      css: "stable",
      label: "estável em 72 h",
      icon: "→"
    };
  }


  function stationMap(data) {
    const map = {};

    for (const station of data.estacoes || []) {
      map[String(station.estacao)] = station;
    }

    return map;
  }


  // ========================================================
  // RESUMO
  // ========================================================

  function buildSummary(stations) {
    const positive = [];

    for (const code of STATION_ORDER) {
      const station = stations[code];

      if (!station) {
        continue;
      }

      const variation72 = number(
        station.variacao_72h_cm
      );

      if (
        variation72 !== null &&
        variation72 >= 2
      ) {
        positive.push(station.nome);
      }
    }

    const barcelos =
      stations["14480002"];

    const barcelos6 =
      barcelos
        ? number(barcelos.variacao_6h_cm)
        : null;

    let text = "";

    if (positive.length) {
      text =
        `Alta acumulada em 72 h aparece em ` +
        `<strong>${positive.join(" e ")}</strong>.`;
    } else {
      text =
        `Nenhuma das estações monitoradas apresenta ` +
        `alta relevante acumulada em 72 h.`;
    }

    if (
      barcelos &&
      number(barcelos.variacao_72h_cm) !== null
    ) {
      const b72 = number(
        barcelos.variacao_72h_cm
      );

      if (b72 <= -2) {
        text +=
          ` Barcelos ainda registra ` +
          `<strong>${formatSigned(b72)} em 72 h</strong>.`;
      } else if (b72 >= 2) {
        text +=
          ` Barcelos já registra ` +
          `<strong>${formatSigned(b72)} em 72 h</strong>.`;
      } else {
        text +=
          ` Barcelos está praticamente estável em 72 h.`;
      }
    }

    if (
      barcelos6 !== null &&
      barcelos6 > 0
    ) {
      text +=
        ` No curto prazo, houve reação de ` +
        `<strong>${formatSigned(barcelos6)} ` +
        `nas últimas 6 h</strong>.`;
    }

    return text;
  }


  // ========================================================
  // CARTÃO DA ESTAÇÃO
  // ========================================================

  function stationHTML(code, station) {
    if (!station) {
      return `
        <div class="river-radar-station stable">
          <div class="river-radar-node-wrap">
            <div class="river-radar-node"></div>
          </div>

          <div class="river-radar-card">
            <div class="river-radar-name">
              ${STATION_LABELS[code]}
            </div>

            <div class="river-radar-code">
              ANA ${code}
            </div>

            <div class="river-radar-time">
              Leitura: <strong>—</strong>
            </div>

            <div class="river-radar-main-value">
              —
            </div>

            <div class="river-radar-main-label">
              sem dados
            </div>
          </div>
        </div>
      `;
    }

    const direction = getDirection(station);

    const isBarcelos =
      code === "14480002";

    const specialClass =
      isBarcelos
        ? " barcelos"
        : "";

    const destinationBadge =
      isBarcelos
        ? `<div class="river-radar-destination">DESTINO</div>`
        : "";

    const measurementTime =
      formatMeasurementTime(
        station.data_medicao_manaus
      );

    return `
      <div
        class="river-radar-station ${direction.css}${specialClass}"
      >

        <div class="river-radar-node-wrap">
          <div class="river-radar-node"></div>
        </div>

        <div class="river-radar-card">

          ${destinationBadge}

          <div class="river-radar-name">
            ${station.nome || STATION_LABELS[code]}
          </div>

          <div class="river-radar-code">
            ANA ${code}
          </div>

          <div class="river-radar-time">
            Leitura:
            <strong>${measurementTime}</strong>
          </div>

          <div class="river-radar-main-value">
            ${formatSigned(station.variacao_72h_cm)}
          </div>

          <div class="river-radar-main-label">
            variação em 72 h
          </div>

          <div class="river-radar-mini">
            <span>
              6 h:
              ${formatSigned(station.variacao_6h_cm)}
            </span>

            <span>
              24 h:
              ${formatSigned(station.variacao_24h_cm)}
            </span>
          </div>

          <div class="river-radar-status">
            ${direction.icon}
            ${direction.label}
          </div>

        </div>

      </div>
    `;
  }


  // ========================================================
  // ESTRUTURA
  // ========================================================

  function createSection() {
    let section =
      document.getElementById(
        "river-radar-section"
      );

    if (section) {
      return section;
    }

    section =
      document.createElement("section");

    section.id =
      "river-radar-section";

    section.className =
      "river-radar-section";

    section.innerHTML = `
      <div class="river-radar-header">

        <div>

          <div class="river-radar-kicker">
            RADAR DO RIO NEGRO
          </div>

          <h2 class="river-radar-title">
            Onde o movimento está acontecendo
          </h2>

          <div class="river-radar-subtitle">
            Leitura conjunta das cinco estações,
            de montante para jusante, usando
            principalmente a variação acumulada
            das últimas 72 horas.
          </div>

        </div>

        <div class="river-radar-live">
          <span class="river-radar-live-dot"></span>
          DADOS ANA
        </div>

      </div>


      <div
        id="river-radar-summary"
        class="river-radar-summary"
      >
        Analisando o corredor do Rio Negro...
      </div>


      <div class="river-radar-direction">
        <span>MONTANTE</span>
        <span class="river-radar-direction-arrow"></span>
        <span>JUSANTE</span>
      </div>


      <div
        id="river-radar-content"
        class="river-radar-loading"
      >
        Carregando estações...
      </div>


      <div class="river-radar-footer">

        <div>
          <strong>Leitura:</strong>
          verde = alta em 72 h •
          vermelho = queda em 72 h •
          amarelo = estabilidade
        </div>

        <div>
          Os níveis absolutos são referências
          locais de cada estação e
          <strong>
            não devem ser comparados diretamente entre si.
          </strong>
        </div>

      </div>
    `;

    const upstreamSection =
      document.querySelector(
        ".upstream-section"
      );

    if (upstreamSection) {
      upstreamSection.insertAdjacentElement(
        "afterend",
        section
      );
    } else {
      const dashboard =
        document.querySelector(
          ".dashboard"
        );

      if (dashboard) {
        dashboard.appendChild(section);
      }
    }

    return section;
  }


  // ========================================================
  // RENDERIZAÇÃO
  // ========================================================

  function render(data) {
    const stations =
      stationMap(data);

    const summary =
      document.getElementById(
        "river-radar-summary"
      );

    const content =
      document.getElementById(
        "river-radar-content"
      );

    if (!summary || !content) {
      return;
    }

    summary.innerHTML =
      buildSummary(stations);

    content.className =
      "river-radar-track";

    content.innerHTML = `
      <div class="river-radar-line"></div>

      <div class="river-radar-flow">
        <span>›</span>
        <span>›</span>
        <span>›</span>
        <span>›</span>
      </div>

      ${STATION_ORDER.map(
        (code) =>
          stationHTML(
            code,
            stations[code]
          )
      ).join("")}
    `;
  }


  // ========================================================
  // CARREGAMENTO
  // ========================================================

  async function loadRadar() {
    try {
      const response =
        await fetch(
          `${DATA_URL}?t=${Date.now()}`,
          {
            cache: "no-store"
          }
        );

      if (!response.ok) {
        throw new Error(
          `HTTP ${response.status}`
        );
      }

      const data =
        await response.json();

      render(data);

    } catch (error) {
      const content =
        document.getElementById(
          "river-radar-content"
        );

      const summary =
        document.getElementById(
          "river-radar-summary"
        );

      if (summary) {
        summary.textContent =
          "Não foi possível atualizar o radar agora.";
      }

      if (content) {
        content.className =
          "river-radar-loading";

        content.textContent =
          "Os demais módulos do painel continuam funcionando normalmente.";
      }

      console.error(
        "Erro ao carregar Radar do Rio Negro:",
        error
      );
    }
  }


  // ========================================================
  // INICIALIZAÇÃO
  // ========================================================

  function init() {
    installStyles();

    createSection();

    loadRadar();

    window.setInterval(
      loadRadar,
      REFRESH_MS
    );
  }


  if (
    document.readyState === "loading"
  ) {
    document.addEventListener(
      "DOMContentLoaded",
      init
    );
  } else {
    init();
  }

})();
