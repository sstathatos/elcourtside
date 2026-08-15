"""Data sources."""

from ingest.sources.euroleague import EuroleagueSource

SOURCES = {
    EuroleagueSource.name: EuroleagueSource,
}


def create_source(name: str, client):
    return SOURCES[name](client)
