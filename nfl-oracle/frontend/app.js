"use strict";

const byId = (id) => document.getElementById(id);
const dayInput = byId("day");
const centralDate = () => new Intl.DateTimeFormat("en-CA", {
  timeZone: "America/Chicago",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
}).format(new Date());

dayInput.value = centralDate();
let requestNumber = 0;
let controller;
let latest = null;
let receivedAt = 0;
let serverOffset = 0;

const text = (id, value) => { byId(id).textContent = value; };
const time = (value) => new Date(value).toLocaleString([], {
  timeZoneName: "short",
  month: "short",
  day: "numeric",
  hour: "numeric",
  minute: "2-digit",
});
const slateDate = (value) => new Date(`${value}T12:00:00`).toLocaleDateString([], {
  weekday: "short",
  month: "short",
  day: "numeric",
  year: "numeric",
}).toUpperCase();

function setHeader(payload) {
  text("header-date", slateDate(payload.slate_date));
  text("header-frozen", payload.frozen_at ? time(payload.frozen_at) : "—");
}

function state() {
  if (!latest) return;
  const now = Date.now() + serverOffset;
  const locked = latest.cutoff_at && now >= Date.parse(latest.cutoff_at);
  const stale = !locked && (latest.stale || Date.now() - receivedAt > 90000);
  document.body.classList.toggle("stale", Boolean(stale));
  const recommendation = latest.lineup ? (locked ? "Locked lineup" : "Five picks ready") : "Waiting for freeze";
  byId("recommendation").textContent = recommendation;
  byId("recommendation").classList.toggle("chip-ready", Boolean(latest.lineup));

  if (latest.lineup) {
    text("status", locked ? "Locked lineup" : stale ? "Saved picks need a fresh check" : "Five picks are ready");
    text("message", locked
      ? "This is the saved lineup from before lock. It will not change."
      : stale
        ? "A current refresh is unavailable. These saved picks may be outdated."
        : "Review the five picks below in slot order. You place any entry yourself.");
    text("timing", `Saved ${time(latest.frozen_at)} · lock ${time(latest.cutoff_at)}`);
  } else {
    const messages = {
      no_slate: ["No slate today", "No NFL contest was found for this date at the last check."],
      blocked: ["Picks are not ready", "The pipeline is waiting for required data or validation."],
      error: ["Picks are unavailable", "The last pipeline run could not finish. Try again shortly."],
      locked: ["Slate locked", "The saved lineup is unavailable for this date."],
      waiting: ["Waiting for picks", "No validated lineup has been saved for this date yet."],
    };
    const message = messages[latest.status] || messages.waiting;
    text("status", message[0]);
    text("message", message[1]);
    text("timing", latest.next_freeze ? `Next freeze ${time(latest.next_freeze)}.` : "");
  }
}

function render(payload) {
  if (payload.slate_date !== dayInput.value || !Number.isFinite(Date.parse(payload.server_time))) {
    throw new Error("invalid_response");
  }
  const picks = payload.lineup?.picks;
  if (payload.lineup && (!Array.isArray(picks) || picks.length !== 5 ||
    new Set(picks.map((pick) => pick.player_id)).size !== 5 ||
    !Number.isFinite(Date.parse(payload.cutoff_at)))) {
    throw new Error("invalid_lineup");
  }

  latest = payload;
  receivedAt = Date.now();
  serverOffset = Date.parse(payload.server_time) - receivedAt;
  setHeader(payload);
  text("game-count", payload.games?.length || "—");
  const total = payload.lineup?.total_value ?? payload.lineup?.expected_score;
  text("projected-total", Number.isFinite(total) ? total.toFixed(1) : "—");
  byId("picks").replaceChildren();

  for (const pick of picks || []) {
    const card = document.createElement("li");
    card.className = "pick";
    const rank = element("span", "pick-rank", pick.slot);
    rank.setAttribute("aria-hidden", "true");
    const identity = element("span", "pick-identity");
    identity.append(
      element("strong", "", pick.name),
      element("span", "", `${pick.team} vs ${pick.opponent || "—"} · ${pick.position}`),
    );
    const slot = element("span", "pick-slot", `×${Number(pick.slot_multiplier).toFixed(2)}`);
    const value = element("span", "pick-value");
    value.append(
      element("strong", "", Number(pick.projected_value).toFixed(1)),
      element("small", "", "projected"),
    );
    const boost = element(
      "span",
      "pick-boost",
      pick.card_boost > 0 ? `+${Number(pick.card_boost).toFixed(1)} boost` : "no boost",
    );
    card.append(rank, identity, slot, value, boost);
    byId("picks").append(card);
  }

  text("provenance", payload.lineup
    ? `Saved version ${payload.sequence} · decision ${payload.digest.slice(0, 12)}`
    : "");
  state();
}

