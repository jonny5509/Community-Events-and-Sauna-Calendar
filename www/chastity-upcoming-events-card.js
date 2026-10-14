class ChastityUpcomingEventsCard extends HTMLElement {
  setConfig(config) {
    if (!config.entities || !Array.isArray(config.entities) || !config.entities.length) {
      throw new Error("Please configure one or more Chastity Events calendar entities.");
    }
    this.config = {
      days: Math.min(Math.max(Number(config.days || 60), 1), 365),
      max_events: Math.min(Math.max(Number(config.max_events || 30), 1), 100),
      title: config.title || "Upcoming Events",
      entities: config.entities,
    };
    this._events = [];
    this._loading = false;
    this._error = "";
    this._lastRefresh = 0;
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._initialized) {
      this._initialized = true;
      this._refresh();
      this._timer = window.setInterval(() => this._refresh(), 5 * 60 * 1000);
    }
    this._render();
  }

  disconnectedCallback() {
    if (this._timer) window.clearInterval(this._timer);
    this._timer = undefined;
  }

  getCardSize() {
    return Math.max(3, Math.min((this._events || []).length + 1, 8));
  }

  async _refresh() {
    if (!this._hass || this._loading) return;
    this._loading = true;
    this._error = "";
    const now = new Date();
    const end = new Date(now.getTime() + this.config.days * 86400000);
    const dateOnly = (d) => {
      const local = new Date(d.getTime() - d.getTimezoneOffset() * 60000);
      return local.toISOString().slice(0, 10);
    };
    try {
      const results = await Promise.all(this.config.entities.map(async (entity) => {
        try {
          const response = await this._hass.callWS({
            type: "calendar/list_events",
            entity_id: entity,
            start_date: dateOnly(now),
            end_date: dateOnly(end),
          });
          return (response.events || []).map((event) => ({ ...event, _entity: entity }));
        } catch (err) {
          return [];
        }
      }));
      const unique = new Map();
      for (const event of results.flat()) {
        const start = typeof event.start === "string" ? event.start : "";
        const key = [String(event.summary || "").trim().toLocaleLowerCase(), start].join("|");
        if (!unique.has(key)) unique.set(key, event);
      }
      this._events = [...unique.values()]
        .filter((event) => event.start && new Date(event.start) >= now)
        .sort((a, b) => new Date(a.start) - new Date(b.start))
        .slice(0, this.config.max_events);
      this._lastRefresh = Date.now();
    } catch (err) {
      this._error = "Couldn't load calendar events. Check the selected calendar entities.";
    } finally {
      this._loading = false;
      this._render();
    }
  }

  _attendance(event) {
    const state = this._hass?.states?.[event._entity];
    const records = state?.attributes?.attendance || [];
    const summary = String(event.summary || "").trim().toLocaleLowerCase();
    const eventStart = String(event.start || "");
    return records.find((record) =>
      String(record.summary || "").trim().toLocaleLowerCase() === summary &&
      (String(record.start || "").startsWith(eventStart.slice(0, 10)) ||
       eventStart.startsWith(String(record.start || "").slice(0, 10)))
    );
  }

  async _setGoing(event) {
    const record = this._attendance(event);
    const status = record?.status === "going" ? "not_going" : "going";
    try {
      await this._hass.callService("chastity_calendar", "set_event_attendance", {
        summary: event.summary,
        start: event.start,
        status,
        url: "",
      });
      await this._refresh();
    } catch (err) {
      this._error = "Couldn't save attendance. Confirm the attendance feature is installed.";
      this._render();
    }
  }

  _formatDate(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return new Intl.DateTimeFormat(undefined, {
      weekday: "short", day: "numeric", month: "short",
      hour: /T\d{2}:\d{2}/.test(value) ? "2-digit" : undefined,
      minute: /T\d{2}:\d{2}/.test(value) ? "2-digit" : undefined,
    }).format(date);
  }

  _render() {
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    const events = this._events || [];
    const rows = events.map((event, index) => {
      const attendance = this._attendance(event);
      const going = attendance?.status === "going";
      const location = event.location ? `<div class="location">${this._escape(event.location)}</div>` : "";
      return `<div class="event">
        <div class="details">
          <div class="name">${this._escape(event.summary || "Untitled event")}</div>
          <div class="date">${this._escape(this._formatDate(event.start))}</div>
          ${location}
          ${attendance ? `<div class="status">${this._escape(attendance.status.replace("_", " "))}</div>` : ""}
        </div>
        <button data-index="${index}" class="${going ? "going" : ""}" aria-pressed="${going}">
          ${going ? "✓ Going" : "Going"}
        </button>
      </div>`;
    }).join("");
    this.shadowRoot.innerHTML = `
      <ha-card header="${this._escape(this.config?.title || "Upcoming Events")}">
        <style>
          :host { display:block; }
          .content { padding: 0 16px 8px; }
          .event { display:flex; align-items:center; gap:12px; padding:14px 0; border-bottom:1px solid var(--divider-color); }
          .event:last-child { border-bottom:0; }
          .details { min-width:0; flex:1; }
          .name { font-weight:600; overflow-wrap:anywhere; }
          .date,.location,.status { color:var(--secondary-text-color); font-size:0.9em; margin-top:4px; }
          button { border:1px solid var(--primary-color); border-radius:18px; padding:7px 14px; color:var(--primary-color); background:transparent; font:inherit; cursor:pointer; white-space:nowrap; }
          button.going { background:var(--primary-color); color:var(--text-primary-color, white); }
          button:disabled { opacity:.6; }
          .message { color:var(--secondary-text-color); padding:16px 0; }
        </style>
        <div class="content">
          ${this._error ? `<div class="message">${this._escape(this._error)}</div>` : ""}
          ${this._loading && !events.length ? '<div class="message">Loading events…</div>' : ""}
          ${!this._loading && !events.length && !this._error ? '<div class="message">No upcoming events found in the selected calendars.</div>' : ""}
          ${rows}
        </div>
      </ha-card>`;
    this.shadowRoot.querySelectorAll("button[data-index]").forEach((button) => {
      button.addEventListener("click", () => {
        const event = events[Number(button.dataset.index)];
        if (event) this._setGoing(event);
      });
    });
  }

  _escape(value) {
    return String(value ?? "").replace(/[&<>"']/g, (char) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    })[char]);
  }
}

if (!customElements.get("chastity-upcoming-events-card")) {
  customElements.define("chastity-upcoming-events-card", ChastityUpcomingEventsCard);
}
window.customCards = window.customCards || [];
window.customCards.push({
  type: "chastity-upcoming-events-card",
  name: "Chastity Upcoming Events",
  description: "Upcoming Chastity Events with a one-tap Going button.",
  getEntitySuggestion: (_hass, entityId) => {
    if (!entityId.startsWith("calendar.chastity_calendar_")) return null;
    return {
      config: {
        type: "custom:chastity-upcoming-events-card",
        entities: [entityId],
      },
    };
  },
});
