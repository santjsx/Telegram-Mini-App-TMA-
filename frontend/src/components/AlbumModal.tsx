import React from 'react';
import { X, Play, Shuffle, Heart, Disc, Music, Sparkles } from 'lucide-react';
import { Track } from '../types';
import { triggerHaptic } from '../hooks/useAudioPlayer';
import { formatTime } from '../utils';

interface AlbumModalProps {
  isOpen: boolean;
  onClose: () => void;
  albumName: string | null;
  allTracks: Track[];
  currentTrack: Track | null;
  isPlaying: boolean;
  onPlayTrack: (track: Track, queue: Track[]) => void;
  onSelectArtist: (artistName: string) => void;
  favorites: number[];
  onToggleFavorite: (id: number) => void;
}

export const AlbumModal: React.FC<AlbumModalProps> = ({
  isOpen,
  onClose,
  albumName,
  allTracks,
  currentTrack,
  isPlaying,
  onPlayTrack,
  onSelectArtist,
  favorites,
  onToggleFavorite,
}) => {
  if (!isOpen || !albumName) return null;

  const albumTracks = allTracks.filter(
    (t) => (t.album || 'Single').toLowerCase() === albumName.toLowerCase()
  );

  if (albumTracks.length === 0) return null;

  const leadTrack = albumTracks[0];
  const artistName = leadTrack.artist;
  const totalDuration = albumTracks.reduce((acc, t) => acc + (t.duration || 0), 0);
  const isLossless = albumTracks.some(
    (t) => t.audio_format === 'FLAC' || t.mime_type.includes('flac')
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6 bg-black/85 backdrop-blur-2xl transition-all duration-300">
      {/* Dynamic ambient backdrop blur */}
      <div
        className="absolute inset-0 opacity-20 pointer-events-none blur-3xl"
        style={{
          background: `radial-gradient(circle at center 30%, ${leadTrack.palette.primary}, ${leadTrack.palette.secondary} 50%, transparent 80%)`,
        }}
      />

      <div className="relative z-10 w-full max-w-2xl max-h-[92vh] flex flex-col rounded-3xl glass-panel border border-white/10 shadow-2xl overflow-hidden animate-fadeIn">
        {/* Header Bar */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/10">
          <div className="flex items-center gap-2 text-xs font-semibold text-slate-400">
            <Disc className="w-4 h-4 text-pink-400" />
            <span>Album Details</span>
          </div>

          <button
            onClick={() => {
              triggerHaptic('light');
              onClose();
            }}
            className="p-2 rounded-xl text-slate-400 hover:text-white hover:bg-white/10 transition-colors"
            aria-label="Close"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Scrollable Content */}
        <div className="flex-1 overflow-y-auto p-6 no-scrollbar space-y-6">
          {/* Album Hero Showcase */}
          <div className="flex flex-col sm:flex-row items-center gap-6 text-center sm:text-left">
            {/* Artwork with ambient glowing shadow */}
            <div className="relative w-44 h-44 sm:w-48 sm:h-48 rounded-2xl overflow-hidden shadow-2xl shrink-0 group">
              <div
                className="absolute -inset-1 rounded-2xl blur-lg opacity-60 group-hover:opacity-100 transition-opacity"
                style={{
                  background: `linear-gradient(135deg, ${leadTrack.palette.primary}, ${leadTrack.palette.secondary})`,
                }}
              />
              <img
                src={leadTrack.artwork_url}
                alt={albumName}
                onError={(e) => {
                  (e.target as HTMLImageElement).src =
                    'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200" fill="%23222"><rect width="200" height="200"/><text x="100" y="110" fill="%23fff" font-size="60" text-anchor="middle">🎵</text></svg>';
                }}
                className="relative z-10 w-full h-full object-cover rounded-2xl border border-white/15"
              />
            </div>

            {/* Album Metadata */}
            <div className="min-w-0 flex-1 space-y-2">
              <div className="flex items-center justify-center sm:justify-start gap-2">
                <span className="text-[10px] font-bold tracking-widest uppercase px-2 py-0.5 rounded-full bg-pink-500/20 text-pink-400 border border-pink-500/30">
                  Album
                </span>
                {isLossless && (
                  <span className="text-[10px] font-mono font-bold tracking-wider px-2 py-0.5 rounded-full bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 flex items-center gap-1">
                    <Sparkles className="w-2.5 h-2.5" />
                    Hi-Res Lossless
                  </span>
                )}
              </div>

              <h1 className="text-2xl sm:text-3xl font-black text-white tracking-tight leading-tight">
                {albumName}
              </h1>

              <button
                onClick={() => {
                  triggerHaptic('light');
                  onSelectArtist(artistName);
                  onClose();
                }}
                className="text-sm font-semibold text-pink-400 hover:text-pink-300 transition-colors"
              >
                {artistName} →
              </button>

              <div className="flex items-center justify-center sm:justify-start gap-3 text-xs text-slate-400">
                <span>{albumTracks.length} tracks</span>
                <span>•</span>
                <span>{formatTime(totalDuration)}</span>
                <span>•</span>
                <span>{leadTrack.genre || 'Music'}</span>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center justify-center sm:justify-start gap-3 pt-2">
                <button
                  onClick={() => {
                    triggerHaptic('medium');
                    onPlayTrack(albumTracks[0], albumTracks);
                  }}
                  className="px-5 py-2.5 rounded-xl text-xs font-bold bg-gradient-to-r from-pink-500 to-purple-600 text-white flex items-center gap-2 shadow-lg shadow-pink-500/25 active:scale-95 transition-all"
                >
                  <Play className="w-4 h-4 fill-current" />
                  <span>Play Album</span>
                </button>

                <button
                  onClick={() => {
                    triggerHaptic('medium');
                    const shuffled = [...albumTracks].sort(() => Math.random() - 0.5);
                    onPlayTrack(shuffled[0], shuffled);
                  }}
                  className="px-4 py-2.5 rounded-xl text-xs font-bold bg-white/10 text-white hover:bg-white/15 flex items-center gap-2 border border-white/10 active:scale-95 transition-all"
                >
                  <Shuffle className="w-4 h-4" />
                  <span>Shuffle</span>
                </button>
              </div>
            </div>
          </div>

          {/* Tracklist Section */}
          <div className="space-y-2 pt-2">
            <h3 className="text-xs font-bold tracking-widest text-slate-400 uppercase">
              Tracks
            </h3>

            <div className="space-y-1">
              {albumTracks.map((track, i) => {
                const isCurrent = currentTrack?.id === track.id;
                const isTrackPlaying = isCurrent && isPlaying;
                const isFav = favorites.includes(track.id) || track.is_favorite;

                return (
                  <div
                    key={track.id}
                    className={`group flex items-center justify-between p-3 rounded-2xl transition-all cursor-pointer ${
                      isCurrent
                        ? 'bg-pink-500/15 border border-pink-500/30'
                        : 'bg-white/[0.02] hover:bg-white/[0.06] border border-transparent hover:border-white/5'
                    }`}
                    onClick={() => {
                      triggerHaptic('light');
                      onPlayTrack(track, albumTracks);
                    }}
                  >
                    {/* Index & Title */}
                    <div className="flex items-center gap-3 min-w-0 flex-1">
                      <span className="w-6 text-center text-xs font-mono text-slate-500">
                        {isTrackPlaying ? (
                          <div className="flex items-center justify-center gap-0.5">
                            <div className="w-1 h-3 bg-pink-400 rounded-full eq-bar-1" />
                            <div className="w-1 h-3 bg-pink-400 rounded-full eq-bar-2" />
                            <div className="w-1 h-3 bg-pink-400 rounded-full eq-bar-3" />
                          </div>
                        ) : (
                          i + 1
                        )}
                      </span>

                      <div className="min-w-0 flex-1">
                        <p
                          className={`text-sm font-semibold truncate ${
                            isCurrent ? 'text-pink-300' : 'text-slate-100 group-hover:text-white'
                          }`}
                        >
                          {track.title}
                        </p>
                        <p className="text-xs text-slate-400 truncate">{track.artist}</p>
                      </div>
                    </div>

                    {/* Right Info: Format, Duration, Favorite */}
                    <div className="flex items-center gap-3 shrink-0">
                      <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-white/5 text-slate-400">
                        {track.audio_format}
                      </span>
                      <span className="text-xs font-mono text-slate-400">{track.duration_str}</span>

                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          triggerHaptic('light');
                          onToggleFavorite(track.id);
                        }}
                        className={`p-1.5 rounded-lg transition-colors ${
                          isFav ? 'text-pink-500' : 'text-slate-500 hover:text-slate-300'
                        }`}
                        aria-label="Toggle favorite"
                      >
                        <Heart className={`w-4 h-4 ${isFav ? 'fill-current' : ''}`} />
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