function element(tag, className, content) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (content !== undefined) node.textContent = String(content);
  return node;
}

async function refresh() {
  const number = ++requestNumber;
  controller?.abort();
  controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 10000);
  const day = dayInput.value;
  if (!latest || latest.slate_date !== day) {
    latest = null;
    byId("picks").replaceChildren();
    text("status", "Loading picks");
    text("message", "Checking the latest saved lineup.");
    text("timing", "");
  }
  try {
    const response = await fetch(`/lineup/${encodeURIComponent(day)}`, {
      signal: controller.signal,
      cache: "no-store",
    });
    if (!response.ok) throw new Error("request_failed");
    const payload = await response.json();
    if (number === requestNumber && day === dayInput.value) render(payload);
  } catch {
    if (number !== requestNumber) return;
    if (latest) {
      latest.stale = true;
      state();
    } else {
      text("status", "Cannot load picks");
      text("message", "The service did not respond. Use Refresh picks to try again.");
    }
  } finally {
    clearTimeout(timeout);
  }
}

async function openDrawer(kind) {
  const drawer = byId("drawer");
  const title = kind === "history" ? "Freeze history" : "System status";
  text("drawer-title", title);
  byId("drawer-content").replaceChildren(element("p", "drawer-loading", "Checking the oracle…"));
  drawer.hidden = false;
  try {
    const endpoint = kind === "history" ? "/history?limit=10" : "/health";
    const response = await fetch(endpoint, { cache: "no-store" });
    if (!response.ok) throw new Error("request_failed");
    const data = await response.json();
    if (kind === "history") {
      const records = data.records || [];
      if (!records.length) {
        byId("drawer-content").replaceChildren(element("p", "drawer-loading", "No frozen lineups yet."));
      } else {
        const list = element("div", "history-list");
        for (const record of records) {
          const row = element("div", "history-row");
          row.append(
            element("strong", "", record.slate_date),
            element(
              "span",
              "",
              `${record.lineup?.picks?.length === 5 ? "5 picks" : "No lineup"} · ${record.digest?.slice(0, 10) || "—"}`,
            ),
          );
          list.append(row);
        }
        byId("drawer-content").replaceChildren(list);
      }
    } else {
      const check = element("div", "system-check");
      check.append(element("span", "system-dot system-dot-ok"), element("strong", "", data.status || "unknown"));
      byId("drawer-content").replaceChildren(
        check,
        element("p", "drawer-copy", "Database connection is healthy. Contest entry remains hard-denied."),
      );
    }
  } catch {
    byId("drawer-content").replaceChildren(
      element("p", "drawer-loading", "Status is temporarily unavailable."),
    );
  }
}

byId("day-form").addEventListener("submit", (event) => { event.preventDefault(); refresh(); });
byId("refresh").addEventListener("click", refresh);
dayInput.addEventListener("change", refresh);
byId("history").addEventListener("click", () => openDrawer("history"));
byId("system").addEventListener("click", () => openDrawer("system"));
byId("drawer-close").addEventListener("click", () => { byId("drawer").hidden = true; });
byId("theme-toggle").addEventListener("click", () => {
  document.documentElement.dataset.theme = document.documentElement.dataset.theme === "light" ? "dark" : "light";
});
setInterval(() => { if (!document.hidden) refresh(); }, 30000);
setInterval(state, 1000);
refresh();
