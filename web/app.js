// Observatoire de la sécheresse au Maroc - web dashboard
// Reads the JSON files exported from the warehouse by scripts/11_export_web.py

const CATEGORIES = [   // same classes and colours as DWH_DB.dbo.DimDroughtCategory (McKee 1993)
  { min: 2,    label: "Extrêmement humide",   color: "#1F4E9C" },
  { min: 1.5,  label: "Très humide",          color: "#3D7CC9" },
  { min: 1,    label: "Modérément humide",    color: "#8DB8E8" },
  { min: -1,   label: "Proche de la normale", color: "#D9D9D9" },
  { min: -1.5, label: "Sécheresse modérée",   color: "#F4C26B" },
  { min: -2,   label: "Sécheresse sévère",    color: "#E07B39" },
  { min: -99,  label: "Sécheresse extrême",   color: "#B3261E" },
];
const MONTHS_FR = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet", "Août",
                   "Septembre", "Octobre", "Novembre", "Décembre"];
const fmtInt = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 });
const fmt1 = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 1, minimumFractionDigits: 1 });
const fmt2 = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 2, minimumFractionDigits: 2 });

const category = v => v == null ? null : CATEGORIES.find(c => v >= c.min);
// diverging colour scale for the map: -2 red, 0 light grey, +2 blue (same as Power BI)
const mapColor = d3.scaleLinear().domain([-2, 0, 2]).range(["#B3261E", "#F2F2F2", "#1F4E9C"]).clamp(true);

let D = {};          // all data
let charts = {};

async function load() {
  const files = ["meta", "provinces", "spi12", "rain", "national", "dams"];
  const res = await Promise.all(files.map(f => fetch(`data/${f}.json`).then(r => r.json())));
  files.forEach((f, i) => (D[f] = res[i]));
  D.topo = await fetch("data/morocco.topojson").then(r => r.json());
  D.provIndex = new Map(D.provinces.map((p, i) => [p.name, i]));
  D.spiIndex = new Map(D.spi12.months.map((m, i) => [m, i]));
  D.rainIndex = new Map(D.rain.months.map((m, i) => [m, i]));
  D.damIndex = new Map(D.dams.months.map((m, i) => [m, i]));
}

function setupControls() {
  const last = D.spi12.months[D.spi12.months.length - 1];
  const years = [...new Set(D.spi12.months.map(m => +m.slice(0, 4)))];
  const ySel = document.getElementById("year"), mSel = document.getElementById("month");
  ySel.innerHTML = years.map(y => `<option>${y}</option>`).join("");
  ySel.value = last.slice(0, 4);
  const fillMonths = () => {
    const y = ySel.value;
    const avail = D.spi12.months.filter(m => m.startsWith(y)).map(m => +m.slice(5));
    const prev = +mSel.value || 99;
    mSel.innerHTML = avail.map(m => `<option value="${m}">${MONTHS_FR[m - 1]}</option>`).join("");
    mSel.value = avail.includes(prev) ? prev : avail[avail.length - 1];
  };
  fillMonths();
  ySel.addEventListener("change", () => { fillMonths(); update(); });
  mSel.addEventListener("change", update);
  const [m1, m2] = D.meta.spi_months;
  document.getElementById("updated").textContent =
    `Données jusqu'à ${MONTHS_FR[+last.slice(5) - 1].toLowerCase()} ${last.slice(0, 4)} · mise à jour le ${D.meta.updated}`;
}

const selected = () => {
  const y = document.getElementById("year").value;
  const m = String(document.getElementById("month").value).padStart(2, "0");
  return { y: +y, m: +m, key: `${y}-${m}` };
};

// ---------- indicators for the selected month ----------
function compute(sel) {
  const spiRow = D.spi12.values[D.spiIndex.get(sel.key)] || [];
  const prov = D.provinces.map((p, i) => ({ ...p, spi: spiRow[i] }));
  const withSpi = prov.filter(p => p.spi != null);
  const dry = withSpi.filter(p => p.spi <= -1);

  // rain from January to the selected month vs the normal of the same months (province average, then ratio)
  let rSum = 0, nSum = 0, nProv = 0;
  D.provinces.forEach((p, i) => {
    let r = 0, n = 0, ok = true;
    for (let mo = 1; mo <= sel.m; mo++) {
      const row = D.rain.values[D.rainIndex.get(`${sel.y}-${String(mo).padStart(2, "0")}`)];
      if (!row || row[i] == null) { ok = false; break; }
      r += row[i]; n += D.rain.normals[i][mo - 1];
    }
    if (ok) { rSum += r; nSum += n; nProv++; p._rainPct = n ? 100 * r / n : null; } else p._rainPct = null;
  });
  const rainPct = nProv && nSum ? 100 * rSum / nSum : null;

  // dams: each dam at its latest reliable month in the 12 months up to the selected one
  let water = 0, max = 0, used = 0;
  const end = D.damIndex.get(sel.key);
  if (end != null) {
    D.dams.dams.forEach((d, j) => {
      for (let t = end; t >= Math.max(0, end - 11); t--) {
        const v = D.dams.values[t][j];
        if (v != null) { water += v; max += d.max; used++; break; }
      }
    });
  }
  return { prov, withSpi, dry, rainPct, dams: used ? { pct: 100 * water / max, used, water } : null };
}

