"""
Wikipedia summaries for tree species.

Text only. The species thumbnail is managed separately (uploaded by a
superadmin), so no image from Wikipedia is ever used.

Wikipedia is a general reference, not a DENR source. The panel shows
this text as background reading, always credited, and the ecological
ranges the recommender uses still come from the reference dataset.

LICENCE
Wikipedia text is available under CC BY-SA 4.0. Reuse requires credit
and a link to the article, which the info panel shows under the text.

Uses the standard library (urllib) so no new dependency is needed.
"""

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

SUMMARY_URL = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"

# Wikimedia asks API clients to identify themselves.
USER_AGENT = "PuNoObservation/1.0 (reforestation species reference panel)"

TIMEOUT_SECONDS = 8

LICENSE_NAME = "CC BY-SA 4.0"
LICENSE_URL = "https://creativecommons.org/licenses/by-sa/4.0/"


class WikipediaUnavailable(Exception):
    """Wikipedia could not be reached. The result must not be saved."""


def fetch_summary(scientific_name):
    """
    Summary of the English Wikipedia article for a scientific name.

    Returns {"title", "extract", "url"}, or None when there is no usable
    article (not found, a disambiguation page, or an empty extract).
    Raises WikipediaUnavailable for network and server errors, so a
    temporary outage is never saved as "no article".

    The scientific name is used, not the common name. "Supa" or "Acle"
    could land on an unrelated article; "Sindora supa" cannot.
    """
    if not scientific_name or not scientific_name.strip():
        return None

    title = urllib.parse.quote(
        scientific_name.strip().replace(" ", "_"), safe="")
    req = urllib.request.Request(
        SUMMARY_URL.format(title=title),
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise WikipediaUnavailable(
            f"Wikipedia returned an error (HTTP {exc.code}).") from exc
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise WikipediaUnavailable("Wikipedia could not be reached.") from exc

    # "standard" is a normal article. Anything else, such as
    # "disambiguation", does not describe one species.
    if data.get("type") != "standard":
        return None

    extract = (data.get("extract") or "").strip()
    if not extract:
        return None

    url = ((data.get("content_urls") or {}).get("desktop") or {}).get("page")
    # The link is put into the page, so only a plain https URL is kept.
    if not (isinstance(url, str) and url.startswith("https://")):
        url = None

    return {
        "title": data.get("title") or scientific_name,
        "extract": extract,
        "url": url,
    }


def refresh_species_summary(species):
    """
    Fetch the summary and store it on a TreeSpecie row.

    The caller commits. Raises WikipediaUnavailable without changing the
    row, so a saved summary survives a failed refresh.
    """
    summary = fetch_summary(species.scientific_name)

    species.wiki_title = summary["title"] if summary else None
    species.wiki_extract = summary["extract"] if summary else None
    species.wiki_url = summary["url"] if summary else None
    species.wiki_fetched_at = datetime.utcnow()
    return summary
