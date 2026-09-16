import React, { useState, useMemo } from 'react';
import {
  Play,
  Heart,
  MoreVertical,
  Plus,
  ListPlus,
  Music,
  Disc,
  Mic2,
  FolderPlus,
  ArrowDownAZ,
  ArrowUpDown,
  Sparkles,
  SlidersHorizontal,
} from 'lucide-react';
import { Track, SortOption } from '../types';
import { triggerHaptic } from '../hooks/useAudioPlayer';

interface TrackListProps {
  tracks: Track[];
  currentTrack: Track | null;
  isPlaying: boolean;
  favorites: number[];
  onToggleFavorite: (id: number) => void;
  onPlay: (track: Track) => void;
  onPlayNext: (track: Track) => void;
  onAddToQueue: (track: Track) => void;
  onAddToPlaylist?: (track: Track) => void;
  onSelectAlbum?: (albumName: string) => void;
  onSelectArtist?: (artistName: string) => void;
  onOpenDetails: (track: Track) => void;
  onPrefetch?: (trackId: number) => void;
}

export const TrackList: React.FC<TrackListProps> = ({
  tracks,
  currentTrack,
  isPlaying,
  favorites,
  onToggleFavorite,
  onPlay,
  onPlayNext,
  onAddToQueue,
  onAddToPlaylist,
  onSelectAlbum,
  onSelectArtist,
  onOpenDetails,
  onPrefetch,
}) => {
  const [activeMenuId, setActiveMenuId] = useState<number | null>(null);
  const [sortOption, setSortOption] = useState<SortOption>('default');
  const [formatFilter, setFormatFilter] = useState<'all' | 'FLAC' | 'MP3' | 'M4A'>('all');
  const [showFilterBar, setShowFilterBar] = useState(false);
  const [loadedImages, setLoadedImages] = useState<Record<number, boolean>>({});

  // Sort and filter tracks
  const processedTracks = useMemo(() => {
    let list = [...tracks];

    // Format Filter
    if (formatFilter !== 'all') {
      list = list.filter((t) =>
        t.audio_format.toUpperCase().includes(formatFilter) ||
        t.mime_type.toUpperCase().includes(formatFilter)
      );
    }

    // Sorting
    switch (sortOption) {
      case 'title_asc':
        list.sort((a, b) => a.title.localeCompare(b.title));
        break;
      case 'title_desc':
        list.sort((a, b) => b.title.localeCompare(a.title));
        break;
      case 'artist_asc':
        list.sort((a, b) => a.artist.localeCompare(b.artist));
        break;
      case 'duration_desc':
        list.sort((a, b) => (b.duration || 0) - (a.duration || 0));
        break;
      case 'recent':
        list.sort((a, b) => b.id - a.id);
        break;
      default:
        break;
    }

    return list;
  }, [tracks, sortOption, formatFilter]);

  if (tracks.length === 0) {
    return (
      <div className="py-16 text-center">
        <div className="w-16 h-16 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center mx-auto mb-3 text-slate-500">
          <Music className="w-8 h-8" />
        </div>
        <h3 className="text-base font-bold text-slate-300">No tracks found</h3>
        <p className="text-xs text-slate-500 mt-1 max-w-xs mx-auto">
          Try adjusting your search terms or category filters.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {/* Sort & Filter Controls Header */}
      <div className="flex items-center justify-between px-1 py-1">
        <div className="flex items-center gap-1.5 overflow-x-auto no-scrollbar">
          {/* Filter Bar Toggle */}
          <button
            onClick={() => {
              triggerHaptic('light');
              setShowFilterBar(!showFilterBar);
            }}
            className={`px-2.5 py-1 rounded-xl text-xs font-semibold flex items-center gap-1 transition-all ${
              showFilterBar || formatFilter !== 'all' || sortOption !== 'default'
                ? 'bg-pink-500/20 text-pink-300 border border-pink-500/30'
                : 'bg-white/5 text-slate-400 hover:text-slate-200 border border-white/5'
            }`}
          >
            <SlidersHorizontal className="w-3 h-3" />
            <span>Sort & Filter</span>
            {(formatFilter !== 'all' || sortOption !== 'default') && (
              <span className="w-1.5 h-1.5 rounded-full bg-pink-400 ml-0.5" />
            )}
          </button>
        </div>

        <span className="text-xs font-medium text-slate-500 font-mono">
          {processedTracks.length} / {tracks.length}
        </span>
      </div>

      {/* Expandable Sort & Filter Options Drawer */}
      {showFilterBar && (
        <div className="p-3 rounded-2xl bg-white/[0.04] border border-white/10 space-y-3 animate-fadeIn">
          {/* Sort By Pills */}
          <div>
            <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400 mb-1.5 flex items-center gap-1">
              <ArrowUpDown className="w-3 h-3 text-pink-400" />
              <span>Sort By</span>
            </p>
            <div className="flex flex-wrap gap-1.5">
              {[
                { id: 'default' as SortOption, label: 'Default' },
                { id: 'title_asc' as SortOption, label: 'Title (A-Z)' },
                { id: 'artist_asc' as SortOption, label: 'Artist (A-Z)' },
                { id: 'duration_desc' as SortOption, label: 'Duration (Longest)' },
                { id: 'recent' as SortOption, label: 'Recently Added' },
              ].map((opt) => (
                <button
                  key={opt.id}
                  onClick={() => {
                    triggerHaptic('light');
                    setSortOption(opt.id);
                  }}
                  className={`px-3 py-1 rounded-xl text-xs font-semibold transition-all ${
                    sortOption === opt.id
                      ? 'bg-gradient-to-r from-pink-500 to-purple-600 text-white shadow-md'
                      : 'bg-white/5 hover:bg-white/10 text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          {/* Format Filter */}
          <div>
            <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400 mb-1.5 flex items-center gap-1">
              <Sparkles className="w-3 h-3 text-cyan-400" />
              <span>Audio Quality / Format</span>
            </p>
            <div className="flex flex-wrap gap-1.5">
              {(['all', 'FLAC', 'MP3', 'M4A'] as const).map((fmt) => (
                <button
                  key={fmt}
                  onClick={() => {
                    triggerHaptic('light');
                    setFormatFilter(fmt);
                  }}
                  className={`px-3 py-1 rounded-xl text-xs font-semibold transition-all ${
                    formatFilter === fmt
                      ? 'bg-cyan-500 text-slate-950 font-bold shadow-md shadow-cyan-500/20'
                      : 'bg-white/5 hover:bg-white/10 text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {fmt === 'all' ? 'All Formats' : fmt === 'FLAC' ? 'FLAC (Lossless)' : fmt}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Tracks List */}
      <div className="space-y-1.5">
        {processedTracks.map((track, index) => {
          const isCurrent = currentTrack?.id === track.id;
          const isTrackPlaying = isCurrent && isPlaying;
          const isFav = favorites.includes(track.id) || track.is_favorite;
          const isMenuOpen = activeMenuId === track.id;
          const isImageLoaded = loadedImages[track.id];

          return (
            <div
              key={track.id}
              onMouseEnter={() => onPrefetch && onPrefetch(track.id)}
              onTouchStart={() => onPrefetch && onPrefetch(track.id)}
              className={`group relative flex items-center justify-between p-2.5 sm:p-3 rounded-2xl transition-all duration-200 ${
                isCurrent
                  ? 'bg-gradient-to-r from-pink-500/15 via-purple-600/10 to-transparent border border-pink-500/30'
                  : 'bg-white/[0.03] hover:bg-white/[0.07] border border-transparent hover:border-white/5'
              }`}
            >
              {/* Left: Index / Cover / Title */}
              <div
                className="flex items-center gap-3 min-w-0 flex-1 cursor-pointer"
                onClick={() => {
                  triggerHaptic('light');
                  onPlay(track);
                }}
              >
                {/* Artwork with blur-up lazy loading */}
                <div className="relative w-12 h-12 rounded-xl overflow-hidden bg-slate-900 border border-white/10 shrink-0">
                  <img
                    src={track.artwork_url}
                    alt={track.title}
                    loading="lazy"
                    onLoad={() => setLoadedImages((prev) => ({ ...prev, [track.id]: true }))}
                    onError={(e) => {
                      (e.target as HTMLImageElement).src =
                        'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" fill="%23222"><rect width="48" height="48"/><text x="24" y="28" fill="%23fff" font-size="18" text-anchor="middle">🎵</text></svg>';
                    }}
                    className={`w-full h-full object-cover transition-opacity duration-300 ${
                      isImageLoaded ? 'opacity-100' : 'opacity-40 blur-sm'
                    }`}
                  />

                  {/* Playing Overlay Indicator */}
                  {isCurrent && (
                    <div className="absolute inset-0 bg-black/60 flex items-center justify-center gap-0.5">
                      {isTrackPlaying ? (
                        <>
                          <div className="w-1 bg-pink-400 rounded-full eq-bar-1" />
                          <div className="w-1 bg-pink-400 rounded-full eq-bar-2" />
                          <div className="w-1 bg-pink-400 rounded-full eq-bar-3" />
                        </>
                      ) : (
                        <Play className="w-4 h-4 text-white fill-current" />
                      )}
                    </div>
                  )}
                </div>

                {/* Title & Artist */}
                <div className="min-w-0 flex-1">
                  <p
                    className={`text-sm font-semibold truncate ${
                      isCurrent ? 'text-pink-300' : 'text-slate-100 group-hover:text-white'
                    }`}
                  >
                    {track.title}
                  </p>
                  <div className="flex items-center gap-2 mt-0.5 text-xs text-slate-400 truncate">
                    <span className="truncate">{track.artist}</span>
                    <span>•</span>
                    <span
                      className={`text-[10px] font-mono px-1.5 py-0.2 rounded border ${
                        track.audio_format === 'FLAC'
                          ? 'bg-cyan-500/15 text-cyan-300 border-cyan-500/30'
                          : 'bg-white/5 text-slate-400 border-white/5'
                      }`}
                    >
                      {track.audio_format}
                    </span>
                  </div>
                </div>
              </div>

              {/* Right: Duration, Favorite, More Menu */}
              <div className="flex items-center gap-1 sm:gap-2 shrink-0 ml-2">
                <span className="text-xs font-mono text-slate-400 hidden sm:inline">
                  {track.duration_str}
                </span>

                {/* Favorite Heart */}
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    triggerHaptic('light');
                    onToggleFavorite(track.id);
                  }}
                  className={`p-2 rounded-xl transition-all ${
                    isFav
                      ? 'text-pink-500 hover:text-pink-400'
                      : 'text-slate-500 hover:text-slate-300'
                  }`}
                  aria-label="Toggle favorite"
                >
                  <Heart className={`w-4 h-4 ${isFav ? 'fill-current' : ''}`} />
                </button>

                {/* More Actions Toggle */}
                <div className="relative">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      triggerHaptic('light');
                      setActiveMenuId(isMenuOpen ? null : track.id);
                    }}
                    className="p-2 rounded-xl text-slate-500 hover:text-slate-300 hover:bg-white/5 transition-all"
                    aria-label="Track options"
                  >
                    <MoreVertical className="w-4 h-4" />
                  </button>

                  {/* Dropdown Menu */}
                  {isMenuOpen && (
                    <div
                      className="absolute right-0 top-full mt-1 w-48 rounded-2xl glass-panel shadow-2xl z-50 p-1.5 border border-white/15 animate-fadeIn"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <button
                        onClick={() => {
                          onPlayNext(track);
                          setActiveMenuId(null);
                        }}
                        className="w-full flex items-center gap-2.5 px-3 py-2 text-xs font-medium text-slate-200 hover:bg-white/10 rounded-xl transition-colors"
                      >
                        <ListPlus className="w-4 h-4 text-pink-400" />
                        <span>Play Next</span>
                      </button>

                      <button
                        onClick={() => {
                          onAddToQueue(track);
                          setActiveMenuId(null);
                        }}
                        className="w-full flex items-center gap-2.5 px-3 py-2 text-xs font-medium text-slate-200 hover:bg-white/10 rounded-xl transition-colors"
                      >
                        <Plus className="w-4 h-4 text-purple-400" />
                        <span>Add to Queue</span>
                      </button>

                      {onAddToPlaylist && (
                        <button
                          onClick={() => {
                            onAddToPlaylist(track);
                            setActiveMenuId(null);
                          }}
                          className="w-full flex items-center gap-2.5 px-3 py-2 text-xs font-medium text-slate-200 hover:bg-white/10 rounded-xl transition-colors"
                        >
                          <FolderPlus className="w-4 h-4 text-amber-400" />
                          <span>Add to Playlist</span>
                        </button>
                      )}

                      {onSelectAlbum && track.album && (
                        <button
                          onClick={() => {
                            onSelectAlbum(track.album);
                            setActiveMenuId(null);
                          }}
                          className="w-full flex items-center gap-2.5 px-3 py-2 text-xs font-medium text-slate-200 hover:bg-white/10 rounded-xl transition-colors"
                        >
                          <Disc className="w-4 h-4 text-cyan-400" />
                          <span>View Album</span>
                        </button>
                      )}

                      {onSelectArtist && track.artist && (
                        <button
                          onClick={() => {
                            onSelectArtist(track.artist);
                            setActiveMenuId(null);
                          }}
                          className="w-full flex items-center gap-2.5 px-3 py-2 text-xs font-medium text-slate-200 hover:bg-white/10 rounded-xl transition-colors"
                        >
                          <Mic2 className="w-4 h-4 text-emerald-400" />
                          <span>View Artist</span>
                        </button>
                      )}

                      <button
                        onClick={() => {
                          onOpenDetails(track);
                          setActiveMenuId(null);
                        }}
                        className="w-full flex items-center gap-2.5 px-3 py-2 text-xs font-medium text-slate-200 hover:bg-white/10 rounded-xl transition-colors"
                      >
                        <Disc className="w-4 h-4 text-slate-400" />
                        <span>Track Info</span>
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
