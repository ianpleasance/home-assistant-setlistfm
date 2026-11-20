/* Bundled setlist.fm cards. No network requests or external runtime dependencies. */
const PRESETS = {
  complete: { name: "Complete", title: "My concerts", limit: 5, description: "Next show, upcoming dates and recent memories." },
  compact: { name: "Compact", title: "Concerts", limit: 3, description: "A small next-show highlight and recent concert list." },
  deluxe: { name: "Deluxe", title: "My concert journey", limit: 10, description: "A featured show, detailed lists and available-record statistics." },
  mobile: { name: "Mobile", title: "Concerts", limit: 5, description: "A touch-friendly, single-column concert companion." },
};
const DOCUMENTATION = "https://github.com/ianpleasance/home-assistant-setlistfm/blob/main/CARDS.md";
const FILTERS = { all: "Upcoming and recent", upcoming: "Upcoming only", past: "Recent only" };

function text(value, fallback = "") {
  return typeof value === "string" && value.trim() ? value : fallback;
}

function element(tag, className, content) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (content !== undefined) node.textContent = content;
  return node;
}

export function safeSetlistUrl(value) {
  if (typeof value !== "string") return null;
  try {
    const url = new URL(value);
    if (!["https:", "http:"].includes(url.protocol) || url.username || url.password ||
        !["setlist.fm", "www.setlist.fm"].includes(url.hostname) || url.port) return null;
    url.protocol = "https:";
    return url.href;
  } catch {
    return null;
  }
}

export function parseConcertDate(value) {
  if (typeof value !== "string" || !/^\d{2}-\d{2}-\d{4}$/.test(value)) return null;
  const [day, month, year] = value.split("-").map(Number);
  const date = new Date(0);
  date.setUTCFullYear(year, month - 1, day);
  if (year < 1 || date.getUTCFullYear() !== year ||
      date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day) return null;
  return { date, key: `${String(year).padStart(4, "0")}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}` };
}

export function todayKey(timeZone, now = new Date()) {
  if (!timeZone) throw new Error("Waiting for the Home Assistant time zone.");
  const parts = new Intl.DateTimeFormat("en", {
    timeZone, year: "numeric", month: "2-digit", day: "2-digit",
  }).formatToParts(now);
  const value = (type) => parts.find((part) => part.type === type).value;
  return `${value("year")}-${value("month")}-${value("day")}`;
}

export function splitConcerts(records, today, grouped = false) {
  const valid = [];
  let invalid = 0;
  for (const record of records) {
    const date = parseConcertDate(record?.date);
    const validDetails = grouped
      ? Array.isArray(record?.performances) && record.performances.length > 0 &&
        record.performances.every((performance) => performance?.artist && typeof performance.artist.name === "string")
      : record?.artist;
    if (!date || !validDetails || !record?.venue) {
      invalid++;
      continue;
    }
    valid.push({ ...record, calendar: date });
  }
  return {
    upcoming: valid.filter((record) => record.calendar.key >= today)
      .sort((a, b) => a.calendar.key.localeCompare(b.calendar.key)),
    past: valid.filter((record) => record.calendar.key < today)
      .sort((a, b) => b.calendar.key.localeCompare(a.calendar.key)),
    invalid,
  };
}

export function isConcertsEntity(hass, entityId) {
  if (!entityId?.startsWith("sensor.")) return false;
  const attributes = hass?.states?.[entityId]?.attributes;
  if (!Array.isArray(attributes?.concerts)) return false;
  // The data contract, not a generated entity-id prefix, identifies this sensor.
  return typeof attributes.concert_list === "string" ||
    /setlist\.fm/i.test(text(attributes.attribution)) ||
    hass?.entities?.[entityId]?.platform === "setlistfm";
}

function entities(hass) {
  return Object.keys(hass?.states || {}).filter((id) => isConcertsEntity(hass, id))
    .sort((a, b) => a.localeCompare(b));
}

function presetFor(type) {
  return Object.keys(PRESETS).find((key) => type === `custom:setlistfm-${key}-card`) || "complete";
}

