"use strict";
const byId = id => document.getElementById(id);
const dayInput = byId("day");
const centralDate = () => new Intl.DateTimeFormat("en-CA", {timeZone: "America/Chicago", year: "numeric", month: "2-digit", day: "2-digit"}).format(new Date());
dayInput.value = centralDate();
let requestNumber = 0;
let controller;
let latest = null;
let receivedAt = 0;
let serverOffset = 0;
const text = (id, value) => { byId(id).textContent = value; };
const time = value => new Date(value).toLocaleString([], {timeZoneName: "short"});
const number = value => typeof value === "number" && Number.isFinite(value) ? value.toFixed(2) : null;
function state() {
  if (!latest) return;
  const now = Date.now() + serverOffset;
  const locked = latest.cutoff_at && now >= Date.parse(latest.cutoff_at);
  const stale = !locked && (latest.stale || Date.now() - receivedAt > 90000);
  document.body.classList.toggle("stale", Boolean(stale));
  if (latest.lineup) {
    text("status", locked ? "Locked lineup" : stale ? "Saved picks need a fresh check" : "Five picks are ready");
    text("message", locked ? "This is the saved lineup from before lock. It will not change." : stale ? "A current refresh is unavailable. These saved picks may be outdated." : "Review the five picks below in slot order. You place any entry yourself.");
    text("timing", `Saved ${time(latest.frozen_at)}. Lock ${time(latest.cutoff_at)}.`);
  } else {
    const messages = {no_slate:["No slate today", "No NFL contest was found for this date at the last check."], blocked:["Picks are not ready", "The pipeline is waiting for required data or validation."], error:["Picks are unavailable", "The last pipeline run could not finish. Try again shortly."], locked:["Slate locked", "The saved lineup is unavailable for this date."], waiting:["Waiting for picks", "No validated lineup has been saved for this date yet."]};
    const message = messages[latest.status] || messages.waiting;
    text("status", message[0]); text("message", message[1]);
    text("timing", latest.next_freeze?.at ? `Next freeze ${time(latest.next_freeze.at)}.` : "");
  }
}
function render(payload) {
  if (payload.slate_date !== dayInput.value || !Number.isFinite(Date.parse(payload.server_time))) throw new Error("invalid_response");
  const picks = payload.lineup?.picks;
  if (payload.lineup && (!Array.isArray(picks) || picks.length !== 5 || new Set(picks.map(p => p.player_id)).size !== 5 || !Number.isFinite(Date.parse(payload.cutoff_at)))) throw new Error("invalid_lineup");
  latest = payload; receivedAt = Date.now(); serverOffset = Date.parse(payload.server_time) - receivedAt;
  byId("picks").replaceChildren();
  for (const pick of picks || []) {
    const card = document.createElement("li"); card.className = "pick";
    const slot = document.createElement("span"); slot.className = "slot"; slot.textContent = String(pick.slot);
    const identity = document.createElement("div");
    const name = document.createElement("div"); name.className = "name"; name.textContent = pick.name;
    const meta = document.createElement("div"); meta.className = "meta"; meta.textContent = `${pick.position} · ${pick.team} vs ${pick.opponent}`;
    identity.append(name, meta);
    const projection = document.createElement("div"); projection.className = "projection";
    const projected = number(pick.projected_value);
    const slotTotal = projected === null ? number(pick.projected_score) : number(
      pick.projected_value * (pick.slot_multiplier + pick.card_boost)
    );
    projection.textContent = `${projected === null ? "Predicted score unavailable" : `Predicted score ${projected}`} · ${slotTotal === null ? "Expected slot total unavailable" : `Expected slot total ${slotTotal}`} · Slot ${pick.slot_multiplier}× · Card +${pick.card_boost}`;
    card.append(slot, identity, projection); byId("picks").append(card);
  }
  text("provenance", payload.lineup ? `Saved version ${payload.sequence}. Decision ${payload.digest.slice(0, 12)}.` : "");
  state();
}
async function refresh() {
  const number = ++requestNumber;
  controller?.abort(); controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 10000);
  const day = dayInput.value;
  if (!latest || latest.slate_date !== day) {
    latest = null; byId("picks").replaceChildren(); text("timing", ""); text("provenance", "");
    text("status", "Loading picks"); text("message", "Checking the latest saved lineup.");
  }
  try {
    const response = await fetch(`/lineup/${encodeURIComponent(day)}`, {signal: controller.signal, cache: "no-store"});
    if (!response.ok) throw new Error("request_failed");
    const payload = await response.json();
    if (number === requestNumber && day === dayInput.value) render(payload);
  } catch {
    if (number !== requestNumber) return;
    if (latest) { latest.stale = true; state(); }
    else { text("status", "Cannot load picks"); text("message", "The service did not respond. Use Refresh to try again."); }
  } finally { clearTimeout(timeout); }
}
byId("day-form").addEventListener("submit", event => {event.preventDefault(); refresh();});
byId("refresh").addEventListener("click", refresh);
dayInput.addEventListener("change", refresh);
setInterval(() => { if (!document.hidden) refresh(); }, 30000);
setInterval(state, 1000);
refresh();
