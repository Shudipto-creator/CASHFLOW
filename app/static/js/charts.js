/* CASHFLOW charts.js - draws charts from JSON data blocks. Requires Chart.js (vendored). */

const CHARTS = (() => {
  function getColor(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }
  const palette = [
    getColor("--color-chart-navy"),
    getColor("--color-chart-teal"),
    getColor("--color-chart-slate"),
    getColor("--color-chart-sand"),
  ];

  function moneyFormatter(locale, currency) {
    return new Intl.NumberFormat(locale, { style: "currency", currency });
  }

  function draw(canvas, spec) {
    const ctx = canvas.getContext("2d");
    const labels = spec.labels || [];
    const datasets = spec.datasets || [];
    const type = spec.type || "line";
    const options = {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      interaction: { mode: "index", intersect: false },
      plugins: { legend: { display: false }, tooltip: { mode: "index", intersect: false } },
      scales: {
        x: { grid: { display: false }, ticks: { color: getColor("--color-muted"), font: { size: 11 } } },
        y: { grid: { color: getColor("--color-border") }, ticks: { color: getColor("--color-muted"), font: { size: 11 }, callback: spec.tickFormatter || undefined } },
      },
    };
    return new Chart(ctx, { type, data: { labels, datasets }, options });
  }

  function init() {
    if (typeof Chart === "undefined") return;
    const blocks = document.querySelectorAll('script[type="application/json"][data-chart]');
    const instances = [];
    const themeMedia = window.matchMedia("(prefers-color-scheme: dark)");
    blocks.forEach((block) => {
      const targetId = block.getAttribute("data-target");
      const canvas = document.getElementById(targetId);
      if (!canvas) return;
      const spec = JSON.parse(block.textContent);
      const chart = draw(canvas, spec);
      instances.push(chart);
    });
    function redrawOnTheme() {
      instances.forEach((chart) => {
        chart.options.scales.x.ticks.color = getColor("--color-muted");
        chart.options.scales.y.ticks.color = getColor("--color-muted");
        chart.options.scales.y.grid.color = getColor("--color-border");
        chart.update();
      });
    }
    themeMedia.addEventListener("change", redrawOnTheme);
  }

  function waitForChart() {
    if (typeof Chart !== "undefined") { init(); return; }
    const timer = setInterval(() => {
      if (typeof Chart !== "undefined") { clearInterval(timer); init(); }
    }, 50);
    setTimeout(() => clearInterval(timer), 5000);
  }

  return { init: waitForChart };
})();

document.addEventListener("DOMContentLoaded", () => CHARTS.init());
