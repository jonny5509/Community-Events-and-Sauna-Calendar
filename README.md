# Chastity Events

A custom [Home Assistant](https://www.home-assistant.io/) integration with recurring challenge and LGBTQ+ observance calendars, sensors, and best-effort discovery of public events across the configured country.

> **Important:** This is a broad discovery tool, not a complete or verified event directory. Public adult-only listings are included when indexed by the sources. Always verify dates, age restrictions, access requirements, and venues with the organiser.

## Features

- Monthly challenge and Pride/observance calendars.
- Focused event sensors for monthly and LGBTQ+ events, plus **Nearest Sauna** and **Next Sauna Event** sensors. The nearest-sauna sensor looks for OpenStreetMap venues within 30 km of the configured location and exposes distance, address, website, phone, map link, and up to five other nearby listings. The next-sauna-event sensor selects the next dated discovery result that mentions a sauna and exposes its listing details.
- Broad searches for community festivals, conventions, meetups, workshops, arts/music events, kink/fetish and chastity events, Pride/LGBTQ+ listings, and public adult-only listings.
- Sauna venue lookup uses OpenStreetMap within 30 km first. If OSM returns no nearby venues, it uses a small maintained fallback index based on the [Gay Sauna Guide UK directory](https://www.gaysaunaguide.net/gay-saunas-in-the-uk/) and geocodes only entries matching the configured town/city. Number 52 Sauna in Newcastle also has its own address-based fallback. The directory index is not fetched or scraped at runtime and may need manual updates; the duplicate Number 52 entry has been removed from this index, while its separate Newcastle address-based fallback remains. Fallback results depend on Nominatim geocoding. The sensor refreshes at 00:00, 06:00, 12:00, and 18:00 Home Assistant local time. The sensor uses the configured location, not live device GPS.
- Google News RSS works without credentials. Optional Ticketmaster Discovery API support provides structured event dates, venue details, and source links.
- Deduplication merges matching title/date listings while retaining category tags and source links; distinct events on the same venue page remain separate.
- Number 52 Sauna discovery checks its main events calendar, offers page, and individual repeating-event pages for its published themed nights. It also generates the published 1st/3rd Thursday and 2nd/4th Thursday schedules, plus recurring offers when the official offers page still matches. Rotating Friday/Saturday themes are taken from dated event-page data where available; verify dates with the venue.

## Installation

### HACS
1. Open HACS and choose **Custom repositories**.
2. Add `jonny5509/Chastity-Events` as an **Integration**.
3. Download the integration and restart Home Assistant.
4. Add it from **Settings → Devices & services → Add integration**.

### Manual
Copy `custom_components/chastity_calendar` to `config/custom_components/`, restart Home Assistant, and add the integration. The internal domain remains `chastity_calendar` to preserve existing configuration and entity IDs.

## Configuration

During setup, choose a country, then narrow the location by region/state and county/sub-region where available. Enter the city or town as free text so small towns, rural locations, and places missing from third-party lists can still be configured. The optional district/neighbourhood list is looked up using OpenStreetMap Nominatim/Overpass and uses the city, county, region, and country to disambiguate the search. Country and region lists use online services with built-in country fallbacks; if a service is unavailable, skip the optional region/county/area levels and enter the city manually. Existing configurations with the older free-text location are retained. The combined location is used for event relevance.

The optional **Ticketmaster Discovery API key** enables searches through the [Ticketmaster Developer Portal](https://developer.ticketmaster.com/products-and-docs/apis/discovery/v2/). Obtain a key from Ticketmaster and enter it during setup or in **Configure**. If omitted, Google News RSS still runs.

### Optional daily participation crowns

In the configuration form or **Configure** settings, select any combination of **EmlaLock**, **Chastify**, and **Chaster** (including none) to choose which services are checked. Credentials for unselected services are ignored. The form accepts credentials for each service; these are optional and are used only for read-only active-session checks. For Chastify, follow the [Developer API guide](https://docs.chastify.net/developer-api/external-api-programs/) to open Developer API in Chastify and create a user-wide DEV key with `locks:read` permission. EmlaLock uses your user ID and API key; Chastify uses a user-wide Developer API token with read permission (a specific lock ID can optionally be supplied); Chaster uses a developer or OAuth access token with lock-read access. See the official [EmlaLock API](https://about.emlalock.com/docs/api/info/), [Chastify Developer API](https://docs.chastify.net/developer-api/external-api-programs/), and [Chaster Public API](https://docs.chaster.app/api/basics/getting-started/) documentation for how to obtain credentials and required permissions.

When a configured provider explicitly confirms an active session, the integration records at most one 👑 crown for that Home Assistant local calendar day. Crowns appear as all-day entries on **Monthly Events** only. The integration stores only the verified dates, not session details. It does not backfill earlier days, and an API error, missing credentials, or ambiguous response never earns a crown. A crown means a provider confirmed an active session at least once during that day; it does not imply continuous activity for the entire day. Credentials are stored with the Home Assistant config entry, so use only your own credentials and revoke tokens you no longer want to use.

## Expanded kink and fetish discovery

- Expand public-event searches for leather, rubber/latex, rope and shibari, pup/pet play, fetish conventions and gear socials, foot/boot fetish, power exchange, findom, furry communities, and fetish fashion. For kink/fetish, chastity, adult, and LGBTQ+ searches, inspect a bounded number of result pages for structured event start dates when search snippets omit dates. Source-focused searches include the REGULATION UK Fetish Calendar, fetish.events, KinkReady, The Fetish Network, Other Nights, OutSavvy, London Alternative Market, Skiddle, and DICE; indexed-search hints are not direct integrations with those sites.
- Add informational entries for International Fetish Day (third Friday in January) and World BDSM Day, plus suggested consent, rope education, leather/gear, rubber/latex, power-exchange reflection, and community-social reminders.
- When a page publishes structured event start-date metadata, use that event date rather than dropping the listing because its search snippet lacks a date. Store whether a date came from a snippet or event-page metadata, and retain the source URL for verification. Community-created prompts are labelled as suggestions rather than official observances. Public event listings still require organiser verification.

## What's new in 2.3.1

- Remove the four redundant calendar activity status sensors. The Monthly Events, LGBTQ+ Events, Sauna Events, and Kink & Fetish Events calendars are the single entities for those event groups.
- Keep the other focused event and sauna sensors, which provide separate information such as the next event or nearest sauna.
- Bump the integration manifest version to 2.3.1.

After upgrading and reloading the integration, Home Assistant may retain an old registry entry for a removed status sensor. If it remains, remove the orphaned sensor entity from **Settings → Devices & services → Entities**; do not remove the corresponding calendar entity.

## What's new in 2.0.8

- Ensure discovered timed events use timezone-aware datetimes before constructing Home Assistant calendar events, preventing calendar state updates from failing validation.
- Compare timed events with timezone-aware range bounds and sort mixed all-day/timed events consistently.
- Correct escaped regular expressions in future-date parsing so yearless, abbreviated-month, and UK numeric dates are recognised.
- Add regression coverage for calendar timezone handling and date parsing.
- Add optional, read-only active-session checks for EmlaLock, Chastify, and Chaster; users can select none, one, two, or all three providers in setup or Configure settings.
- Award at most one crown per Home Assistant local calendar day, even if multiple selected providers confirm an active session; display the crown as an all-day entry on Monthly Events only.
- Never award crowns when a provider check fails or its response does not explicitly verify an active session.
- Update the integration manifest to 2.0.8.

## What's new in 2.0.6

- Fix missed upcoming LGBTQ+ listings when search snippets show dates without a year, use abbreviated month names, or use UK numeric date formats.
- Increase bounded structured-date lookups for LGBTQ+ results from four to eight pages per search when snippets omit dates.
- Add regression tests for yearless, abbreviated-month, rollover, and UK numeric dates.
- Update the integration manifest to 2.0.6.

## What's new in 2.0.5

- Expand Number 52 discovery to individual repeating-event pages for its published themed nights.
- Generate the published 1st/3rd Thursday and 2nd/4th Thursday occurrences while retaining dated event-page listings for rotating Friday/Saturday themes.
- Keep the nearest-sauna filter from 2.0.4; Number 52 events are still included only when Number 52 is the nearest mapped sauna.
- Update the integration manifest to 2.0.5.

## What's new in 2.0.4

- Include Number 52 Sauna events only when Number 52 is the closest mapped sauna to the configured location within the 30 km sauna-discovery radius.
- Apply the same rule to Number 52 results from official pages and Google News RSS, so distant listings cannot bypass the nearest-sauna check.
- Update the integration manifest to 2.0.4.

## What's new in 2.0.3

- Improve LGBTQ+ event discovery when search snippets omit dates by inspecting up to four linked results per LGBTQ+ search for explicit Schema.org `Event.startDate` or `event:start_time` metadata.
- Never substitute generic article publication dates for event dates; listings without a reliable future event date remain excluded.
- Bound each page lookup to six seconds and cap lookups per query to limit added latency.
- Retain the 2.0.2 timeout/retry protection.
- Only include Number 52 Sauna events when Number 52 is the closest mapped sauna within the configured 30 km sauna-discovery radius; apply the same rule to official-page and RSS results.
- Update the integration manifest to 2.0.3.

## What's new in 2.0.2

- Fix discovery timeouts leaving the LGBTQ+ and other event calendars empty until the next scheduled six-hour refresh.
- Increase the overall discovery timeout from 60 to 180 seconds to accommodate the concurrent public-source searches.
- Automatically retry discovery two minutes after a timeout, retaining any events already loaded and exposing retry status in diagnostics.
- Log successful discovery counts to make it easier to verify that searches are returning events.
- Update the integration manifest to 2.0.2.

## What's new in 2.0.1

- Add a dedicated **LGBTQ+ Events** calendar for discovered gay, lesbian, bisexual, transgender, queer, and Pride listings. These events are filtered out of Monthly Events; sauna-related LGBTQ+ events may appear in both relevant focused calendars.
- Rename the former Pride-focused calendar to **LGBTQ+ Events** while preserving its unique ID for existing installations.
- Add regression tests for routing LGBTQ+ events away from the general calendar.
- Update the integration version and discovery user agent to 2.0.1.

## What's new in 2.0.0

- Broaden LGBTQ+ discovery with additional focused searches for OutSavvy, Eventbrite UK, Meetup, Gaydio, and Attitude, alongside Queer LDN and wherequeersgo.
- Run the added source-focused searches through the same location-aware Google News RSS pipeline; these are indexed-search hints, not direct integrations with those services.
- Add regression coverage for URL normalisation and date extraction boundaries.
- Update the integration manifest and source user-agent to 2.0.0.

## Event data

Events can expose `category`, overlapping `categories`, `source`, `sources`, `url`, `source_links`, `location`, `date_confidence`, and `last_seen`. RSS dates are inferred from snippets and may be wrong. Ticketmaster dates are taken from structured records when available. Cross-source title/date matches merge when possible; distinct events published on the same venue page remain separate. The integration manifest version for the duplicate status-sensor removal is 2.3.1 (earlier release notes below describe their original releases). Subsequent scheduled refreshes update the current results.

## Transparent limitations

- No source can discover every event or every post. Private groups, login-only social posts, closed mailing lists, and unindexed websites cannot reliably be searched.
- RSS returns a limited set of indexed results. Snippets may omit dates or include irrelevant dates.
- Ticketmaster requires an API key and covers only its catalogue and supported countries; it is not a universal event directory.
- Keyword-derived categories may overlap or be incorrect.
- Country search terms improve relevance but do not guarantee the event is physically in the country. Venue details are shown only when supplied by a source.
- Adult-only events are included when publicly indexed, but eligibility and age restrictions must be checked with the organiser.
- Zero results means no matching dated listing was found, not that no events exist.

## Event Hub (2.2.5)

The Event Hub adds four Home Assistant button entities associated with a dedicated **Chastity Events** device. In 2.2.1, all calendar and sensor entities also declare this same device association, so the integration's entities appear together on the device page instead of under **Ungrouped**:

- **Next Event Information** — creates/updates a persistent notification with the next discovered event's date, description, source and real source URL when available.
- **Next Event Directions** — creates a notification with a Google Maps search link when the event has a location; otherwise it explains that location data is missing.
- **Next Sauna Event Information** — the same event details for the next discovered sauna-related event.
- **Next Sauna Event Directions** — a map link for the next sauna event when a venue/location is available.

The buttons use current coordinator data, skip expired or undated records, and show a helpful notification when no matching event or source URL is available. They do not fabricate event addresses or links. The controls appear as buttons on the integration's device page after Home Assistant reloads the integration.

### What's new in 2.2.5

- Fix six calendar-routing regression tests that still used the old calendar constructor and failed with a missing `entry_id` argument.
- Keep the v2.2.4 event-sensor title cleanup across all event sensor states while leaving full event details in calendar entities.
- Keep the Nearest Sauna venue attributes unchanged.
- Update the integration manifest version to 2.2.5.

### What's new in 2.2.4

- Apply event-title cleanup consistently to all event sensor states, including Next Month Event, Past LGBTQ Event, Next LGBTQ Event, and category-specific event sensors such as Next Queer Event.
- Remove the appended `Tickets` suffix and the ticketing/date/time text that follows it, case-insensitively.
- Keep full source event details in calendar entities and preserve the Nearest Sauna venue attributes.
- Add regression tests for event sensor title cleanup and bump the integration manifest version to 2.2.4.

### What's new in 2.2.1

- Associate all calendar entities and all sensor entities with the same integration device used by the Event Hub buttons, fixing entities appearing under **Ungrouped**.
- Keep existing unique IDs, sensor logic, calendar logic, discovery, and configuration intact.
- Update the integration manifest version to 2.2.1.

### Add the Event Hub dashboard

Home Assistant integrations cannot safely install or modify a user's Lovelace dashboard automatically. Import the example view from [dashboards/event_hub.yaml](dashboards/event_hub.yaml) into a dashboard (Dashboard → Edit dashboard → Raw configuration editor), or copy its cards into an existing dashboard. Check **Developer tools → States** and replace entity IDs in the sample if Home Assistant assigned different IDs. The example brings the integration's existing capabilities into one place: all four calendars (including the dedicated Kink & Fetish Events calendar), every existing event and sauna sensor (including category-specific LGBTQ+ sensors), and all four action buttons. Existing entities are retained rather than replaced. The dashboard YAML is a starting template; if entity IDs differ on your Home Assistant instance, adjust them in the dashboard editor.


## Troubleshooting diagnostics

Home Assistant's integration diagnostics download includes the last discovery attempt, last successful update, current discovery status, any top-level discovery error, and event counts by source and category. API keys and other credential-like config fields are excluded. These details help distinguish an empty search result from a timed-out or failed discovery run.

## Privacy

Configured country/location terms are sent to Google News RSS; if enabled, search terms and country code are sent to Ticketmaster. Do not enter private information in the location field. Do not publish API keys.

## Contributing

Bug reports and pull requests are welcome. Include Home Assistant version and logs with personal information removed.


### Selecting the dedicated kink and fetish calendar

The integration exposes a separate **Kink & Fetish Events** calendar entity alongside Monthly Events, LGBTQ+ Events, and Sauna Events. After the updated integration is installed and Home Assistant reloads it, select the Kink & Fetish Events entity in the Home Assistant Calendar dashboard or use its entity ID in a calendar card/automation. Events are included when discovery returns a dated event and its metadata or text identifies it as kink/fetish-related; this is not a guarantee that every listing on every external website will be imported.
