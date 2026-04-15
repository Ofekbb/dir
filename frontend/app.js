const DATA_URL = "data/apartments.json";

let allApartments = [];

// ── Helpers ──────────────────────────────────────────────────────────────────

function esc(str) {
  if (!str) return "";
  const el = document.createElement("span");
  el.textContent = str;
  return el.innerHTML;
}

function formatDate(isoStr) {
  if (!isoStr) return "";
  const d = new Date(isoStr.endsWith("Z") ? isoStr : isoStr + "Z");
  return d.toLocaleDateString("he-IL", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function isNew(isoStr) {
  if (!isoStr) return false;
  const d = new Date(isoStr.endsWith("Z") ? isoStr : isoStr + "Z");
  return Date.now() - d.getTime() < 24 * 60 * 60 * 1000;
}

function featureTag(label, val) {
  if (val === null || val === undefined) return "";
  const cls = val ? "yes" : "no";
  return `<span class="feature-tag ${cls}">${esc(label)}</span>`;
}

// ── Render ───────────────────────────────────────────────────────────────────

function renderCard(apt) {
  const escapedImgUrl = apt.image_url ? esc(apt.image_url) : "";
  const imgHtml = escapedImgUrl
    ? `<img class="apt-card-img" src="${escapedImgUrl}" alt="תמונת דירה" loading="lazy" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'" /><div class="apt-card-img-placeholder" style="display:none">🏠</div>`
    : `<div class="apt-card-img-placeholder">🏠</div>`;

  const priceHtml = apt.price
    ? `<span class="apt-card-price">₪${Number(apt.price).toLocaleString()}</span>`
    : `<span class="apt-card-price" style="color:var(--text-dim)">ללא מחיר</span>`;

  const newBadge = isNew(apt.first_seen) ? `<span class="apt-card-new">חדש!</span>` : "";

  const meta = [
    apt.rooms ? `<span class="apt-meta-item">🛏 ${esc(String(apt.rooms))} חד׳</span>` : "",
    apt.size_sqm ? `<span class="apt-meta-item">📐 ${esc(String(apt.size_sqm))} מ״ר</span>` : "",
  ].filter(Boolean).join("");

  const features = [
    featureTag("מרפסת", apt.balcony),
    featureTag("חניה", apt.parking),
    featureTag("מרוהט", apt.furnished),
    featureTag("ממ״ד", apt.mamad),
    apt.agent === false || apt.agent === 0 ? `<span class="feature-tag yes">ללא תיווך</span>` :
    apt.agent === true || apt.agent === 1  ? `<span class="feature-tag">עם תיווך</span>` : "",
  ].filter(Boolean).join("");

  const escapedUrl = apt.listing_url ? esc(apt.listing_url) : "";
  const linkHtml = escapedUrl
    ? `<a class="apt-card-link" href="${escapedUrl}" target="_blank" rel="noopener noreferrer">צפייה →</a>`
    : "";

  return `
    <div class="apt-card">
      ${imgHtml}
      <div class="apt-card-body">
        <div class="apt-card-header">
          ${priceHtml}
          ${newBadge}
        </div>
        ${apt.address ? `<div class="apt-card-address">${esc(apt.address)}</div>` : ""}
        ${apt.neighborhood ? `<div class="apt-card-neighborhood">📍 ${esc(apt.neighborhood)}</div>` : ""}
        ${meta ? `<div class="apt-card-meta">${meta}</div>` : ""}
        ${features ? `<div class="apt-card-features">${features}</div>` : ""}
        <div class="apt-card-footer">
          <span class="apt-card-date">${formatDate(apt.first_seen)}</span>
          ${linkHtml}
        </div>
      </div>
    </div>
  `;
}

// ── Filter & Sort ─────────────────────────────────────────────────────────────

function getFilters() {
  const activeRoomBtn = document.getElementById("filter-rooms").querySelector(".room-btn.active");
  return {
    neighborhood: document.getElementById("filter-neighborhood").value,
    maxPrice: parseInt(document.getElementById("filter-price").value, 10),
    minRooms: parseFloat(activeRoomBtn?.dataset.val || "0"),
    balcony: document.getElementById("feat-balcony").checked,
    parking: document.getElementById("feat-parking").checked,
    noAgent: document.getElementById("feat-no-agent").checked,
    sort: document.getElementById("sort-by").value,
  };
}

function applyFilters() {
  const f = getFilters();
  const priceMax = parseInt(document.getElementById("filter-price").max, 10);

  let list = allApartments.filter(apt => {
    if (f.neighborhood && apt.neighborhood !== f.neighborhood) return false;
    if (f.maxPrice < priceMax && apt.price && apt.price > f.maxPrice) return false;
    if (f.minRooms && apt.rooms && apt.rooms < f.minRooms) return false;
    if (f.balcony && !apt.balcony) return false;
    if (f.parking && !apt.parking) return false;
    if (f.noAgent && apt.agent !== false && apt.agent !== 0) return false;
    return true;
  });

  list.sort((a, b) => {
    switch (f.sort) {
      case "price_asc":  return (a.price || 0) - (b.price || 0);
      case "price_desc": return (b.price || 0) - (a.price || 0);
      case "rooms_desc": return (b.rooms || 0) - (a.rooms || 0);
      default:
        return new Date(b.first_seen || 0) - new Date(a.first_seen || 0);
    }
  });

  const grid = document.getElementById("cards-grid");
  const none = document.getElementById("no-results");

  if (list.length === 0) {
    grid.innerHTML = "";
    none.classList.remove("hidden");
  } else {
    none.classList.add("hidden");
    grid.innerHTML = list.map(renderCard).join("");
  }
}

// ── Populate Dropdowns ────────────────────────────────────────────────────────

function populateNeighborhoods() {
  const neighborhoods = [...new Set(allApartments.map(a => a.neighborhood).filter(Boolean))].sort();
  const sel = document.getElementById("filter-neighborhood");
  sel.innerHTML = `<option value="">הכל</option>` +
    neighborhoods.map(n => `<option value="${esc(n)}">${esc(n)}</option>`).join("");
}

// ── Settings View ─────────────────────────────────────────────────────────────

function renderSettings() {
  const sourcesList = document.getElementById("sources-list");
  const sources = [...new Set(allApartments.map(a => a.source).filter(Boolean))];
  if (sources.length > 0) {
    sourcesList.innerHTML = sources.map(s => `
      <div class="source-item">
        <div class="source-name">${esc(s)}</div>
      </div>
    `).join("");
  } else {
    sourcesList.innerHTML = `<p style="color:var(--text-dim);font-size:14px">אין נתונים עדיין</p>`;
  }

  const statsEl = document.getElementById("stats-table");
  const newToday = allApartments.filter(a => isNew(a.first_seen)).length;
  const avgPrice = allApartments.filter(a => a.price).reduce((sum, a) => sum + a.price, 0) /
                   (allApartments.filter(a => a.price).length || 1);
  statsEl.innerHTML = `
    <div class="stat-item"><div class="stat-item-label">סה״כ דירות</div><div class="stat-item-value">${allApartments.length}</div></div>
    <div class="stat-item"><div class="stat-item-label">חדשות (24 שעות)</div><div class="stat-item-value">${newToday}</div></div>
    <div class="stat-item"><div class="stat-item-label">מחיר ממוצע</div><div class="stat-item-value">₪${Math.round(avgPrice).toLocaleString()}</div></div>
    <div class="stat-item"><div class="stat-item-label">שכונות</div><div class="stat-item-value">${[...new Set(allApartments.map(a => a.neighborhood).filter(Boolean))].length}</div></div>
  `;
}

// ── Fetch Data ────────────────────────────────────────────────────────────────

async function loadData() {
  try {
    const res = await fetch(DATA_URL);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    allApartments = await res.json();
  } catch (e) {
    console.error("Failed to load apartments.json:", e);
    allApartments = [];
  }

  document.getElementById("apt-count").textContent = `${allApartments.length} דירות`;

  const latest = allApartments
    .map(a => a.last_seen)
    .filter(Boolean)
    .sort()
    .at(-1);
  if (latest) {
    document.getElementById("last-updated").textContent = `עדכון אחרון: ${formatDate(latest)}`;
  }

  const prices = allApartments.map(a => a.price).filter(Boolean);
  const priceMax = Math.max(...prices, 20000);
  const priceInput = document.getElementById("filter-price");
  priceInput.max = priceMax;
  priceInput.value = priceMax;
  document.getElementById("filter-price-val").textContent = "הכל";

  populateNeighborhoods();
  applyFilters();
  renderSettings();
}

// ── Event Listeners ───────────────────────────────────────────────────────────

document.querySelectorAll(".nav-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".nav-btn").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".view").forEach(v => v.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(`view-${btn.dataset.view}`).classList.add("active");
  });
});

