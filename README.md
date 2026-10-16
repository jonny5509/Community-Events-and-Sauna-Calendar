# Community Events Calendar

A custom [Home Assistant](https://www.home-assistant.io/) integration for discovering public community events and displaying them in focused calendars and sensors.

> **Please verify listings with the organiser.** Event discovery is best-effort: dates, availability, age restrictions, access requirements, and venue details may be incomplete or change.

## Features

- **Three calendars:** Monthly Events, LGBTQ+ Events, and Kink & Fetish Events.
- **Event sensors:** ongoing and next monthly event, past and next LGBTQ+ event, and next-event details for LGBTQIA+ categories exposed through the `next_lgbtq_event` sensor attributes.
- **Community-interest sensors:** next furry event and next kink/fetish event.
- **Event Hub buttons:** create notifications with next-event details and map links when source and location data are available.
- **Personal attendance tracking:** save Interested, Going, or Not going for individual event occurrences.
- **Going reminders:** persist attendance choices and send a Home Assistant dashboard notification plus notifications to configured Home Assistant mobile apps exactly 24 hours before an event starts.
- **Multiple discovery sources:** Google News RSS works without credentials. An optional Ticketmaster Discovery API key can add structured event listings and venue details.
- **Event deduplication:** matching title/date listings are combined where possible while retaining source links and category information.
- **Optional daily participation crowns:** read-only active-session checks for EmlaLock, Chastify, and Chaster can add at most one crown per local calendar day to Monthly Events.

## Installation

### HACS

If the integration is available in the HACS default store, search for **Community Events Calendar** and download it.

If it is not listed yet:

1. Open **HACS → Custom repositories**.
2. Add `jonny5509/community-events-calendar` and choose **Integration** as the category.
3. Download the integration.
4. Restart Home Assistant.
5. Go to **Settings → Devices & services → Add integration** and search for **Community Events Calendar**.

### Manual installation

1. Copy `custom_components/chastity_calendar` into your Home Assistant `config/custom_components/` directory.
2. Restart Home Assistant.
3. Open **Settings → Devices & services → Add integration** and add **Community Events Calendar**.

The internal integration domain remains `chastity_calendar` to preserve existing configuration and retained entity IDs.

### Upcoming Events dashboard card

The optional **Community Events Calendar — Upcoming Events** Lovelace card lists upcoming events from selected calendar entities and adds a one-tap **Going** button beside each event. Attendance choices are saved by the integration.

1. Copy `www/chastity-upcoming-events-card.js` into your Home Assistant `config/www/chastity-upcoming-events-card.js`.
2. In **Settings → Dashboards → Resources**, add `/local/chastity-upcoming-events-card.js` as a **JavaScript module**.
3. Add a **Manual** card with this YAML, replacing entity IDs with those in your installation:

```yaml
type: custom:chastity-upcoming-events-card
title: Upcoming Events
days: 60
max_events: 30
entities:
  - calendar.chastity_calendar_monthly
  - calendar.chastity_calendar_pride
  - calendar.chastity_calendar_kink
```

The card uses Home Assistant's calendar event API and the `chastity_calendar.set_event_attendance` service.

## Configuration

During setup, choose a country and then select any available region, county, or district options. Enter your town or city as free text. If optional location lists are unavailable, skip them and enter the city manually.

The configured location is used to improve event relevance.

### Optional Ticketmaster support

Create an API key in the [Ticketmaster Developer Portal](https://developer.ticketmaster.com/products-and-docs/apis/discovery/v2/) and enter it during setup or in the integration's **Configure** options. Without a key, Google News RSS discovery still works.

### Optional daily participation crowns

In setup or **Configure**, select any combination of **EmlaLock**, **Chastify**, and **Chaster**, or select none. Add the credentials for the providers you choose:

- [EmlaLock API](https://about.emlalock.com/docs/api/info/) — user ID and API key.
- [Chastify Developer API](https://docs.chastify.net/developer-api/external-api-programs/) — a user-wide Developer API token with read-only `locks:read` permission. A lock ID may optionally be supplied.
- [Chaster Public API](https://docs.chaster.app/api/basics/getting-started/) — a developer or OAuth access token with lock-read access.

Crowns are added only when a selected provider explicitly confirms an active session. At most one all-day crown is recorded per Home Assistant local calendar day, on **Monthly Events** only. The integration does not backfill earlier days or award a crown for errors, missing credentials, or ambiguous responses. A crown confirms activity at least once that day; it does not mean a session lasted all day.

Credentials are stored with the Home Assistant config entry. Use your own credentials and revoke tokens you no longer need.

## Event discovery and calendars

The integration searches for publicly indexed LGBTQ+ and Pride events, community meetups, festivals, conventions, arts and music events, and kink/fetish-related events. Searches may include leather, rubber/latex, rope and shibari, pup/pet play, chastity, fetish fashion, furry communities, and related social events.

Searches can use indexed results from event platforms and community calendars. A source name in a search query does **not** mean the integration directly connects to or officially partners with that site.

The dedicated **Kink & Fetish Events** calendar keeps matching events separate from the general monthly calendar. LGBTQ+ events are routed to **LGBTQ+ Events**; some events may appear in more than one focused calendar when they fit multiple categories.

### Personal attendance and reminders

Use the `chastity_calendar.set_event_attendance` service to save your choice for an event occurrence. Choices are stored locally by Home Assistant and survive restarts. Marking an event `going` schedules a reminder exactly 24 hours before its start; changing it to `interested` or `not_going` cancels the pending reminder. If the 24-hour point has already passed when you mark Going, no late reminder is sent.

Example service action (replace the title, start time, and URL with the event's actual details):

```yaml
action: chastity_calendar.set_event_attendance
data:
  summary: Local Community Event
  start: "2026-11-05T18:00:00+00:00"
  status: going
  url: "https://example.com/event"
```

Use `status: interested` to save a maybe, or `status: not_going` to record that you will not attend. Include the exact start date/time for that occurrence; use an ISO date for an all-day event. The integration creates a persistent dashboard notification and sends phone notifications through configured `notify.mobile_app_*` services. At least one Home Assistant mobile app must be registered for phone delivery. This service stores your choice, but it does not add interactive attendance controls directly inside Home Assistant's standard calendar card; you can call it from Developer Tools → Actions or a dashboard script/button.

### Event Hub dashboard

Home Assistant integrations cannot automatically install or modify your dashboard. To use the example dashboard:

1. Open [`dashboards/event_hub.yaml`](dashboards/event_hub.yaml).
2. Import or copy its cards using your dashboard's **Raw configuration editor**.
3. Check **Developer tools → States** and adjust entity IDs if Home Assistant assigned different ones.

The example includes the calendars, event sensors, and Event Hub buttons. It is a starting template; customise it to suit your dashboard.

## Limitations

- Discovery cannot reliably access private groups, login-only posts, closed mailing lists, or websites that are not indexed.
- RSS results are limited; snippets may omit dates or contain irrelevant dates.
- Ticketmaster covers only its own catalogue and supported countries.
- Dates inferred from snippets can be wrong. Structured event dates are used when available, but listings should still be verified.
- Keyword-based categories can overlap, be incorrect, or miss events whose descriptions do not use expected terms.
- A configured country improves relevance but does not guarantee that an event physically takes place there.
- Adult-only listings may appear when publicly indexed. Check age limits and entry requirements with the organiser.
- No results means no matching dated listing was found; it does not mean no events exist.

## Troubleshooting

If a calendar or sensor is empty, check the integration logs and diagnostics. Diagnostics include discovery status, recent attempts, top-level errors, and event counts by source and category. Credential-like configuration fields are excluded.

If a dashboard referenced a retired identity-specific event sensor, switch it to the **Next LGBTQ Event** sensor and read the relevant entry under `next_events_by_category`. The individual identity-specific entities are intentionally removed during setup to avoid leaving stale, unavailable entities in the registry.

If the dashboard example does not work, confirm the actual entity IDs under **Developer tools → States** and update the YAML accordingly.

## Privacy

Configured country and location terms are sent to Google News RSS; if Ticketmaster is enabled, search terms and country code are also sent to Ticketmaster.  Do not put private information in location fields or publish API keys.

## Contributing

Bug reports and pull requests are welcome. Include your Home Assistant version and relevant logs, with personal information and credentials removed.

## License

This project is licensed under the [MIT License](LICENSE).
