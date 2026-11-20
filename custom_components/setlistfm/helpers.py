"""Shared helpers for the setlist.fm integration."""

from datetime import date, datetime
import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)


def concert_date(value: str) -> date:
    """Parse only canonical setlist.fm calendar dates, including early years."""
    parsed = datetime.strptime(value, "%d-%m-%Y").date()
    if value != f"{parsed.day:02d}-{parsed.month:02d}-{parsed.year:04d}":
        raise ValueError("Concert event date must use DD-MM-YYYY")
    return parsed


def dated_concerts(records: list[dict[str, Any]]) -> list[tuple[date, dict[str, Any]]]:
    """Associate valid records with dates without mutating their input order."""
    dated = []
    for record in records:
        try:
            dated.append((concert_date(record["eventDate"]), record))
        except (KeyError, TypeError, ValueError):
            _LOGGER.warning("Skipping concert with an invalid event date")
    return dated


def select_dated[T](
    records: list[tuple[date, T]], today: date, show: str, limit: int,
    *, visits: bool = False,
) -> list[T]:
    """Filter and bound records; preserve legacy ordering outside the visit view."""
    upcoming = sorted((item for item in records if item[0] >= today), key=lambda item: item[0])
    past = sorted((item for item in records if item[0] < today), key=lambda item: item[0], reverse=True)
    if show == "past":
        selected = past
    elif show == "upcoming":
        selected = upcoming if visits else sorted(upcoming, key=lambda item: item[0], reverse=True)
    elif show == "all":
        selected = upcoming + past if visits else sorted(records, key=lambda item: item[0], reverse=True)
    else:
        selected = []
    return [item for _, item in selected[:limit]]


def simplify_concert(concert: dict[str, Any]) -> dict[str, Any]:
    """Keep the legacy, intentionally small card record shape."""
    artist = concert.get("artist", {})
    venue = concert.get("venue", {})
    city = venue.get("city", {})
    return {
        "id": concert.get("id"),
        "date": concert.get("eventDate"),
        "artist": {"name": artist.get("name", "Unknown"), "mbid": artist.get("mbid")},
        "venue": {
            "name": venue.get("name", "Unknown"),
            "city": city.get("name", ""),
            "state": city.get("state", ""),
            "country": city.get("country", {}).get("name", ""),
        },
        "song_count": sum(len(item.get("song", [])) for item in concert.get("set", [])),
        "url": concert.get("url", ""),
    }


def normalize_username(username: str) -> str:
    """Return the lowercase username expected by the setlist.fm API."""
    return username.strip().lower()


def normalize_concert(record: Any) -> tuple[dict[str, Any], bool]:
    """Validate a concert and repair unusable optional fields without losing it."""
    if (
        not isinstance(record, dict)
        or not isinstance(record.get("id"), str)
        or not record["id"]
        or not isinstance(record.get("eventDate"), str)
    ):
        raise ValueError("Concert is missing an ID or event date")
    concert_date(record["eventDate"])
    repaired = False

    def mapping(value: Any) -> dict[str, Any]:
        nonlocal repaired
        if value is None:
            return {}
        if not isinstance(value, dict):
            repaired = True
            return {}
        return value

    def text(value: Any, default: str = "") -> str:
        nonlocal repaired
        if value is None:
            return default
        if not isinstance(value, str):
            repaired = True
            return default
        return value

    artist = mapping(record.get("artist"))
    venue = mapping(record.get("venue"))
    city = mapping(venue.get("city"))
    country = mapping(city.get("country"))
    # Prefer the documented representation, even when empty, never sum both.
    sets = record.get("set") if "set" in record else mapping(record.get("sets")).get("set")
    if sets is None:
        sets = []
    elif not isinstance(sets, list):
        repaired = True
        sets = []
    clean_sets = []
    for item in sets:
        if not isinstance(item, dict):
            repaired = True
            continue
        songs = item.get("song")
        if songs is None:
            songs = []
        elif not isinstance(songs, list):
            repaired = True
            songs = []
        clean_songs = [song for song in songs if isinstance(song, dict)]
        repaired |= len(clean_songs) != len(songs)
        clean_sets.append({**item, "song": clean_songs})

    return {
        **record,
        "artist": {
            **artist,
            "name": text(artist.get("name"), "Unknown"),
            "mbid": text(artist.get("mbid")) or None,
        },
        "venue": {
            **venue,
            "id": text(venue.get("id")) or None,
            "name": text(venue.get("name"), "Unknown"),
            "city": {
                **city,
                "name": text(city.get("name")),
                "state": text(city.get("state")),
                "country": {**country, "name": text(country.get("name"))},
            },
        },
        "set": clean_sets,
        "url": text(record.get("url")),
    }, repaired