document.getElementById("filter-neighborhood").addEventListener("change", applyFilters);
document.getElementById("sort-by").addEventListener("change", applyFilters);
document.getElementById("feat-balcony").addEventListener("change", applyFilters);
document.getElementById("feat-parking").addEventListener("change", applyFilters);
document.getElementById("feat-no-agent").addEventListener("change", applyFilters);

document.getElementById("filter-price").addEventListener("input", e => {
  const val = parseInt(e.target.value, 10);
  document.getElementById("filter-price-val").textContent =
    val >= parseInt(e.target.max, 10) ? "הכל" : `${val.toLocaleString()} ₪`;
  applyFilters();
});

document.getElementById("filter-rooms").addEventListener("click", e => {
  const btn = e.target.closest(".room-btn");
  if (!btn) return;
  document.querySelectorAll(".room-btn").forEach(b => b.classList.remove("active"));
  btn.classList.add("active");
  applyFilters();
});

document.getElementById("btn-reset").addEventListener("click", () => {
  document.getElementById("filter-neighborhood").value = "";
  const priceInput = document.getElementById("filter-price");
  priceInput.value = priceInput.max;
  document.getElementById("filter-price-val").textContent = "הכל";
  document.querySelectorAll(".room-btn").forEach((b, i) => b.classList.toggle("active", i === 0));
  document.getElementById("feat-balcony").checked = false;
  document.getElementById("feat-parking").checked = false;
  document.getElementById("feat-no-agent").checked = false;
  document.getElementById("sort-by").value = "date_desc";
  applyFilters();
});

// ── Init ──────────────────────────────────────────────────────────────────────
loadData();