function normalizeConfig(config, preset) {
  if (!config || typeof config !== "object") throw new Error("A card configuration is required.");
  if (config.entity !== undefined && (typeof config.entity !== "string" ||
      (config.entity && !config.entity.startsWith("sensor.")))) {
    throw new Error("Select a concerts sensor.");
  }
  if (config.title !== undefined && typeof config.title !== "string") throw new Error("Title must be text.");
  if (config.limit !== undefined && (!Number.isInteger(config.limit) || config.limit < 1 || config.limit > 50)) {
    throw new Error("Concerts per section must be a whole number from 1 to 50.");
  }
  if (config.filter !== undefined && !Object.hasOwn(FILTERS, config.filter)) throw new Error("Invalid concert filter.");
  for (const key of ["show_location", "show_songs", "group_by_visit"]) {
    if (config[key] !== undefined && typeof config[key] !== "boolean") throw new Error(`${key} must be true or false.`);
  }
  return {
    entity: "", title: PRESETS[preset].title, limit: PRESETS[preset].limit,
    filter: "all", show_location: true, show_songs: preset !== "compact", group_by_visit: false,
    ...config,
  };
}

const STYLE = `
  :host { display:block; min-width:0; color:var(--primary-text-color); font-family:var(--ha-font-family-body, var(--paper-font-body1_-_font-family, inherit)); }
  * { box-sizing:border-box; }
  ha-card { display:block; overflow:hidden; background:var(--ha-card-background, var(--card-background-color)); border-radius:var(--ha-card-border-radius, 12px); }
  .card { padding:24px; container-type:inline-size; }
  .eyebrow, .section-label { font-size:var(--ha-font-size-s, 12px); font-weight:600; letter-spacing:.08em; text-transform:uppercase; color:var(--secondary-text-color); }
  .eyebrow { display:flex; align-items:center; gap:8px; margin-bottom:8px; }
  .mark { width:8px; height:8px; background:var(--primary-color); border-radius:50%; }
  h2 { font-size:var(--ha-font-size-2xl, 24px); line-height:1.25; font-weight:600; margin:0; letter-spacing:-.025em; overflow-wrap:anywhere; }
  h3 { font-size:var(--ha-font-size-m, 16px); line-height:1.4; font-weight:600; margin:0 0 12px; }
  h4 { font-size:var(--ha-font-size-m, 16px); line-height:1.4; font-weight:600; margin:0; overflow-wrap:anywhere; }
  p { margin:6px 0 0; line-height:1.5; overflow-wrap:anywhere; }
  .account, .muted, .scope, footer { color:var(--secondary-text-color); font-size:var(--ha-font-size-s, 12px); line-height:1.5; }
  .account { margin-top:6px; overflow-wrap:anywhere; }
  .stats { display:flex; flex-wrap:wrap; gap:12px 28px; padding:20px 0; margin:0; }
  .stat { display:flex; flex-direction:column-reverse; gap:2px; }
  dt { font-size:12px; color:var(--secondary-text-color); }
  dd { margin:0; font-size:24px; font-weight:600; font-variant-numeric:tabular-nums; }
  section { margin-top:22px; }
  .hero { padding:20px; border-radius:12px; border:1px solid var(--divider-color); border-inline-start:4px solid var(--primary-color); background:var(--secondary-background-color); }
  .hero h4 { font-size:22px; letter-spacing:-.02em; }
  .hero .section-label { margin-bottom:14px; }
  .event { display:grid; grid-template-columns:48px minmax(0, 1fr); gap:14px; align-items:start; }
  .date { display:flex; flex-direction:column; text-align:center; gap:2px; border:1px solid var(--divider-color); border-radius:8px; padding:6px 2px; font-size:11px; color:var(--secondary-text-color); line-height:1.25; }
  .day { font-size:23px; color:var(--primary-text-color); font-weight:600; font-variant-numeric:tabular-nums; }
  .date-line { font-size:12px; color:var(--secondary-text-color); }
  .venue { font-size:14px; }
  .location, .songs { font-size:12px; color:var(--secondary-text-color); }
  .performance { padding:8px 0; }
  .performance-name { display:block; font-weight:600; overflow-wrap:anywhere; }
  ul { list-style:none; margin:0; padding:0; }
  li { padding:16px 0; border-bottom:1px solid var(--divider-color); }
  li:first-child { padding-top:0; }
  li:last-child { border-bottom:0; padding-bottom:0; }
  a { color:var(--primary-color); text-decoration:none; }
  a:hover { text-decoration:underline; }
  a, button { -webkit-tap-highlight-color:transparent; }
  .setlist { display:inline-flex; align-items:center; min-height:44px; margin-top:4px; font-size:13px; font-weight:600; }
  a:focus-visible, button:focus-visible { outline:2px solid var(--primary-color); outline-offset:3px; border-radius:4px; }
  .scope { margin-top:20px; padding-top:16px; border-top:1px solid var(--divider-color); }
  footer { display:flex; flex-wrap:wrap; align-items:center; justify-content:space-between; gap:0 12px; margin-top:8px; }
  footer a, footer button { display:inline-flex; align-items:center; min-height:44px; }
  button { cursor:pointer; background:none; color:var(--primary-color); border:0; padding:0; font:inherit; font-weight:600; }
  .notice { padding:16px; margin-top:18px; border:1px solid var(--divider-color); border-radius:8px; color:var(--secondary-text-color); font-size:14px; line-height:1.5; }
  .warning { border-inline-start:3px solid var(--warning-color, var(--primary-color)); }
  .updated { flex-basis:100%; font-size:12px; }
  .compact { padding:20px; }
  .compact h2 { font-size:20px; }
  .compact .hero { padding:16px; }
  .compact .hero h4 { font-size:18px; }
  .compact .stats { padding-bottom:0; }
  .compact .event { grid-template-columns:40px minmax(0, 1fr); gap:12px; }
  .compact .setlist { margin-top:0; }
  .compact .columns .date-line, .compact .columns .venue, .compact .columns .location { display:none; }
  .deluxe .hero { padding:24px; }
  .deluxe .hero h4 { font-size:28px; }
  @container (min-width:560px) { .columns { display:grid; grid-template-columns:minmax(0, 1fr) minmax(0, 1fr); gap:28px; } }
  .mobile .columns { display:block; }
  @container (max-width:300px) {
    .event { grid-template-columns:38px minmax(0, 1fr); gap:10px; }
    .hero, .deluxe .hero { padding:14px; }
    .hero h4, .deluxe .hero h4 { font-size:20px; }
    .stats { gap:12px 18px; }
  }
  @media (max-width:400px) { .card { padding:16px; } }
`;

