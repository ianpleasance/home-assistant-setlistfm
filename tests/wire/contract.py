"""Independent assertions for the documented subset (see devtools README).

No imports from the mock generator, client, or concert normalizer. The historical
wrapper is enabled explicitly; it is not mislabeled as the published schema.
"""

from datetime import datetime


def assert_attendance_contract(payload, *, historical=False):
    """Check the derived JSON subset, not client-normalized attendance data."""
    assert isinstance(payload, dict)
    assert set(payload) == {"setlist", "total", "page", "itemsPerPage"}
    for field, minimum in (("total", 0), ("page", 1), ("itemsPerPage", 1)):
        assert type(payload[field]) is int
        assert payload[field] >= minimum
    assert isinstance(payload["setlist"], list)
    assert len(payload["setlist"]) <= payload["itemsPerPage"]
    for record in payload["setlist"]:
        assert isinstance(record, dict)
        assert isinstance(record["id"], str) and record["id"]
        assert isinstance(record["eventDate"], str)
        assert datetime.strptime(record["eventDate"], "%d-%m-%Y").strftime(
            "%d-%m-%Y"
        ) == record["eventDate"]
        for field in ("url", "versionId", "lastUpdated", "info"):
            if field in record:
                assert isinstance(record[field], str)
        if "artist" in record:
            assert isinstance(record["artist"], dict)
            for field in ("name", "mbid"):
                if field in record["artist"]:
                    assert isinstance(record["artist"][field], str)
        if "venue" in record:
            venue = record["venue"]
            assert isinstance(venue, dict)
            if "name" in venue:
                assert isinstance(venue["name"], str)
            if "city" in venue:
                city = venue["city"]
                assert isinstance(city, dict)
                for field in ("name", "state"):
                    if field in city:
                        assert isinstance(city[field], str)
                if "country" in city:
                    assert isinstance(city["country"], dict)
                    for field in ("name", "code"):
                        if field in city["country"]:
                            assert isinstance(city["country"][field], str)
        assert not ("set" in record and "sets" in record)
        if "sets" in record:
            assert historical, "sets.set is historical compatibility, not the published shape"
            assert isinstance(record["sets"], dict)
            assert set(record["sets"]) == {"set"}
            sets = record["sets"]["set"]
        else:
            sets = record.get("set", [])
        assert isinstance(sets, list)
        for concert_set in sets:
            assert isinstance(concert_set, dict)
            if "encore" in concert_set:
                assert type(concert_set["encore"]) is int
                assert concert_set["encore"] >= 1
            assert isinstance(concert_set["song"], list)
            for song in concert_set["song"]:
                assert isinstance(song, dict)
                assert isinstance(song["name"], str)
                if "tape" in song:
                    assert type(song["tape"]) is bool
