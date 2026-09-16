"""
Search engine for TPMC.
Supports exact tag queries, structured field filters, keyword search, and pagination.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import List, Tuple
from app.index.models import Track
from app.index.parser import normalize_tag, normalize_string

try:
    from rapidfuzz import fuzz
except ImportError:
    fuzz = None


@dataclass
class SearchResult:
    query: str
    tracks: List[Track]
    total_count: int
    page: int
    page_size: int
    total_pages: int

    @property
    def has_next_page(self) -> bool:
        return self.page < self.total_pages

    @property
    def has_prev_page(self) -> bool:
        return self.page > 1


class SearchEngine:
    @classmethod
    def search(
        cls,
        query: str,
        tracks: List[Track],
        page: int = 1,
        page_size: int = 25,
    ) -> SearchResult:
        """
        Execute search on a list of tracks with pagination.
        """
        cleaned_query = query.strip()
        if not cleaned_query:
            matched_tracks = tracks
        else:
            matched_tracks = cls._filter_tracks(cleaned_query, tracks)

        total_count = len(matched_tracks)
        total_pages = max(1, math.ceil(total_count / page_size)) if total_count > 0 else 1
        current_page = max(1, min(page, total_pages))

        start_idx = (current_page - 1) * page_size
        end_idx = start_idx + page_size
        page_tracks = matched_tracks[start_idx:end_idx]

        return SearchResult(
            query=cleaned_query,
            tracks=page_tracks,
            total_count=total_count,
            page=current_page,
            page_size=page_size,
            total_pages=total_pages,
        )

    @classmethod
    def _filter_tracks(cls, query: str, tracks: List[Track]) -> List[Track]:
        # 1. Exact Tag Search: query starts with '#'
        if query.startswith("#"):
            target_tag = normalize_tag(query)
            return [t for t in tracks if target_tag in t.tags]

        # 2. Structured Field Search: artist:val, album:val, genre:val, year:val
        if ":" in query:
            parts = query.split(":", 1)
            field_name = normalize_string(parts[0])
            raw_target = parts[1].strip()
            # Normalize variations: spaces and underscores
            target_norm = normalize_string(raw_target)
            target_space = target_norm.replace("_", " ")
            target_under = target_norm.replace(" ", "_")

            results = []
            for t in tracks:
                matched = False
                if field_name in {"artist", "performer"}:
                    perf_norm = normalize_string(t.performer)
                    if (
                        target_space in perf_norm.replace("_", " ")
                        or target_under in perf_norm.replace(" ", "_")
                        or target_under == t.structured_tags.get("artist")
                    ):
                        matched = True
                elif field_name == "album":
                    alb_norm = normalize_string(t.album)
                    if (
                        target_space in alb_norm.replace("_", " ")
                        or target_under in alb_norm.replace(" ", "_")
                        or target_under == t.structured_tags.get("album")
                    ):
                        matched = True
                elif field_name == "genre":
                    gen_norm = normalize_string(t.genre)
                    if (
                        target_space in gen_norm.replace("_", " ")
                        or target_under in gen_norm.replace(" ", "_")
                        or target_under == t.structured_tags.get("genre")
                    ):
                        matched = True
                elif field_name in t.structured_tags:
                    tag_val = normalize_string(t.structured_tags[field_name])
                    if target_space in tag_val.replace("_", " ") or target_under in tag_val.replace(" ", "_"):
                        matched = True

                if not matched and f"{field_name}:{target_under}" in t.tags:
                    matched = True

                if matched:
                    results.append(t)
            return results

        # 3. Favorite Shortcut
        if query.lower() in {"favorite", "favorites", "fav"}:
            return [t for t in tracks if t.is_favorite]

        # 4. Keyword & Fuzzy Search
        keywords = [normalize_string(k) for k in query.split() if k.strip()]
        if not keywords:
            return tracks

        query_norm = normalize_string(query)
        scored_tracks: List[Tuple[float, Track]] = []

        for t in tracks:
            norm_title = normalize_string(t.title)
            norm_perf = normalize_string(t.performer)
            norm_album = normalize_string(t.album)
            norm_fn = normalize_string(t.filename)
            norm_tags = t.tags

            score = 0.0
            matched_all_keywords = True

            for kw in keywords:
                kw_matched = False
                # 1. Exact equality
                if kw == norm_perf or kw == norm_title:
                    score += 25.0
                    kw_matched = True
                # 2. Substring matching
                elif kw in norm_title:
                    score += 15.0
                    kw_matched = True
                elif kw in norm_perf:
                    score += 12.0
                    kw_matched = True
                elif kw in norm_album:
                    score += 8.0
                    kw_matched = True
                elif kw in norm_tags:
                    score += 10.0
                    kw_matched = True
                elif kw in norm_fn:
                    score += 5.0
                    kw_matched = True
                # 3. Fuzzy typo-tolerant matching (per-word for words >= 4 chars)
                elif fuzz and len(kw) >= 4:
                    words_to_check = norm_title.split() + norm_perf.split() + norm_album.split()
                    best_ratio = max((fuzz.ratio(kw, w) for w in words_to_check), default=0.0)
                    if best_ratio >= 82:
                        score += best_ratio / 10.0
                        kw_matched = True

                if not kw_matched:
                    matched_all_keywords = False
                    break

            # Extra whole-phrase fuzzy bonus if available
            if fuzz:
                combined_name = f"{norm_perf} {norm_title}"
                phrase_ratio = fuzz.token_sort_ratio(query_norm, combined_name)
                if phrase_ratio >= 85:
                    score += phrase_ratio / 5.0
                    matched_all_keywords = True

            if matched_all_keywords and score > 0:
                scored_tracks.append((score, t))

        # Sort highest score first
        scored_tracks.sort(key=lambda item: item[0], reverse=True)
        return [item[1] for item in scored_tracks]
