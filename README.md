# Chastity Challenge Calendar

A custom [Home Assistant](https://www.home-assistant.io/) integration that adds two calendar entities, two sensors, and best-effort discovery of dated events from public Google News RSS results.

> **Important:** Online discoveries are unverified search results, not an authoritative event directory. Check the original organiser/source before relying on a date or location. Some recurring challenge names are informal or community-created rather than official observances.

## Features

- **Monthly Events calendar** — recurring challenge themes such as Locktober and No Nut November.
- **Pride EC Events calendar** — recurring LGBTQ+ observances, including Transgender Day of Visibility, Pride Month, National Coming Out Day, and World AIDS Day.
- **Next Event sensor** — shows the name of the current or next event, with start date, end date, and description attributes.
- **Upcoming Events sensor** — counts events active or starting in the next 30 days, with the counting window documented in its attributes.
- **Location-aware discovery** — configure a country and optional city/region to make public RSS searches more relevant.
- **UI configuration** — set up and edit the search area through Settings; no YAML configuration is required.

## Installation

### Install with HACS

1. Open **HACS** in Home Assistant.
2. Open the menu and choose **Custom repositories**.
3. Add `jonny5509/calendar-events` and select **Integration** as the category.
4. Find **Chastity Challenge Calendar** in HACS and download it.
5. Restart Home Assistant.
6. Go to **Settings → Devices & services → Add integration**, search for **Chastity Challenge Calendar**, and follow the setup flow.

If the repository becomes available directly in the HACS default catalogue, you can search for it without adding a custom repository.

### Manual installation

1. Copy `custom_components/chastity_calendar` into your Home Assistant `config/custom_components/` directory.
2. Restart Home Assistant.
3. Add **Chastity Challenge Calendar** from **Settings → Devices & services → Add integration**.

## Configuration

During setup, select a country and optionally enter a city, state, province, or region. You can change these values later through the integration's **Configure** option.

The country and location are used as search terms and to select a Google News edition where supported. They improve relevance but do **not** guarantee that a result physically takes place in the selected area.

## Entities and dashboard

The integration creates these entities:

| Entity | Contents |
| --- | --- |
| **Monthly Events calendar** | Recurring monthly challenge themes and discovered community events |
| **Pride EC Events calendar** | Recurring LGBTQ+ observances and discovered Pride-related events |
| **Next Event sensor** | Event name as its state; includes `start_date`, `end_date`, and `description` attributes |
| **Upcoming Events sensor** | Number of events active or starting in the next 30 days |

Exact entity IDs depend on your Home Assistant entity registry. Find them under **Developer tools → States**.

Add a standard **Calendar** card to a dashboard and select either or both calendars:

```yaml
type: calendar
initial_view: month
entities:
  - calendar.chastity_challenge_calendar_monthly
  - calendar.chastity_challenge_calendar_pride
```

You can also display the sensors in an Entities card or use them in templates and automations. For example, a template can read the next event date with `state_attr('sensor.chastity_calendar_next_event', 'start_date')`; verify the actual entity ID in your instance.

## Event discovery and limitations

The integration searches public Google News RSS results for dated community and Pride-related events. Searches are refreshed periodically. A result is included only when a future date within the supported search window can be extracted from the title or snippet.

- Online results are labelled **Possible event** and include the original result link.
- Search snippets can contain incorrect, ambiguous, or unrelated dates; always verify them.
- Search engines may miss local festivals, community listings, private groups, and social-media posts.
- If RSS discovery is unavailable, the built-in recurring calendar observances remain available.
- The built-in annual entries are informational; some challenge themes are informal or suggested ideas, not official holidays.

## Automation example

This example sends a notification when Locktober starts. Replace `notify.notify` and the entity ID with values from your Home Assistant installation.

```yaml
alias: Locktober starts
triggers:
  - trigger: calendar
    entity_id: calendar.chastity_challenge_calendar_monthly
    event: start
    offset: "0:0:0"
conditions:
  - condition: template
    value_template: "{{ trigger.calendar_event.summary == 'Locktober' }}"
actions:
  - action: notify.notify
    data:
      title: "Calendar challenge"
      message: "Locktober starts today."
mode: single
```

## Troubleshooting

- **Can't find the integration:** confirm the folder is named `custom_components/chastity_calendar`, restart Home Assistant, and check the logs.
- **No discovered local festivals:** RSS discovery is best-effort. Check the configured country/location and verify that Home Assistant has internet access.
- **A result has the wrong date or location:** follow the original link and treat the listing as unverified.

## Privacy and safety

The integration sends configured country/location terms to Google News RSS search URLs to retrieve public results. Do not enter private or sensitive information in the location field. This integration only provides calendar entries and reminders; it does not control devices. Any intimate or sexual activity should be consensual.

## Contributing

Bug reports and pull requests are welcome. Please include your Home Assistant version, relevant logs with personal information removed, and clear steps to reproduce the issue.