function update() {
  const sel = selected();
  const c = compute(sel);
  const label = `${MONTHS_FR[sel.m - 1].toLowerCase()} ${sel.y}`;

  document.getElementById("k-prov").textContent = c.withSpi.length ? `${fmt1.format(100 * c.dry.length / c.withSpi.length)} %` : "–";
  document.getElementById("k-prov-n").textContent = c.withSpi.length ? `${c.dry.length} sur ${c.withSpi.length} provinces (SPI-12 ≤ -1), ${label}` : "pas de données";
  const people = c.dry.reduce((s, p) => s + p.pop, 0);
  document.getElementById("k-people").textContent = c.withSpi.length ? `${fmt1.format(people / 1e6)} M` : "–";
  document.getElementById("k-rain").textContent = c.rainPct != null ? `${fmt1.format(c.rainPct)} %` : "–";
  document.getElementById("k-rain-n").textContent = `janvier → ${label}, moyenne des provinces (100 % = normal)`;
  document.getElementById("k-dams").textContent = c.dams ? `${fmt1.format(c.dams.pct)} %` : "–";
  document.getElementById("k-dams-n").textContent = c.dams
    ? `${fmt1.format(c.dams.water)} km² d'eau, ${c.dams.used} barrages, % de la plus grande surface observée`
    : "pas de mesure avant 2000";

  drawMap(c, label);
  drawTable(c);
  markCharts(sel);
}

// ---------- map ----------
let mapSvg, mapPaths;
function setupMap() {
  const el = document.getElementById("map");
  const geo = topojson.feature(D.topo, D.topo.objects.provinces);
  // A few tiny coastal slivers (left by map simplification, e.g. 72 of 1314 pieces of Oued Ed-Dahab)
  // are wound the wrong way; D3 then reads them as "the whole globe minus the piece" and paints the
  // full map. Reverse only those pieces.
  geo.features.forEach(f => {
    const polys = f.geometry.type === "Polygon" ? [f.geometry.coordinates] : f.geometry.coordinates;
    polys.forEach(p => {
      if (d3.geoArea({ type: "Polygon", coordinates: p }) > 2 * Math.PI) p.forEach(ring => ring.reverse());
    });
  });
  const w = 600, h = 630;
  const proj = d3.geoMercator().fitSize([w, h], geo);
  const path = d3.geoPath(proj);
  mapSvg = d3.select(el).append("svg").attr("viewBox", `0 0 ${w} ${h}`);
  mapPaths = mapSvg.append("g").selectAll("path").data(geo.features).join("path").attr("d", path);
  const tip = document.getElementById("tip");
  mapPaths
    .on("mousemove", (ev, f) => {
      const p = D._cur && D._cur.prov[D.provIndex.get(f.properties.ProvinceShort)];
      if (!p) return;
      const cat = category(p.spi);
      tip.innerHTML = `<b>${p.name}</b><br>${p.region}<br>SPI-12 : ${p.spi == null ? "–" : fmt2.format(p.spi)}` +
        (cat ? `<br>${cat.label}` : "") +
        (p._rainPct != null ? `<br>Pluie : ${fmt1.format(p._rainPct)} % de la normale` : "") +
        `<br>Population 2024 : ${fmtInt.format(p.pop)}`;
      const box = el.parentElement.getBoundingClientRect();
      tip.style.left = `${Math.min(ev.clientX - box.left + 12, box.width - 250)}px`;
      tip.style.top = `${ev.clientY - box.top + 12}px`;
      tip.hidden = false;
    })
    .on("mouseleave", () => (tip.hidden = true));
  document.getElementById("legend").innerHTML =
    [["#B3261E", "≤ -2 sécheresse extrême"], ["#E07B39", "-1,5"], ["#F4C26B", "-1 sécheresse"],
     ["#F2F2F2", "0 normal"], ["#8DB8E8", "+1 humide"], ["#1F4E9C", "≥ +2 très humide"], ["#BFBFBF", "pas de donnée"]]
      .map(([c, t]) => `<span><i style="background:${c};border:1px solid #ddd"></i>${t}</span>`).join("");
}

function drawMap(c) {
  D._cur = c;
  mapPaths.attr("fill", f => {
    const p = c.prov[D.provIndex.get(f.properties.ProvinceShort)];
    return p && p.spi != null ? mapColor(p.spi) : "#BFBFBF";
  });
}

// ---------- table ----------
function drawTable(c) {
  const rows = [...c.withSpi].sort((a, b) => a.spi - b.spi).slice(0, 12);
  document.querySelector("#table tbody").innerHTML = rows.map(p => {
    const cat = category(p.spi);
    const dark = ["#B3261E", "#1F4E9C", "#3D7CC9", "#E07B39"].includes(cat.color);
    return `<tr><td>${p.name}</td><td>${p.region.replace(/^Région (de |d'|du )?/, "")}</td>` +
      `<td class="num">${fmt2.format(p.spi)}</td>` +
      `<td><span class="badge" style="background:${cat.color};color:${dark ? "#fff" : "#252423"}">${cat.label}</span></td></tr>`;
  }).join("") || `<tr><td colspan="4">Pas de données pour ce mois.</td></tr>`;
}