// HA replaces the global element registry during bootstrap. Check the active
// registry each frame: an old registry's whenDefined promise may never resolve.
await new Promise((resolve) => {
  const ready = () => {
    if (customElements.get("ha-card")) resolve();
    else window.requestAnimationFrame(ready);
  };
  ready();
});

class SetlistFmCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
  }

  static getConfigElement() { return document.createElement("setlistfm-card-editor"); }

  static getStubConfig(hass, entityIds = [], fallbackEntityIds = []) {
    const candidates = [...entityIds, ...fallbackEntityIds, ...entities(hass)];
    const entity = candidates.find((id) => isConcertsEntity(hass, id)) || "";
    return normalizeConfig({ entity }, this.preset);
  }

  setConfig(config) {
    this._config = normalizeConfig(config, this.constructor.preset);
    this._renderKey = undefined;
    this._render();
  }

  set hass(hass) { this._hass = hass; this._render(); }
  get hass() { return this._hass; }

  connectedCallback() {
    this._render();
    this._clock = window.setInterval(() => this._render(), 60000);
  }

  disconnectedCallback() { window.clearInterval(this._clock); }

  getCardSize() {
    return Math.ceil((this.shadowRoot.querySelector("ha-card")?.getBoundingClientRect().height ||
      (this.constructor.preset === "compact" ? 400 : 650)) / 50);
  }

  getGridOptions() { return { columns: 12, min_columns: 6, min_rows: 3 }; }

  _link(label, url, className) {
    const link = element("a", className, label);
    link.href = url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    return link;
  }

  _notice(parent, message, warning = false) {
    const notice = element("p", `notice${warning ? " warning" : ""}`, message);
    notice.setAttribute("role", "status");
    parent.append(notice);
  }

  _event(record, hero = false) {
    const language = this._hass.locale?.language || this._hass.language || "en";
    const format = (options) => new Intl.DateTimeFormat(language, { ...options, timeZone: "UTC" }).format(record.calendar.date);
    const grouped = this._config.group_by_visit;
    const row = element("div", `event${grouped ? " visit" : ""}`);
    const badge = element("time", "date");
    badge.dateTime = record.calendar.key;
    badge.setAttribute("aria-label", format({ dateStyle: "full" }));
    badge.append(element("span", "", format({ month: "short" })),
      element("span", "day", format({ day: "numeric" })), element("span", "", format({ year: "numeric" })));
    const details = element("div");
    const artist = grouped ? "" : text(record.artist.name, "Unknown artist");
    details.append(element("h4", "", grouped ? text(record.venue.name, "Unknown venue") : artist));
    details.append(element("p", "date-line", format({ weekday: "short", day: "numeric", month: "short", year: "numeric" })));
    if (!grouped) details.append(element("p", "venue", text(record.venue.name, "Unknown venue")));
    if (this._config.show_location) {
      const location = [record.venue.city, record.venue.state, record.venue.country].map((part) => text(part)).filter(Boolean).join(", ");
      if (location) details.append(element("p", "location", location));
    }
    if (grouped) {
      details.append(element("p", "muted", `${record.performance_count} performances at this visit (artist order, not billing)`));
      const lineup = element("ul", "lineup");
      for (const performance of record.performances) {
        const item = element("li", "performance");
        const name = text(performance.artist.name, "Unknown artist");
        item.append(element("span", "performance-name", name));
        this._performanceDetails(item, performance, name, record.date, false);
        lineup.append(item);
      }
      details.append(lineup);
      if (record.grouping_complete === false) {
        this._notice(details, "Venue identity is missing. This performance is shown separately; it may belong to another visit.", true);
      }
      if (Number.isInteger(record.omitted_performance_count) && record.omitted_performance_count > 0) {
        this._notice(details, `${record.omitted_performance_count} additional performances are omitted by the display safety limit. This lineup is incomplete; the native visit count is unaffected.`, true);
      }
    } else {
      this._performanceDetails(details, record, artist, record.date, hero);
    }
    row.append(badge, details);
    return row;
  }

  _performanceDetails(parent, record, artist, date, hero) {
    if (this._config.show_songs && Number.isInteger(record.song_count) && record.song_count > 0) {
      parent.append(element("p", "songs", `${record.song_count} songs listed`));
    }
    const url = safeSetlistUrl(record.url);
    if (url) {
      const link = this._link(hero ? "Explore setlist" : "View setlist", url, "setlist");
      link.setAttribute("aria-label", `View ${artist} setlist on ${date} (opens in a new tab)`);
      parent.append(link);
    }
  }

  _section(parent, title, records, emptyMessage) {
    const section = element("section");
    section.append(element("h3", "", title));
    if (!records.length) {
      section.append(element("p", "muted", emptyMessage));
    } else {
      const list = element("ul");
      for (const record of records.slice(0, this._config.limit)) {
        const item = element("li");
        item.append(this._event(record));
        list.append(item);
      }
      section.append(list);
      if (records.length > this._config.limit) {
        section.append(element("p", "muted", `${records.length - this._config.limit} more available. Increase the card's section limit to see more.`));
      }
    }
    parent.append(section);
  }

  _render() {
    if (!this._config) return;
    const hass = this._hass;
    const state = hass?.states?.[this._config.entity];
    let today;
    let timezoneError;
    try { today = todayKey(hass?.config?.time_zone); }
    catch (error) { timezoneError = error instanceof RangeError ? "The Home Assistant time zone is invalid." : error.message; }
    const key = [state, today, hass?.config?.time_zone, hass?.locale?.language, hass?.language, !!hass, this._config];
    if (this._renderKey?.every((part, index) => part === key[index])) return;
    this._renderKey = key;
    const style = element("style");
    style.textContent = STYLE;
    const card = element("ha-card");
    const body = element("div", `card ${this.constructor.preset}`);
    const header = element("header");
    const eyebrow = element("div", "eyebrow");
    eyebrow.append(element("span", "mark"), element("span", "", "setlist.fm / live music"));
    header.append(eyebrow, element("h2", "", this._config.title || PRESETS[this.constructor.preset].title));
    if (state) header.append(element("p", "account", text(state.attributes.friendly_name, this._config.entity)));
    body.append(header);
    card.append(body);
    this.shadowRoot.replaceChildren(style, card);

    if (!this._config.entity) {
      this._notice(body, "Choose your setlist.fm concerts sensor in the card editor to see your shows.");
    } else if (!hass) {
      this._notice(body, "Connecting to Home Assistant...");
    } else if (!state) {
      this._notice(body, `The entity ${this._config.entity} was not found. Select its current name in the card editor.`, true);
    } else if (state.state === "unavailable") {
      this._notice(body, "Concert data is unavailable. Check the setlist.fm integration; saved shows will return when it reconnects.", true);
    } else if (state.state === "unknown") {
      this._notice(body, "Concert data is not ready yet. Waiting for a successful integration update.");
    } else if (!Array.isArray(state.attributes.concerts)) {
      this._notice(body, "This entity has no concerts list. Select the setlist.fm concerts sensor, not a date or total sensor.", true);
    } else if (timezoneError) {
      this._notice(body, timezoneError, true);
    } else {
      this._content(body, state, today);
    }
    this._footer(body, state);
  }

  _content(body, state, today) {
    const grouped = this._config.group_by_visit;
    if (state.attributes.last_update_success === false) {
      this._notice(body, "The last refresh failed. These are previously loaded records, not a fresh result.", true);
    }
    if (state.attributes.complete === false) {
      let detail = "Counts and the next show cover only the available records.";
      if (state.attributes.completeness_reason === "attendance_not_found") {
        detail = "The response cannot distinguish an empty account from an unknown username. Total attendance is unknown.";
      } else if (state.attributes.completeness_reason === "invalid_records") {
        const skipped = state.attributes.skipped_count;
        const omitted = Number.isInteger(skipped) && skipped > 0
          ? `${skipped} invalid ${skipped === 1 ? "record was" : "records were"}`
          : "Invalid records were";
        detail = `${omitted} skipped by the integration before providing this list. ${detail}`;
      }
      this._notice(body, `Attendance data is incomplete. ${detail}`, true);
    }
    if (grouped && !Array.isArray(state.attributes.concert_visits)) {
      this._notice(body, "Group by concert visit requires an updated setlist.fm integration. Update the integration and refresh, or turn grouping off to see individual performances.", true);
      return;
    }
    const { upcoming, past, invalid } = splitConcerts(
      grouped ? state.attributes.concert_visits : state.attributes.concerts, today, grouped,
    );
    const count = upcoming.length + past.length;
    const uncertain = grouped && state.attributes.grouping_complete !== true;
    if (uncertain) {
      this._notice(body, "Visit grouping is uncertain: attendance coverage or venue identity is incomplete. Unidentified performances remain separate; a unique total cannot be established.", true);
    }
    if (invalid) this._notice(body, `${invalid} concert record(s) could not be displayed because their date or details are invalid.`, true);
    const stats = element("dl", "stats");
    const values = [[grouped ? (uncertain ? "Visit groups / separate performances" : "Visits in list") : "Available records", count]];
    if (grouped) values.push(["Performances in list", [...upcoming, ...past].reduce((total, visit) => total + visit.performances.length, 0)]);
    if (this.constructor.preset !== "compact") values.push([grouped ? "Upcoming groups" : "Upcoming in list", upcoming.length]);
    if (this.constructor.preset === "deluxe") values.push([grouped ? "Past groups" : "Past in list", past.length]);
    for (const [label, value] of values) {
      const stat = element("div", "stat");
      stat.append(element("dt", "", label), element("dd", "", String(value)));
      stats.append(stat);
    }
    body.append(stats);
    if (!count) {
      this._notice(body, "No concert records are available in this display list. Check the integration's Show concerts and Number of concerts options. An empty list does not establish your total attendance.");
      return;
    }
    const showUpcoming = this._config.filter !== "past";
    const showPast = this._config.filter !== "upcoming";
    if (showUpcoming) {
      const hero = element("section", "hero");
      hero.append(element("h3", "section-label", grouped ? "Next visit in this list" : "Next in this list"));
      if (upcoming[0]) hero.append(this._event(upcoming[0], true));
      else hero.append(element("p", "muted", "No upcoming concerts in the available records."));
      body.append(hero);
    }
    const columns = element("div", "columns");
    if (showUpcoming && this.constructor.preset !== "compact") {
      this._section(columns, "More upcoming", upcoming.slice(1), "No additional upcoming dates in this list.");
    } else if (showUpcoming && upcoming.length > 1) {
      body.append(element("p", "muted", `${upcoming.length - 1} more upcoming in the available records. Use Complete, Deluxe or Mobile to show the list.`));
    }
    if (showPast) this._section(columns, grouped ? "Recent visits" : "Recent concerts", past, "No past concerts in the available records.");
    body.append(columns);
  }

  _footer(body, state) {
    body.append(element("p", "scope", this._config.group_by_visit
      ? "Visits approximate one venue ID per calendar day, not tickets or billing. Grouped from all fetched performances before the integration's visit limit; this filtered list is not your full history. Upcoming coverage on setlist.fm may be limited."
      : "Based on the integration's filtered, limited display list, not your full history. Upcoming coverage on setlist.fm may be limited."));
    const footer = element("footer");
    footer.append(this._link("Data from setlist.fm", "https://www.setlist.fm", ""));
    if (state) {
      const more = element("button", "", "Account details");
      more.type = "button";
      more.addEventListener("click", () => this.dispatchEvent(new CustomEvent("hass-more-info", {
        bubbles: true, composed: true, detail: { entityId: this._config.entity },
      })));
      footer.append(more);
      const updated = state.attributes.last_updated;
      if (typeof updated === "string" && !Number.isNaN(Date.parse(updated))) {
        const language = this._hass.locale?.language || this._hass.language || "en";
        if (this._hass.config?.time_zone) {
          try {
            footer.append(element("span", "updated", `Last successful update: ${new Intl.DateTimeFormat(language, {
              dateStyle: "medium", timeStyle: "short", timeZone: this._hass.config.time_zone,
            }).format(new Date(updated))}`));
          } catch (error) {
            if (!(error instanceof RangeError)) throw error;
            footer.append(element("span", "updated", "Last update cannot be formatted with the current locale or time zone."));
          }
        }
      }
    }
    body.append(footer);
  }
}

