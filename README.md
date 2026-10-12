# Chastity Challenge Calendar

A custom [Home Assistant](https://www.home-assistant.io/) integration with recurring challenge and LGBTQ+ observance calendars, sensors, and best-effort discovery of public events across the configured country.

> **Important:** This is a broad discovery tool, not a complete or verified event directory. Public adult-only listings are included when indexed by the sources. Always verify dates, age restrictions, access requirements, and venues with the organiser.

## Features

- Monthly challenge and Pride/observance calendars.
- Next Event, Upcoming Events, Event Locations, Nearby Saunas, and LGBTQ+ category sensors.
- Broad searches for community festivals, conventions, meetups, workshops, arts/music events, kink/fetish and chastity events, Pride/LGBTQ+ listings, and public adult-only listings.
- Google News RSS works without credentials. Optional Ticketmaster Discovery API support provides structured event dates, venue details, and source links.
- Deduplication merges repeated source URLs and matching title/date listings, retaining category tags and source links.
- Automatic event refresh every six hours; nearby sauna lookup refreshes every 24 hours.
- Nearby Saunas sensor geocodes the configured city/region and lists mapped sauna/public-bath venues within 20 km, nearest first, including distance, address when mapped, and website/map links where available.

## Installation

### HACS
1. Open HACS and choose **Custom repositories**.
2. Add `jonny5509/calendar-events` as an **Integration**.
3. Download the integration and restart Home Assistant.
4. Add it from **Settings → Devices & services → Add integration**.

### Manual
Copy `custom_components/chastity_calendar` to `config/custom_components/`, restart Home Assistant, and add the integration.

## Configuration

Choose a country, then optionally enter region/state, city/town, and district/area/postcode in that order. You can leave any lower level blank. The integration combines the entered levels for RSS relevance and uses the most specific combined location as the centre for the Nearby Saunas sensor. Sauna discovery uses OpenStreetMap's Nominatim geocoder and Overpass data; it searches a 20 km radius and refreshes daily. This is a best-effort map directory, not a complete adult-venue directory.

The optional **Ticketmaster Discovery API key** enables searches through the [Ticketmaster Developer Portal](https://developer.ticketmaster.com/products-and-docs/apis/discovery/v2/). Obtain a key from Ticketmaster and enter it during setup or in **Configure**. If omitted, Google News RSS still runs.

## Event data

Events can expose `category`, overlapping `categories`, `source`, `sources`, `url`, `source_links`, `location`, `date_confidence`, and `last_seen`. RSS dates are inferred from snippets and may be wrong. Ticketmaster dates are taken from structured records when available. Repeated URLs collapse even if a publisher updates the date; cross-source title/date matches merge when possible. Subsequent scheduled refreshes update the current results.

## Transparent limitations

- No source can discover every event or every post. Private groups, login-only social posts, closed mailing lists, and unindexed websites cannot reliably be searched.
- RSS returns a limited set of indexed results. Snippets may omit dates or include irrelevant dates.
- Ticketmaster requires an API key and covers only its catalogue and supported countries; it is not a universal event directory.
- Keyword-derived categories may overlap or be incorrect.
- Country search terms improve relevance but do not guarantee the event is physically in the country. Venue details are shown only when supplied by a source.
- Adult-only events are included when publicly indexed, but eligibility and age restrictions must be checked with the organiser.
- Nearby sauna coverage depends on OpenStreetMap tagging; adult-only venues and venue events may be missing, and the integration does not verify opening hours, age rules, or events hosted at each sauna.
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

## Privacy

Configured country/location terms are sent to Google News RSS; if enabled, search terms and country code are sent to Ticketmaster. Do not enter private information in the location field. Do not publish API keys.

## Contributing

Bug reports and pull requests are welcome. Include Home Assistant version and logs with personal information removed.
