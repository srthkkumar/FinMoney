const API_BASE = "http://localhost:8000";

const ALLOCATION_LABELS = {
  conservative: "Conservative",
  balanced: "Balanced",
  aggressive: "Aggressive",
  custom: "Your mix",
};

const ALLOCATION_COLORS = {
  conservative: { line: "#3B6E8F", band: "59, 110, 143" },
  balanced:     { line: "#1F4B3F", band: "31, 75, 63" },
  aggressive:   { line: "#B8863A", band: "184, 134, 58" },
  custom:       { line: "#7A4FA3", band: "122, 79, 163" },
};

let latestResult = null;
let activeAllocation = "balanced";
let chartInstance = null;

const form = document.getElementById("plan-form");
const submitBtn = document.getElementById("submit-btn");
const resultsPanel = document.getElementById("results-panel");
const surplusLine = document.getElementById("surplus-line");
const tabsEl = document.getElementById("allocation-tabs");
const historyList = document.getElementById("history-list");

const useCustomCheckbox = document.getElementById("use-custom");
const sliderGrid = document.getElementById("slider-grid");
const equitySlider = document.getElementById("equity-slider");
const goldSlider = document.getElementById("gold-slider");
const equityValueEl = document.getElementById("equity-value");
const goldValueEl = document.getElementById("gold-value");
const debtValueEl = document.getElementById("debt-value");
const debtBarFill = document.getElementById("debt-bar-fill");

const skeletonState = document.getElementById("skeleton-state");
const resultsContent = document.getElementById("results-content");
const errorBanner = document.getElementById("error-banner");
const errorMessage = document.getElementById("error-message");

function updateSliderDisplay() {
  const equity = Number(equitySlider.value);
  const gold = Math.min(Number(goldSlider.value), 100 - equity);
  goldSlider.value = gold;
  const debt = 100 - equity - gold;

  equityValueEl.textContent = `${equity}%`;
  goldValueEl.textContent = `${gold}%`;
  debtValueEl.textContent = `${debt}%`;
  debtBarFill.style.width = `${debt}%`;
}

function getCustomAllocation() {
  if (!useCustomCheckbox.checked) return null;
  const equity = Number(equitySlider.value) / 100;
  const gold = Number(goldSlider.value) / 100;
  const debt = 1 - equity - gold;
  return { equity, debt: Math.max(debt, 0), gold };
}

useCustomCheckbox.addEventListener("change", () => {
  sliderGrid.hidden = !useCustomCheckbox.checked;
});
equitySlider.addEventListener("input", updateSliderDisplay);
goldSlider.addEventListener("input", updateSliderDisplay);
updateSliderDisplay();

function showLoading() {
  resultsPanel.hidden = false;
  errorBanner.hidden = true;
  resultsContent.hidden = true;
  skeletonState.hidden = false;
}

function showError(message) {
  skeletonState.hidden = true;
  resultsContent.hidden = true;
  errorBanner.hidden = false;
  errorMessage.textContent = message;
}

function showResults() {
  skeletonState.hidden = true;
  errorBanner.hidden = true;
  resultsContent.hidden = false;
}

function formatRupees(n) {
  const abs = Math.abs(n);
  if (abs >= 1e7) return "₹" + (n / 1e7).toFixed(2) + " Cr";
  if (abs >= 1e5) return "₹" + (n / 1e5).toFixed(2) + " L";
  return "₹" + Math.round(n).toLocaleString("en-IN");
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();

  const payload = {
    current_age: Number(document.getElementById("current_age").value),
    retirement_age: Number(document.getElementById("retirement_age").value),
    monthly_income: Number(document.getElementById("monthly_income").value),
    monthly_expenses: Number(document.getElementById("monthly_expenses").value),
    current_savings: Number(document.getElementById("current_savings").value),
    monthly_sip: Number(document.getElementById("monthly_sip").value),
    custom_allocation: getCustomAllocation(),
  };

  if (payload.retirement_age <= payload.current_age) {
    showError("Retirement age must be greater than your current age.");
    resultsPanel.hidden = false;
    return;
  }

  submitBtn.disabled = true;
  submitBtn.textContent = "Simulating 2,000 futures…";
  showLoading();

  try {
    const res = await fetch(`${API_BASE}/api/simulate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      const detail = Array.isArray(err.detail)
        ? err.detail.map((d) => d.msg).join(", ")
        : err.detail;
      throw new Error(detail || `Request failed (${res.status})`);
    }

    latestResult = await res.json();
    if (!latestResult.allocations[activeAllocation]) {
      activeAllocation = "balanced";
    }
    showResults();
    renderResults(latestResult, payload);
    loadHistory();
  } catch (err) {
    showError(
      `Couldn't reach the planning engine at ${API_BASE}. ` +
        `Make sure the backend is running (see README). Details: ${err.message}`
    );
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "Run 2,000 simulations";
  }
});

