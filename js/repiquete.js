const REPIQUETE_URL =
  "data/repiquete.json";

let repiqueteData = null;


/* =========================
   FORMATAÇÃO
========================= */

function repiqueteFormatVariation(
  value
) {
  if (
    value === null ||
    value === undefined ||
    Number.isNaN(Number(value))
  ) {
    return "—";
  }

  const n =
    Number(value);

  if (n > 0) {
    return (
      `+${Math.abs(n)
        .toFixed(1)
        .replace(".", ",")} cm`
    );
  }

  if (n < 0) {
    return (
      `-${Math.abs(n)
        .toFixed(1)
        .replace(".", ",")} cm`
    );
  }

  return "0 cm";
}


function repiqueteFormatDateTime(
  value
) {
  if (!value) {
    return "—";
  }

  const [
    datePart,
    timePart = ""
  ] =
    String(value)
      .split(" ");

  const parts =
    datePart.split("-");

  if (
    parts.length !== 3
  ) {
    return String(value);
  }

  return (
    `${parts[2]}/` +
    `${parts[1]} ` +
    `${timePart.slice(0, 5)}`
  );
}


function repiqueteLocalizeReason(
  value
) {
  return String(
    value || ""
  ).replace(
    /([+-]?\d+)\.(\d+)/g,
    "$1,$2"
  );
}


function repiqueteUpstreamText(
  count
) {
  if (count === 0) {
    return (
      "Nenhuma estação a montante " +
      "com alta em 72 h"
    );
  }

  if (count === 1) {
    return (
      "1 estação a montante " +
      "com alta em 72 h"
    );
  }

  return (
    `${count} estações a montante ` +
    `com alta em 72 h`
  );
}


/* =========================
   INSERIR PAINEL
========================= */

function repiqueteInsertPanel() {
  if (
    document.getElementById(
      "repiquete-card"
    )
  ) {
    return;
  }

  const alertCard =
    document.getElementById(
      "alert-card"
    );

  if (!alertCard) {
    return;
  }

  alertCard.insertAdjacentHTML(
    "afterend",
    `
      <section
        id="repiquete-card"
        class="
          repiquete-card
          repiquete-loading
        "
      >

        <div class="repiquete-header">

          <div>

            <div class="section-label">
              DETECTOR DE REPIQUETE
            </div>

            <h2>
              Mudança de tendência em Barcelos
            </h2>

            <div class="repiquete-subtitle">
              Acompanhamento experimental da
              transição de vazante para alta.
            </div>

          </div>


          <div
            id="repiquete-badge"
            class="repiquete-badge"
          >
            ANALISANDO
          </div>

        </div>


        <div class="repiquete-progress">

          <div
            class="repiquete-stage"
            data-level="0"
          >
            <div class="repiquete-stage-dot">
              0
            </div>

            <div class="repiquete-stage-label">
              Sem sinal
            </div>
          </div>


          <div
            class="repiquete-stage"
            data-level="1"
          >
            <div class="repiquete-stage-dot">
              1
            </div>

            <div class="repiquete-stage-label">
              Sinal a montante
            </div>
          </div>


          <div
            class="repiquete-stage"
            data-level="2"
          >
            <div class="repiquete-stage-dot">
              2
            </div>

            <div class="repiquete-stage-label">
              Possível reversão
            </div>
          </div>


          <div
            class="repiquete-stage"
            data-level="3"
          >
            <div class="repiquete-stage-dot">
              3
            </div>

            <div class="repiquete-stage-label">
              Em formação
            </div>
          </div>


          <div
            class="repiquete-stage"
            data-level="4"
          >
            <div class="repiquete-stage-dot">
              4
            </div>

            <div class="repiquete-stage-label">
              Confirmado
            </div>
          </div>

        </div>


        <div class="repiquete-main-grid">

          <div class="repiquete-message-card">

            <div
              id="repiquete-title"
              class="repiquete-title"
            >
              Analisando comportamento...
            </div>

            <div
              id="repiquete-message"
              class="repiquete-message"
            >
              Comparando Barcelos com o comportamento
              recente das estações a montante.
            </div>


            <div
              id="repiquete-reasons"
              class="repiquete-reasons"
            ></div>

          </div>


          <div class="repiquete-metrics">

            <div class="repiquete-metric">

              <div class="repiquete-metric-label">
                BARCELOS • 6 H
              </div>

              <div
                id="repiquete-b6"
                class="repiquete-metric-value"
              >
                —
              </div>

            </div>


            <div class="repiquete-metric">

              <div class="repiquete-metric-label">
                BARCELOS • 24 H
              </div>

              <div
                id="repiquete-b24"
                class="repiquete-metric-value"
              >
                —
              </div>

            </div>


            <div class="repiquete-metric">

              <div class="repiquete-metric-label">
                BARCELOS • 72 H
              </div>

              <div
                id="repiquete-b72"
                class="repiquete-metric-value"
              >
                —
              </div>

            </div>


            <div class="repiquete-metric">

              <div class="repiquete-metric-label">
                BARCELOS • 7 DIAS
              </div>

              <div
                id="repiquete-b7d"
                class="repiquete-metric-value"
              >
                —
              </div>

            </div>

          </div>

        </div>


        <div class="repiquete-context-grid">

          <div class="repiquete-context-card">

            <div class="repiquete-context-label">
              SINAL A MONTANTE
            </div>

            <div
              id="repiquete-upstream"
              class="repiquete-context-value"
            >
              —
            </div>

            <div
              id="repiquete-upstream-detail"
              class="repiquete-context-detail"
            >
              —
            </div>

          </div>


          <div class="repiquete-context-card">

            <div class="repiquete-context-label">
              CONFIRMAÇÃO EM BARCELOS
            </div>

            <div
              id="repiquete-confirmation"
              class="repiquete-context-value"
            >
              —
            </div>

            <div class="repiquete-context-detail">
              +3 cm/24 h em 3 verificações
              consecutivas, separadas por 6 h
            </div>

          </div>


          <div class="repiquete-context-card">

            <div class="repiquete-context-label">
              ÚLTIMO CHECKPOINT DO DETECTOR
            </div>

            <div
              id="repiquete-last-checkpoint"
              class="repiquete-context-value"
            >
              —
            </div>

            <div
              id="repiquete-last-checkpoint-detail"
              class="repiquete-context-detail"
            >
              —
            </div>

          </div>

        </div>


        <div class="repiquete-note">

          As métricas de Barcelos usam a leitura mais
          recente da ANA. O checkpoint do detector usa
          a série horária fechada nos horários 00, 06,
          12 e 18 h; por isso os valores podem diferir
          ligeiramente. “Possível reversão” e
          “repiquete em formação” não significam
          confirmação. O estado confirmado exige
          persistência da alta observada em Barcelos
          e não representa previsão futura.

        </div>

      </section>
    `
  );
}


