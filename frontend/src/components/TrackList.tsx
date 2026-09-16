import React from 'react';
import { Play, Pause, Heart, MoreVertical, Plus, ListPlus, Music, Disc } from 'lucide-react';
import { Track } from '../types';
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
  onOpenDetails: (track: Track) => void;
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
  onOpenDetails,
}) => {
  const [activeMenuId, setActiveMenuId] = React.useState<number | null>(null);

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
    <div className="space-y-1.5">
      {tracks.map((track, index) => {
        const isCurrent = currentTrack?.id === track.id;
        const isTrackPlaying = isCurrent && isPlaying;
        const isFav = favorites.includes(track.id) || track.is_favorite;
        const isMenuOpen = activeMenuId === track.id;

        return (
          <div
            key={track.id}
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
              {/* Artwork / Animated Waveform */}
              <div className="relative w-12 h-12 rounded-xl overflow-hidden bg-slate-900 border border-white/10 shrink-0">
                <img
                  src={track.artwork_url}
                  alt={track.title}
                  loading="lazy"
                  onError={(e) => {
                    (e.target as HTMLImageElement).src =
                      'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" fill="%23222"><rect width="48" height="48"/><text x="24" y="28" fill="%23fff" font-size="18" text-anchor="middle">🎵</text></svg>';
                  }}
                  className="w-full h-full object-cover"
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
                  <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-white/5 border border-white/5">
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
                    className="absolute right-0 top-full mt-1 w-44 rounded-2xl glass-panel shadow-2xl z-50 p-1.5 border border-white/15 animate-fadeIn"
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
                    <button
                      onClick={() => {
                        onOpenDetails(track);
                        setActiveMenuId(null);
                      }}
                      className="w-full flex items-center gap-2.5 px-3 py-2 text-xs font-medium text-slate-200 hover:bg-white/10 rounded-xl transition-colors"
                    >
                      <Disc className="w-4 h-4 text-cyan-400" />
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
  );
};