const EDITOR_STYLE = `
  :host { display:block; color:var(--primary-text-color); font-family:inherit; }
  * { box-sizing:border-box; }
  .fields { display:grid; gap:18px; padding:8px 0; }
  label { display:grid; gap:8px; font-size:14px; font-weight:500; }
  select, input { width:100%; min-height:44px; padding:10px 12px; border:1px solid var(--divider-color); border-radius:8px; background:var(--card-background-color); color:var(--primary-text-color); font:inherit; }
  input[type=checkbox] { width:22px; min-height:22px; margin:0; accent-color:var(--primary-color); }
  .check { display:flex; align-items:center; gap:12px; min-height:44px; }
  input:focus-visible, select:focus-visible { outline:2px solid var(--primary-color); outline-offset:2px; }
  p { font-size:13px; line-height:1.6; color:var(--secondary-text-color); margin:8px 0; }
`;

class SetlistFmCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this.shadowRoot.addEventListener("focusout", () => queueMicrotask(() => {
      if (this._optionsPending) this._updateAccounts();
    }));
  }

  setConfig(config) {
    this._config = normalizeConfig(config, presetFor(config.type));
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._updateAccounts();
  }

  get hass() { return this._hass; }

  _change(key, value) {
    this._config = { ...this._config, [key]: value };
    this.dispatchEvent(new CustomEvent("config-changed", {
      bubbles: true, composed: true, detail: { config: { ...this._config } },
    }));
  }

  _field(parent, title, control) {
    const label = element("label", control.type === "checkbox" ? "check" : "");
    const caption = element("span", "", title);
    caption.id = `field-${parent.children.length}`;
    control.setAttribute("aria-labelledby", caption.id);
    label.append(caption, control);
    parent.append(label);
  }

  _updateAccounts(force = false) {
    const account = this.shadowRoot.querySelector(".account-selector");
    if (!account || !this._config) return;
    const ids = entities(this._hass);
    const optionsKey = JSON.stringify(ids.map((id) => [id, this._hass.states[id].attributes.friendly_name]));
    if (!force && optionsKey === this._optionsKey) {
      this._optionsPending = false;
      return;
    }
    if (this.shadowRoot.activeElement === account) {
      this._optionsPending = true;
      return;
    }
    const options = document.createDocumentFragment();
    const placeholder = element("option", "", "Select a setlist.fm account");
    placeholder.value = "";
    options.append(placeholder);
    if (this._config.entity && !ids.includes(this._config.entity)) {
      const missing = element("option", "", `${this._config.entity} (not currently available)`);
      missing.value = this._config.entity;
      options.append(missing);
    }
    for (const id of ids) {
      const option = element("option", "", `${text(this._hass.states[id].attributes.friendly_name, id)} (${id})`);
      option.value = id;
      options.append(option);
    }
    account.replaceChildren(options);
    account.value = this._config.entity;
    this._optionsKey = optionsKey;
    this._optionsPending = false;
  }

  _render() {
    if (!this._config) return;
    // HA echoes editor configurations; keep the active input and its cursor.
    if (this.shadowRoot.activeElement) return;
    const style = element("style");
    style.textContent = EDITOR_STYLE;
    const fields = element("div", "fields");
    const account = element("select", "account-selector");
    account.addEventListener("change", () => this._change("entity", account.value));
    this._field(fields, "Account / concerts entity", account);
    const title = element("input");
    title.type = "text";
    title.value = this._config.title;
    title.addEventListener("input", () => this._change("title", title.value));
    this._field(fields, "Title", title);
    const filter = element("select");
    for (const [value, label] of Object.entries(FILTERS)) {
      const option = element("option", "", label);
      option.value = value;
      filter.append(option);
    }
    filter.value = this._config.filter;
    filter.addEventListener("change", () => this._change("filter", filter.value));
    this._field(fields, "Show", filter);
    const limit = element("input");
    limit.type = "number";
    limit.min = "1";
    limit.max = "50";
    limit.step = "1";
    limit.value = String(this._config.limit);
    limit.addEventListener("change", () => {
      if (limit.value && limit.checkValidity()) this._change("limit", limit.valueAsNumber);
      else limit.reportValidity();
    });
    this._field(fields, "Maximum concerts per list section (1-50)", limit);
    for (const [key, label] of [["show_location", "Show city and country"], ["show_songs", "Show listed song counts"], ["group_by_visit", "Group by concert visit"]]) {
      const checkbox = element("input");
      checkbox.type = "checkbox";
      checkbox.checked = this._config[key];
      checkbox.addEventListener("change", () => this._change(key, checkbox.checked));
      this._field(fields, label, checkbox);
    }
    fields.append(element("p", "", "Only concerts sensors are listed; renamed entities and multiple accounts are supported. If none appear, finish setting up setlist.fm and wait for a successful refresh. Card filters can narrow the integration's display list, not fetch additional concerts."));
    fields.append(element("p", "", "Grouping is off by default. When enabled, the section limit counts venue-day visits instead of performances. Requires an updated integration; all listed artists keep their own setlist links."));
    this.shadowRoot.replaceChildren(style, fields);
    this._updateAccounts(true);
  }
}

if (!customElements.get("setlistfm-card-editor")) customElements.define("setlistfm-card-editor", SetlistFmCardEditor);
window.customCards = window.customCards || [];
for (const [preset, details] of Object.entries(PRESETS)) {
  const type = `setlistfm-${preset}-card`;
  if (!customElements.get(type)) {
    customElements.define(type, class extends SetlistFmCard { static preset = preset; });
  }
  if (!window.customCards.some((card) => card.type === type)) {
    window.customCards.push({
      type, name: `setlist.fm ${details.name}`, description: details.description,
      preview: true, documentationURL: DOCUMENTATION,
      getEntitySuggestion: (hass, entityId) => isConcertsEntity(hass, entityId)
        ? { config: { type: `custom:${type}`, ...customElements.get(type).getStubConfig(hass, [entityId]) } }
        : null,
    });
  }
}
