# Community Events & Sauna Calendar

A custom [Home Assistant](https://www.home-assistant.io/) integration with recurring challenge and LGBTQ+ observance calendars, sensors, and best-effort discovery of public events across the configured country.

> **Important:** This is a broad discovery tool, not a complete or verified event directory. Public adult-only listings are included when indexed by the sources. Always verify dates, age restrictions, access requirements, and venues with the organiser.

## Features

- Monthly challenge and Pride/observance calendars.
- Focused event sensors for monthly and LGBTQ+ events, plus **Nearest Sauna** and **Next Sauna Event** sensors. The nearest-sauna sensor looks for OpenStreetMap venues within 30 km of the configured location and exposes distance, address, website, phone, map link, and up to five other nearby listings. The next-sauna-event sensor selects the next dated discovery result that mentions a sauna and exposes its listing details.
- Broad searches for community festivals, conventions, meetups, workshops, arts/music events, kink/fetish and chastity events, Pride/LGBTQ+ listings, and public adult-only listings.
- Sauna venue lookup uses OpenStreetMap within 30 km first. If OSM returns no nearby venues, it uses a small maintained fallback index based on the [Gay Sauna Guide UK directory](https://www.gaysaunaguide.net/gay-saunas-in-the-uk/) and geocodes only entries matching the configured town/city. Number 52 Sauna in Newcastle also has its own address-based fallback. The directory index is not fetched or scraped at runtime and may need manual updates; the duplicate Number 52 entry has been removed from this index, while its separate Newcastle address-based fallback remains. Fallback results depend on Nominatim geocoding. The sensor refreshes at 00:00, 06:00, 12:00, and 18:00 Home Assistant local time. The sensor uses the configured location, not live device GPS.
- Google News RSS works without credentials. Optional Ticketmaster Discovery API support provides structured event dates, venue details, and source links.
- Deduplication merges matching title/date listings while retaining category tags and source links; distinct events on the same venue page remain separate.
- Number 52 Sauna recurring offers are generated only when the current official offers page still matches the published offer wording. The integration does not assign guessed weekday recurrence to rotating themed nights; those should come from dated official listings.

## Installation

### HACS
1. Open HACS and choose **Custom repositories**.
2. Add `jonny5509/Community-Events-and-Sauna-Calendar` as an **Integration**.
3. Download the integration and restart Home Assistant.
4. Add it from **Settings → Devices & services → Add integration**.

### Manual
Copy `custom_components/chastity_calendar` to `config/custom_components/`, restart Home Assistant, and add the integration. The internal domain remains `chastity_calendar` to preserve existing configuration and entity IDs.

## Configuration

During setup, choose a country, then narrow the location by region/state and county/sub-region where available. Enter the city or town as free text so small towns, rural locations, and places missing from third-party lists can still be configured. The optional district/neighbourhood list is looked up using OpenStreetMap Nominatim/Overpass and uses the city, county, region, and country to disambiguate the search. Country and region lists use online services with built-in country fallbacks; if a service is unavailable, skip the optional region/county/area levels and enter the city manually. Existing configurations with the older free-text location are retained. The combined location is used for event relevance.

The optional **Ticketmaster Discovery API key** enables searches through the [Ticketmaster Developer Portal](https://developer.ticketmaster.com/products-and-docs/apis/discovery/v2/). Obtain a key from Ticketmaster and enter it during setup or in **Configure**. If omitted, Google News RSS still runs.

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

Events can expose `category`, overlapping `categories`, `source`, `sources`, `url`, `source_links`, `location`, `date_confidence`, and `last_seen`. RSS dates are inferred from snippets and may be wrong. Ticketmaster dates are taken from structured records when available. Cross-source title/date matches merge when possible; distinct events published on the same venue page remain separate. The integration manifest version for this release is 2.0.1. Subsequent scheduled refreshes update the current results.

## Transparent limitations

- No source can discover every event or every post. Private groups, login-only social posts, closed mailing lists, and unindexed websites cannot reliably be searched.
- RSS returns a limited set of indexed results. Snippets may omit dates or include irrelevant dates.
- Ticketmaster requires an API key and covers only its catalogue and supported countries; it is not a universal event directory.
- Keyword-derived categories may overlap or be incorrect.
- Country search terms improve relevance but do not guarantee the event is physically in the country. Venue details are shown only when supplied by a source.
- Adult-only events are included when publicly indexed, but eligibility and age restrictions must be checked with the organiser.
- Zero results means no matching dated listing was found, not that no events exist.

## Dashboard

```yaml
type: calendar
initial_view: month
entities:
  - calendar.chastity_challenge_calendar_monthly
  - calendar.chastity_challenge_calendar_pride
```

Exact entity IDs can vary; check **Developer tools → States**.

## Troubleshooting diagnostics

Home Assistant's integration diagnostics download includes the last discovery attempt, last successful update, current discovery status, any top-level discovery error, and event counts by source and category. API keys and other credential-like config fields are excluded. These details help distinguish an empty search result from a timed-out or failed discovery run.

## Privacy

Configured country/location terms are sent to Google News RSS; if enabled, search terms and country code are sent to Ticketmaster. Do not enter private information in the location field. Do not publish API keys.

## Contributing

Bug reports and pull requests are welcome. Include Home Assistant version and logs with personal information removed.
