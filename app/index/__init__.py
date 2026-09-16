"""
Indexing, metadata parsing, and search engine package
"""

from app.index.models import Track
from app.index.parser import MetadataParser, normalize_tag
from app.index.indexer import MusicIndexer
from app.index.search import SearchEngine

__all__ = [
    "Track",
    "MetadataParser",
    "normalize_tag",
    "MusicIndexer",
    "SearchEngine",
]
