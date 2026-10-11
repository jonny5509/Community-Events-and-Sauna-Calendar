# calendar-events

## Chastity Challenge Calendar for Home Assistant

This repository now includes a custom Home Assistant integration at
`custom_components/chastity_calendar`. It exposes a real `calendar` entity
with annual all-day entries for Locktober, No Nut November, and other chastity-
themed online community challenges.

### Included events

- International Male Chastity Day — 14 January (informal)
- Jailbird January
- Feminized February
- Maleless March
- Abstinence April
- You May Not Cum
- Summer Chastity Challenge (suggested theme)
- Midyear Chastity Challenge (suggested theme)
- Anal Only August
- Sissy September
- Locktober — 1–31 October
- No Nut November — 1–30 November
- Denied December
- Chastity Advent Calendar — 1–24 December (suggested theme)

**Accuracy note:** Locktober and No Nut November are well-known online challenges.
Several other names are niche, community-created themes or suggested ideas, not
official observances. This integration labels them in each event description.

### Install

1. Copy `custom_components/chastity_calendar` into your Home Assistant
   configuration directory, preserving the folder structure.
2. Restart Home Assistant.
3. Open **Settings → Devices & services → Add integration**.
4. Search for **Chastity Challenge Calendar** and add it.
5. Open **Settings → Dashboards → Resources** only if you are using a separate
   custom card; the standard Home Assistant Calendar card needs no extra resource.
6. Add a **Calendar** card to a dashboard and select the new calendar entity.
   The entity ID will usually be `calendar.chastity_challenge_calendar` or
   similar; verify it under **Developer tools → States**.

Example dashboard card YAML (replace the entity ID with the one shown in your
instance):

```yaml
type: calendar
initial_view: month
entities:
  - calendar.chastity_challenge_calendar
```

### Example automation

This example sends a notification when the Locktober calendar event starts.
Change `notify.notify` to a notification service configured in your Home
Assistant instance.

```yaml
alias: Locktober starts
triggers:
  - trigger: calendar
    entity_id: calendar.chastity_challenge_calendar
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

### Online event discovery

The integration also searches Google News public RSS results for several chastity/community-event and LGBTQ+ queries at startup and every 12 hours. During setup, enter a **country** (required) and optionally a **city, state, province, or region** to narrow the search. You can change these later under the integration's **Configure** options. The country selects a Google News edition where supported and is also added to search queries; the optional location is added to queries as a relevance filter. Results are not guaranteed to physically take place in the selected area because public search snippets are imperfect.

It adds a result only when it can extract an explicit date within the next two years. These entries are prefixed **Possible event:** and marked unverified; their descriptions include the original search-result link. Please verify dates before relying on them. The built-in recurring challenge entries remain unchanged and are not country-filtered.

This is best-effort discovery, not a search of the entire internet. Search engines may miss private groups, social posts, event platforms, or pages they have not indexed. It requires Home Assistant to have internet access. If the search service is temporarily unavailable, the recurring built-in calendar entries remain available.

### Notes

- The built-in annual events are generated locally. Online discovery uses public Google News RSS feeds and the configured country/location as search filters.
- Google News country editions are mapped for common countries; other country names are still included in the query, but use the global/US English feed edition. This is best-effort geographic filtering, not a strict geofence.
- This is a calendar and reminder integration only. It does not control any device.
- Challenges involving intimacy or sexual activity should always be consensual.
- This is an initial custom integration; validate it against your Home Assistant
  version before relying on it for important automations.
