"""Data sources. Each source is a module behind the common interface in
base.py; the pipeline is generic over sources (multi-source future)."""

from ingest.sources.euroleague import EuroleagueSource

SOURCES = {
    EuroleagueSource.name: EuroleagueSource,
}


def create_source(name: str, client):
    return SOURCES[name](client)