function renderResults(result, inputs) {
  resultsPanel.hidden = false;

  const surplus = result.monthly_surplus;
  surplusLine.textContent =
    surplus >= 0
      ? `You're running a monthly surplus of ${formatRupees(surplus)} beyond your SIP.`
      : `Your expenses + SIP currently exceed your income by ${formatRupees(-surplus)}/month — the plan below assumes you close that gap.`;

  renderTabs(result);
  renderChart(result, activeAllocation);
  renderCorpusTable(result);
  renderLeverTable(result.lever_analysis);

  resultsPanel.scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderTabs(result) {
  tabsEl.innerHTML = "";
  Object.keys(result.allocations).forEach((key) => {
    const btn = document.createElement("button");
    btn.className = "tab-btn" + (key === activeAllocation ? " active" : "");
    btn.textContent = ALLOCATION_LABELS[key] || key;
    btn.setAttribute("role", "tab");
    btn.addEventListener("click", () => {
      activeAllocation = key;
      [...tabsEl.children].forEach((c) => c.classList.remove("active"));
      btn.classList.add("active");
      renderChart(latestResult, activeAllocation);
    });
    tabsEl.appendChild(btn);
  });
}

function renderChart(result, allocationKey) {
  const alloc = result.allocations[allocationKey];
  const years = result.years;
  const colors = ALLOCATION_COLORS[allocationKey];
  const pp = alloc.path_percentiles;

  const datasets = [
    {
      label: "p95",
      data: pp.p95,
      borderWidth: 0,
      pointRadius: 0,
      fill: false,
    },
    {
      label: "5th–95th",
      data: pp.p5,
      borderWidth: 0,
      pointRadius: 0,
      backgroundColor: `rgba(${colors.band}, 0.16)`,
      fill: "-1",
    },
    {
      label: "p75",
      data: pp.p75,
      borderWidth: 0,
      pointRadius: 0,
      fill: false,
    },
    {
      label: "25th–75th",
      data: pp.p25,
      borderWidth: 0,
      pointRadius: 0,
      backgroundColor: `rgba(${colors.band}, 0.32)`,
      fill: "-1",
    },
    {
      label: "Median",
      data: pp.p50,
      borderColor: colors.line,
      borderWidth: 2.5,
      pointRadius: 0,
      fill: false,
      tension: 0.15,
    },
  ];

  if (chartInstance) chartInstance.destroy();
  const ctx = document.getElementById("fan-chart").getContext("2d");
  chartInstance = new Chart(ctx, {
    type: "line",
    data: { labels: years, datasets },
    options: {
      responsive: true,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) =>
              ctx.dataset.label === "Median"
                ? `Median: ${formatRupees(ctx.parsed.y)}`
                : null,
            title: (items) => `Age ${items[0].label}`,
          },
          filter: (item) => item.dataset.label === "Median",
        },
      },
      scales: {
        x: { title: { display: true, text: "Age" }, grid: { display: false } },
        y: {
          title: { display: true, text: "Portfolio value" },
          ticks: { callback: (v) => formatRupees(v) },
          grid: { color: "#EDEAE0" },
        },
      },
    },
  });
}

function renderCorpusTable(result) {
  const table = document.getElementById("corpus-table");
  const rows = ["p5", "p25", "p50", "p75", "p95"];
  const rowLabels = {
    p5: "1-in-20 poor market",
    p25: "Below-average market",
    p50: "Median",
    p75: "Above-average market",
    p95: "1-in-20 strong market",
  };

  let html = "<tr><th>Scenario</th>";
  Object.keys(result.allocations).forEach((key) => {
    html += `<th>${ALLOCATION_LABELS[key]}</th>`;
  });
  html += "</tr>";

  rows.forEach((p) => {
    html += `<tr><td>${rowLabels[p]}</td>`;
    Object.keys(result.allocations).forEach((key) => {
      const val = result.allocations[key].final_corpus_percentiles[p];
      const cls = p === "p50" ? "figure median-figure" : "figure";
      html += `<td class="${cls}">${formatRupees(val)}</td>`;
    });
    html += "</tr>";
  });

  table.innerHTML = html;
}

function renderLeverTable(lever) {
  const table = document.getElementById("lever-table");
  let html = "<tr><th>Extra monthly investment</th><th>Median corpus at retirement</th></tr>";
  lever.points.forEach((pt) => {
    html += `<tr><td>${pt.extra_monthly === 0 ? "Your current plan" : "+" + formatRupees(pt.extra_monthly) + "/mo"}</td><td class="figure median-figure">${formatRupees(pt.median_final_corpus)}</td></tr>`;
  });
  table.innerHTML = html;
}

async function loadHistory() {
  try {
    const res = await fetch(`${API_BASE}/api/history`);
    if (!res.ok) return;
    const runs = await res.json();
    if (!runs.length) return;

    historyList.innerHTML = "";
    runs.forEach((run) => {
      const li = document.createElement("li");
      const time = new Date(run.created_at).toLocaleTimeString();
      li.innerHTML = `<span>Run #${run.id} · age ${run.inputs.current_age} → ${run.inputs.retirement_age}, SIP ${formatRupees(run.inputs.monthly_sip)}/mo</span><span class="hl-meta">${time}</span>`;
      historyList.appendChild(li);
    });
  } catch (e) {
    // Silently ignore — history is a nice-to-have, not critical path.
  }
}

loadHistory();