// ---------- charts ----------
function setupCharts() {
  Chart.defaults.font.family = '"Segoe UI", system-ui, sans-serif';
  Chart.defaults.color = "#6b6a66";
  const common = { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } };

  // 1. national SPI-12 per month
  const nat = D.spi12.values.map(row => {
    const v = row.filter(x => x != null);
    return v.length ? v.reduce((a, b) => a + b, 0) / v.length : null;
  });
  charts.spi = new Chart(document.getElementById("c-spi"), {
    type: "bar",
    data: { labels: D.spi12.months, datasets: [{ data: nat, borderWidth: 0, categoryPercentage: 1, barPercentage: 1,
      backgroundColor: nat.map(v => v <= -1 ? "#B3261E" : v >= 1 ? "#1F4E9C" : "#BFBFBF") }] },
    options: { ...common, scales: { x: { ticks: { maxTicksLimit: 18, callback: (v, i) => D.spi12.months[i].slice(0, 4) }, grid: { display: false } },
      y: { suggestedMin: -2.5, suggestedMax: 2.5 } } },
  });

  // 2. yearly rain % of normal (full years only)
  const lastRain = D.meta.rain_months[1];
  const rainYears = D.national.filter(n => n.rain_pct != null && (n.year < +lastRain.slice(0, 4) || lastRain.endsWith("-12")));
  charts.rain = new Chart(document.getElementById("c-rain"), {
    type: "bar",
    data: { labels: rainYears.map(n => n.year), datasets: [{ data: rainYears.map(n => n.rain_pct),
      backgroundColor: rainYears.map(n => n.rain_pct < 80 ? "#B3261E" : n.rain_pct > 120 ? "#1F4E9C" : "#BFBFBF") }] },
    options: { ...common, scales: { y: { suggestedMin: 0, ticks: { callback: v => `${v} %` } }, x: { grid: { display: false } } } },
  });

  // 3. dams: total surface of reliable measurements (months where >= 20 dams are reliable)
  const tot = D.dams.values.map(row => {
    const v = row.filter(x => x != null);
    return v.length >= 20 ? v.reduce((a, b) => a + b, 0) : null;
  });
  charts.dams = new Chart(document.getElementById("c-dams"), {
    type: "line",
    data: { labels: D.dams.months, datasets: [{ data: tot, borderColor: "#1F4E9C", backgroundColor: "rgba(31,78,156,.12)",
      fill: true, pointRadius: 0, spanGaps: true, borderWidth: 1.6 }] },
    options: { ...common, scales: { x: { ticks: { maxTicksLimit: 14, callback: (v, i) => D.dams.months[i].slice(0, 4) }, grid: { display: false } } },
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: c => `${fmt1.format(c.parsed.y)} km² (≥ 20 barrages mesurés)` } } } },
  });

  // 4. wheat production + March NDVI
  const w = D.national.filter(n => n.wheat_t != null);
  charts.wheat = new Chart(document.getElementById("c-wheat"), {
    data: { labels: w.map(n => n.year), datasets: [
      { type: "bar", label: "Production de blé (Mt)", data: w.map(n => n.wheat_t / 1e6), backgroundColor: "#E0B85A", yAxisID: "y" },
      { type: "line", label: "Verdure des cultures en mars (NDVI)", data: w.map(n => n.ndvi_march), borderColor: "#2E7D4F",
        pointRadius: 2, yAxisID: "y1", tension: 0.2 }] },
    options: { ...common, plugins: { legend: { display: true, position: "bottom" } },
      scales: { y: { title: { display: true, text: "Mt" } }, y1: { position: "right", grid: { display: false }, title: { display: true, text: "NDVI" } },
        x: { grid: { display: false } } } },
  });

  // 5. temperature (full years)
  const t = D.national.filter(n => n.tmax_avg != null);
  charts.temp = new Chart(document.getElementById("c-temp"), {
    type: "line",
    data: { labels: t.map(n => n.year), datasets: [{ data: t.map(n => n.tmax_avg), borderColor: "#B3261E", pointRadius: 2, tension: 0.2 }] },
    options: { ...common, scales: { x: { grid: { display: false } } } },
  });
}

function markCharts(sel) {
  // highlight the selected month / year in the history charts
  const i = D.spi12.months.indexOf(sel.key);
  charts.spi.data.datasets[0].borderWidth = D.spi12.months.map((_, k) => (k === i ? 2 : 0));
  charts.spi.data.datasets[0].borderColor = "#252423";
  charts.spi.update("none");
}

(async () => {
  try {
    await load();
    setupControls();
    setupMap();
    setupCharts();
    update();
  } catch (e) {
    document.getElementById("updated").textContent = "Erreur de chargement des données : " + e.message;
    console.error(e);
  }
})();
