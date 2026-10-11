# Contributing

Thank you for helping improve Chastity Challenge Calendar.

## Before opening an issue

- Search existing issues and pull requests to avoid duplicates.
- Include your Home Assistant version and the integration version.
- For bugs, describe the expected and actual behaviour and include clear reproduction steps.
- Remove access tokens, private URLs, personal details, and other sensitive information from logs.

## Pull requests

1. Open an issue first for substantial behaviour changes so the approach can be discussed.
2. Make focused changes on a branch; avoid unrelated formatting or refactoring.
3. Add or update tests for bug fixes and new behaviour.
4. Update the README or changelog when user-facing behaviour changes.
5. Run the checks below before requesting review.

## Local checks

Install Python 3.12 or newer, then run:

```bash
python -m pip install pytest ruff
ruff check custom_components tests
pytest
```

GitHub Actions also runs HACS validation and Home Assistant's hassfest validation on pull requests.

## Event discovery guidelines

- Treat Google News RSS as an unverified source of leads, not an authoritative event database.
- Keep the original result URL in event descriptions.
- Do not imply that a result is physically located in the configured area unless the source supports that claim.
- Only add dates that can be extracted explicitly and fall within the supported future window.
- Handle missing, malformed, duplicate, and unavailable RSS results without breaking recurring calendar events.
- Keep the distinction between monthly community challenges and Pride observances intact.

## Privacy and safety

Configured country and location values are used in public search queries. Do not include private or sensitive information in examples, logs, screenshots, or issue reports. Calendar entries are informational and must not trigger or control physical devices.