/* =========================
   CLASSES DE VARIAÇÃO
========================= */

function repiqueteVariationClass(
  value
) {
  const n =
    Number(value);

  if (
    !Number.isFinite(n) ||
    n === 0
  ) {
    return "neutral";
  }

  return (
    n > 0
      ? "positive"
      : "negative"
  );
}


/* =========================
   PROGRESSO
========================= */

function repiqueteRenderProgress(
  level
) {
  const stages =
    document.querySelectorAll(
      ".repiquete-stage"
    );

  stages.forEach(
    stage => {
      const stageLevel =
        Number(
          stage.dataset.level
        );

      stage.classList.remove(
        "active",
        "reached"
      );

      if (
        stageLevel < level
      ) {
        stage.classList.add(
          "reached"
        );
      }

      if (
        stageLevel === level
      ) {
        stage.classList.add(
          "active"
        );
      }
    }
  );
}


/* =========================
   MÉTRICAS
========================= */

function repiqueteSetMetric(
  id,
  value
) {
  const element =
    document.getElementById(
      id
    );

  if (!element) {
    return;
  }

  element.textContent =
    repiqueteFormatVariation(
      value
    );

  element.classList.remove(
    "positive",
    "negative",
    "neutral"
  );

  element.classList.add(
    repiqueteVariationClass(
      value
    )
  );
}


/* =========================
   RENDER
========================= */

