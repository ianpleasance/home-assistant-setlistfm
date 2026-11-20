"""Venue-day projections of a full attendance snapshot, not ticket identities."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from .api import AttendanceData
from .helpers import dated_concerts, select_dated, simplify_concert

MAX_PERFORMANCES_PER_VISIT = 100
MAX_DISPLAY_PERFORMANCES = 500


@dataclass
class ConcertVisit:
    """Keep source performances together until after the display limit is applied."""

    event_date: date
    venue_id: str | None
    performances: list[dict[str, Any]]


class ConcertVisits:
    """One cached grouping of the entire validated snapshot."""

    def __init__(self, data: AttendanceData) -> None:
        groups: dict[tuple[date, str], ConcertVisit] = {}
        self.visits: list[ConcertVisit] = []
        self.unidentified_performance_count = 0
        dated = dated_concerts(data["concerts"])
        self.invalid_date_count = len(data["concerts"]) - len(dated)
        for event_date, record in dated:
            venue_id = record.get("venue", {}).get("id")
            if not isinstance(venue_id, str) or not venue_id.strip() or venue_id != venue_id.strip():
                self.unidentified_performance_count += 1
                self.visits.append(ConcertVisit(event_date, None, [record]))
                continue
            key = (event_date, venue_id)
            if key not in groups:
                groups[key] = ConcertVisit(event_date, venue_id, [])
                self.visits.append(groups[key])
            groups[key].performances.append(record)
        for visit in self.visits:
            visit.performances.sort(key=lambda record: (
                record.get("artist", {}).get("name", "").casefold(), record["id"],
            ))
        self.visits.sort(key=lambda visit: (
            visit.event_date, visit.venue_id or "", visit.performances[0]["id"],
        ))
        self.metadata = {
            "grouping_rule": "venue_day",
            "grouping_complete": (
                data["complete"]
                and not self.unidentified_performance_count
                and not self.invalid_date_count
            ),
            "identified_visit_count": len(groups),
            "unidentified_performance_count": self.unidentified_performance_count,
            "invalid_date_count": self.invalid_date_count,
        }
        self.count = len(groups) if self.metadata["grouping_complete"] else None

    def display(self, today: date, show: str, limit: int) -> list[dict[str, Any]]:
        """Bound visits, retaining their lineups with explicit resource overflow."""
        selected = select_dated(
            [(visit.event_date, visit) for visit in self.visits],
            today, show, min(50, max(1, limit)), visits=True,
        )
        result = []
        budget = MAX_DISPLAY_PERFORMANCES
        for index, visit in enumerate(selected):
            # Reserve one performance for each remaining visit, even without ID.
            allowance = min(MAX_PERFORMANCES_PER_VISIT, budget - (len(selected) - index - 1))
            performances = []
            for record in visit.performances[:allowance]:
                simple = simplify_concert(record)
                performances.append({
                    key: simple[key] for key in ("id", "artist", "song_count", "url")
                })
            representative = simplify_concert(visit.performances[0])
            result.append({
                "date": representative["date"],
                "venue": {**representative["venue"], "id": visit.venue_id},
                "performances": performances,
                "grouping_complete": visit.venue_id is not None,
                "performance_count": len(visit.performances),
                "omitted_performance_count": len(visit.performances) - len(performances),
            })
            budget -= len(performances)
        return result
