import React from 'react';
import { X, Play, Shuffle, Heart, Mic2, Disc, Radio } from 'lucide-react';
import { Track } from '../types';
import { triggerHaptic } from '../hooks/useAudioPlayer';
import { formatTime } from '../utils';

interface ArtistModalProps {
  isOpen: boolean;
  onClose: () => void;
  artistName: string | null;
  allTracks: Track[];
  currentTrack: Track | null;
  isPlaying: boolean;
  onPlayTrack: (track: Track, queue: Track[]) => void;
  onSelectAlbum: (albumName: string) => void;
  favorites: number[];
  onToggleFavorite: (id: number) => void;
}

export const ArtistModal: React.FC<ArtistModalProps> = ({
  isOpen,
  onClose,
  artistName,
  allTracks,
  currentTrack,
  isPlaying,
  onPlayTrack,
  onSelectAlbum,
  favorites,
  onToggleFavorite,
}) => {
  if (!isOpen || !artistName) return null;

  const artistTracks = allTracks.filter(
    (t) => (t.artist || 'Various Artists').toLowerCase() === artistName.toLowerCase()
  );

  if (artistTracks.length === 0) return null;

  const leadTrack = artistTracks[0];
  const totalDuration = artistTracks.reduce((acc, t) => acc + (t.duration || 0), 0);

  // Group albums
  const albumsMap = new Map<string, Track[]>();
  artistTracks.forEach((t) => {
    const alb = t.album || 'Single';
    if (!albumsMap.has(alb)) albumsMap.set(alb, []);
    albumsMap.get(alb)!.push(t);
  });
  const albumsList = Array.from(albumsMap.entries()).map(([name, trks]) => ({
    name,
    count: trks.length,
    artwork_url: trks[0].artwork_url,
    palette: trks[0].palette,
  }));

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
            <Mic2 className="w-4 h-4 text-purple-400" />
            <span>Artist Profile</span>
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
          {/* Artist Hero Header */}
          <div className="flex flex-col sm:flex-row items-center gap-6 text-center sm:text-left">
            <div className="relative w-36 h-36 sm:w-40 sm:h-40 rounded-full overflow-hidden shadow-2xl shrink-0 border-2 border-white/20 group">
              <img
                src={leadTrack.artwork_url}
                alt={artistName}
                onError={(e) => {
                  (e.target as HTMLImageElement).src =
                    'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200" fill="%23222"><rect width="200" height="200"/><text x="100" y="110" fill="%23fff" font-size="60" text-anchor="middle">🎙️</text></svg>';
                }}
                className="w-full h-full object-cover rounded-full"
              />
            </div>

            <div className="min-w-0 flex-1 space-y-2">
              <span className="text-[10px] font-bold tracking-widest uppercase px-2 py-0.5 rounded-full bg-purple-500/20 text-purple-300 border border-purple-500/30">
                Verified Artist
              </span>

              <h1 className="text-2xl sm:text-3xl font-black text-white tracking-tight">
                {artistName}
              </h1>

              <div className="flex items-center justify-center sm:justify-start gap-3 text-xs text-slate-400">
                <span>{artistTracks.length} tracks</span>
                <span>•</span>
                <span>{albumsList.length} {albumsList.length === 1 ? 'album' : 'albums'}</span>
                <span>•</span>
                <span>{formatTime(totalDuration)} total</span>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center justify-center sm:justify-start gap-3 pt-2">
                <button
                  onClick={() => {
                    triggerHaptic('medium');
                    onPlayTrack(artistTracks[0], artistTracks);
                  }}
                  className="px-5 py-2.5 rounded-xl text-xs font-bold bg-gradient-to-r from-pink-500 to-purple-600 text-white flex items-center gap-2 shadow-lg shadow-pink-500/25 active:scale-95 transition-all"
                >
                  <Play className="w-4 h-4 fill-current" />
                  <span>Play Artist</span>
                </button>

                <button
                  onClick={() => {
                    triggerHaptic('medium');
                    const shuffled = [...artistTracks].sort(() => Math.random() - 0.5);
                    onPlayTrack(shuffled[0], shuffled);
                  }}
                  className="px-4 py-2.5 rounded-xl text-xs font-bold bg-white/10 text-white hover:bg-white/15 flex items-center gap-2 border border-white/10 active:scale-95 transition-all"
                >
                  <Shuffle className="w-4 h-4" />
                  <span>Shuffle</span>
                </button>

                <button
                  onClick={() => {
                    triggerHaptic('light');
                    onPlayTrack(artistTracks[0], artistTracks);
                  }}
                  className="px-3.5 py-2.5 rounded-xl text-xs font-bold bg-purple-500/20 text-purple-300 hover:bg-purple-500/30 flex items-center gap-1.5 border border-purple-500/30 active:scale-95 transition-all"
                  title="Artist Radio"
                >
                  <Radio className="w-3.5 h-3.5" />
                  <span>Radio</span>
                </button>
              </div>
            </div>
          </div>

          {/* Albums by this Artist */}
          {albumsList.length > 0 && (
            <div className="space-y-3 pt-2">
              <h3 className="text-xs font-bold tracking-widest text-slate-400 uppercase flex items-center gap-2">
                <Disc className="w-3.5 h-3.5 text-pink-400" />
                <span>Discography ({albumsList.length})</span>
              </h3>

              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                {albumsList.map((alb) => (
                  <div
                    key={alb.name}
                    onClick={() => {
                      triggerHaptic('light');
                      onSelectAlbum(alb.name);
                    }}
                    className="group p-3 rounded-2xl bg-white/[0.03] hover:bg-white/[0.08] border border-white/5 hover:border-white/15 cursor-pointer transition-all flex flex-col gap-2.5"
                  >
                    <div className="relative aspect-square rounded-xl overflow-hidden shadow-lg">
                      <img
                        src={alb.artwork_url}
                        alt={alb.name}
                        className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                        onError={(e) => {
                          (e.target as HTMLImageElement).src =
                            'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" fill="%23222"><rect width="100" height="100"/><text x="50" y="55" fill="%23fff" font-size="30" text-anchor="middle">💿</text></svg>';
                        }}
                      />
                    </div>
                    <div className="min-w-0">
                      <h4 className="text-xs font-bold text-white truncate group-hover:text-pink-300 transition-colors">
                        {alb.name}
                      </h4>
                      <p className="text-[11px] text-slate-400 mt-0.5">
                        {alb.count} {alb.count === 1 ? 'song' : 'songs'}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* All Tracks by Artist */}
          <div className="space-y-2 pt-2">
            <h3 className="text-xs font-bold tracking-widest text-slate-400 uppercase">
              All Tracks ({artistTracks.length})
            </h3>

            <div className="space-y-1">
              {artistTracks.map((track, i) => {
                const isCurrent = currentTrack?.id === track.id;
                const isTrackPlaying = isCurrent && isPlaying;
                const isFav = favorites.includes(track.id) || track.is_favorite;

                return (
                  <div
                    key={track.id}
                    className={`group flex items-center justify-between p-3 rounded-2xl transition-all cursor-pointer ${
                      isCurrent
                        ? 'bg-purple-500/15 border border-purple-500/30'
                        : 'bg-white/[0.02] hover:bg-white/[0.06] border border-transparent hover:border-white/5'
                    }`}
                    onClick={() => {
                      triggerHaptic('light');
                      onPlayTrack(track, artistTracks);
                    }}
                  >
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

                      <div className="w-10 h-10 rounded-xl overflow-hidden bg-slate-900 border border-white/10 shrink-0">
                        <img
                          src={track.artwork_url}
                          alt={track.title}
                          className="w-full h-full object-cover"
                          onError={(e) => {
                            (e.target as HTMLImageElement).src =
                              'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" fill="%23222"><rect width="40" height="40"/><text x="20" y="24" fill="%23fff" font-size="16" text-anchor="middle">🎵</text></svg>';
                          }}
                        />
                      </div>

                      <div className="min-w-0 flex-1">
                        <p
                          className={`text-sm font-semibold truncate ${
                            isCurrent ? 'text-pink-300' : 'text-slate-100 group-hover:text-white'
                          }`}
                        >
                          {track.title}
                        </p>
                        <p className="text-xs text-slate-400 truncate">{track.album || 'Single'}</p>
                      </div>
                    </div>

                    <div className="flex items-center gap-3 shrink-0">
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