function repiqueteRender(
  data
) {
  repiqueteData =
    data;

  const card =
    document.getElementById(
      "repiquete-card"
    );

  if (!card) {
    return;
  }

  const level =
    Number(
      data.nivel ?? 0
    );

  card.classList.remove(
    "repiquete-loading",
    "repiquete-level-0",
    "repiquete-level-1",
    "repiquete-level-2",
    "repiquete-level-3",
    "repiquete-level-4"
  );

  card.classList.add(
    `repiquete-level-${level}`
  );


  const badge =
    document.getElementById(
      "repiquete-badge"
    );

  const title =
    document.getElementById(
      "repiquete-title"
    );

  const message =
    document.getElementById(
      "repiquete-message"
    );

  if (badge) {
    badge.textContent =
      data.rotulo ||
      "SEM INFORMAÇÃO";
  }

  if (title) {
    title.textContent =
      data.titulo ||
      "Situação indisponível";
  }

  if (message) {
    message.textContent =
      data.mensagem ||
      "Sem mensagem disponível.";
  }


  repiqueteRenderProgress(
    level
  );


  const barcelos =
    data
      .situacao_atual
      ?.barcelos ||
    {};

  repiqueteSetMetric(
    "repiquete-b6",
    barcelos
      .variacao_6h_cm
  );

  repiqueteSetMetric(
    "repiquete-b24",
    barcelos
      .variacao_24h_cm
  );

  repiqueteSetMetric(
    "repiquete-b72",
    barcelos
      .variacao_72h_cm
  );

  repiqueteSetMetric(
    "repiquete-b7d",
    barcelos
      .variacao_7d_cm
  );


  const reasons =
    document.getElementById(
      "repiquete-reasons"
    );

  if (reasons) {
    const items =
      data.motivos ||
      [];

    reasons.innerHTML =
      items.length
        ? items
            .map(
              reason => `
                <div class="repiquete-reason">
                  ${repiqueteLocalizeReason(
                    reason
                  )}
                </div>
              `
            )
            .join("")
        : `
            <div class="repiquete-reason">
              Nenhum motivo adicional registrado.
            </div>
          `;
  }


  const upstream =
    data
      .contexto_montante ||
    {};

  const upstreamValue =
    document.getElementById(
      "repiquete-upstream"
    );

  const upstreamDetail =
    document.getElementById(
      "repiquete-upstream-detail"
    );

  if (upstreamValue) {
    upstreamValue.textContent =
      upstream.sinal
        ? "PRESENTE"
        : "NÃO IDENTIFICADO";
  }

  if (upstreamDetail) {
    const count =
      Number(
        upstream
          .estacoes_positivas_72h ??
        0
      );

    upstreamDetail.textContent =
      repiqueteUpstreamText(
        count
      );
  }


  const confirmation =
    document.getElementById(
      "repiquete-confirmation"
    );

  const event =
    data
      .evento_barcelos ||
    {};

  if (confirmation) {
    confirmation.textContent =
      event.confirmado
        ? "CONFIRMADO"
        : "AINDA NÃO";
  }


  const checkpoints =
    data
      .ultimos_checkpoints_barcelos ||
    [];

  const latestCheckpoint =
    checkpoints.length
      ? checkpoints[
          checkpoints.length - 1
        ]
      : null;

  const checkpointValue =
    document.getElementById(
      "repiquete-last-checkpoint"
    );

  const checkpointDetail =
    document.getElementById(
      "repiquete-last-checkpoint-detail"
    );

  if (
    checkpointValue &&
    latestCheckpoint
  ) {
    checkpointValue.textContent =
      repiqueteFormatDateTime(
        latestCheckpoint
          .hora_manaus
      );
  }

  if (
    checkpointDetail &&
    latestCheckpoint
  ) {
    checkpointDetail.textContent =
      (
        `série horária • ` +
        `6 h: ` +
        `${repiqueteFormatVariation(
          latestCheckpoint
            .variacao_6h_cm
        )} • ` +
        `24 h: ` +
        `${repiqueteFormatVariation(
          latestCheckpoint
            .variacao_24h_cm
        )}`
      );
  }
}


/* =========================
   ERRO
========================= */

function repiqueteRenderUnavailable() {
  const card =
    document.getElementById(
      "repiquete-card"
    );

  if (!card) {
    return;
  }

  const badge =
    document.getElementById(
      "repiquete-badge"
    );

  const title =
    document.getElementById(
      "repiquete-title"
    );

  const message =
    document.getElementById(
      "repiquete-message"
    );

  if (badge) {
    badge.textContent =
      "INDISPONÍVEL";
  }

  if (title) {
    title.textContent =
      "Detector temporariamente indisponível";
  }

  if (message) {
    message.textContent =
      (
        "Os demais dados do painel continuam " +
        "disponíveis, mas o detector de " +
        "repiquete não pôde ser carregado."
      );
  }
}


/* =========================
   CARREGAR
========================= */

async function repiqueteLoad() {
  try {
    const response =
      await fetch(
        (
          `${REPIQUETE_URL}` +
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

    repiqueteRender(
      data
    );

  } catch (error) {
    console.error(
      "Erro no detector de repiquete:",
      error
    );

    repiqueteRenderUnavailable();
  }
}


/* =========================
   INICIALIZAÇÃO
========================= */

document.addEventListener(
  "DOMContentLoaded",
  () => {
    repiqueteInsertPanel();

    repiqueteLoad();

    setInterval(
      repiqueteLoad,
      5 * 60 * 1000
    );
  }
);
