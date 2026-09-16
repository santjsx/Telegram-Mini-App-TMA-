import React, { useState, useEffect } from 'react';
import {
  X,
  Plus,
  Play,
  Shuffle,
  Trash2,
  Music,
  FolderPlus,
  ListMusic,
  Check,
  Download,
  Upload,
} from 'lucide-react';
import { Playlist, Track } from '../types';
import { triggerHaptic } from '../hooks/useAudioPlayer';
import { formatTime } from '../utils';

interface PlaylistsModalProps {
  isOpen: boolean;
  onClose: () => void;
  allTracks: Track[];
  onPlayTracks: (tracks: Track[]) => void;
  trackToAdd?: Track | null;
  onTrackAdded?: () => void;
  initialPlaylistId?: string | null;
}

const GRADIENT_PRESETS: [string, string][] = [
  ['#FF2D55', '#FF375F'], // Apple Red / Pink
  ['#AF52DE', '#5856D6'], // Purple / Indigo
  ['#007AFF', '#5AC8FA'], // iOS Blue / Cyan
  ['#FF9500', '#FFCC00'], // Sunrise Gold
  ['#34C759', '#30D158'], // Spotify Green
  ['#FF2D55', '#5856D6'], // Magenta / Royal
  ['#00DFD8', '#0070F3'], // Electric Cyan
  ['#FA709A', '#FEE140'], // Sunset Coral
];

export const PlaylistsModal: React.FC<PlaylistsModalProps> = ({
  isOpen,
  onClose,
  allTracks,
  onPlayTracks,
  trackToAdd = null,
  onTrackAdded,
  initialPlaylistId = null,
}) => {
  const [playlists, setPlaylists] = useState<Playlist[]>([]);
  const [selectedPlaylistId, setSelectedPlaylistId] = useState<string | null>(initialPlaylistId);
  const [isCreating, setIsCreating] = useState(false);
  const [newPlaylistName, setNewPlaylistName] = useState('');
  const [selectedGradientIndex, setSelectedGradientIndex] = useState(0);

  // Load playlists from localStorage
  useEffect(() => {
    try {
      const stored = localStorage.getItem('tpmc_custom_playlists');
      if (stored) {
        setPlaylists(JSON.parse(stored));
      } else {
        // Create default starter playlist
        const defaultPlaylist: Playlist = {
          id: 'favorites_mix',
          name: 'My Vibe Mix',
          description: 'Handpicked favorites and top tracks',
          coverGradient: GRADIENT_PRESETS[0],
          trackIds: allTracks.slice(0, 8).map((t) => t.id),
          createdAt: Date.now(),
          updatedAt: Date.now(),
        };
        setPlaylists([defaultPlaylist]);
        localStorage.setItem('tpmc_custom_playlists', JSON.stringify([defaultPlaylist]));
      }
    } catch {
      // ignore
    }
  }, [allTracks]);

  // Sync selected playlist if prop changes
  useEffect(() => {
    if (initialPlaylistId) {
      setSelectedPlaylistId(initialPlaylistId);
    }
  }, [initialPlaylistId]);

  const savePlaylists = (updated: Playlist[]) => {
    setPlaylists(updated);
    try {
      localStorage.setItem('tpmc_custom_playlists', JSON.stringify(updated));
    } catch {
      // ignore
    }
  };

  const handleCreatePlaylist = () => {
    if (!newPlaylistName.trim()) return;
    triggerHaptic('medium');

    const newPl: Playlist = {
      id: `pl_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`,
      name: newPlaylistName.trim(),
      coverGradient: GRADIENT_PRESETS[selectedGradientIndex],
      trackIds: trackToAdd ? [trackToAdd.id] : [],
      createdAt: Date.now(),
      updatedAt: Date.now(),
    };

    const updated = [newPl, ...playlists];
    savePlaylists(updated);
    setNewPlaylistName('');
    setIsCreating(false);

    if (trackToAdd) {
      if (onTrackAdded) onTrackAdded();
      onClose();
    } else {
      setSelectedPlaylistId(newPl.id);
    }
  };

  const handleAddTrackToPlaylist = (pl: Playlist) => {
    if (!trackToAdd) return;
    triggerHaptic('medium');

    if (pl.trackIds.includes(trackToAdd.id)) {
      if (onTrackAdded) onTrackAdded();
      onClose();
      return;
    }

    const updated = playlists.map((p) => {
      if (p.id === pl.id) {
        return {
          ...p,
          trackIds: [trackToAdd.id, ...p.trackIds],
          updatedAt: Date.now(),
        };
      }
      return p;
    });

    savePlaylists(updated);
    if (onTrackAdded) onTrackAdded();
    onClose();
  };

  const handleDeletePlaylist = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    triggerHaptic('heavy');
    const updated = playlists.filter((p) => p.id !== id);
    savePlaylists(updated);
    if (selectedPlaylistId === id) setSelectedPlaylistId(null);
  };

  const handleRemoveTrackFromPlaylist = (trackId: number) => {
    if (!selectedPlaylistId) return;
    triggerHaptic('light');

    const updated = playlists.map((p) => {
      if (p.id === selectedPlaylistId) {
        return {
          ...p,
          trackIds: p.trackIds.filter((id) => id !== trackId),
          updatedAt: Date.now(),
        };
      }
      return p;
    });

    savePlaylists(updated);
  };

  const handleExportPlaylists = () => {
    triggerHaptic('light');
    const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(playlists, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute('href', dataStr);
    downloadAnchor.setAttribute('download', `tpmc_playlists_backup_${new Date().toISOString().slice(0, 10)}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  const handleImportPlaylists = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (event) => {
      try {
        const imported = JSON.parse(event.target?.result as string);
        if (Array.isArray(imported)) {
          triggerHaptic('medium');
          savePlaylists(imported);
        }
      } catch {
        alert('Invalid playlist JSON backup file.');
      }
    };
    reader.readAsText(file);
  };

  if (!isOpen) return null;

  const currentPl = playlists.find((p) => p.id === selectedPlaylistId);
  const playlistTracks = currentPl
    ? currentPl.trackIds
        .map((id) => allTracks.find((t) => t.id === id))
        .filter((t): t is Track => !!t)
    : [];

  const totalDuration = playlistTracks.reduce((acc, t) => acc + (t.duration || 0), 0);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6 bg-black/80 backdrop-blur-2xl transition-all duration-300">
      <div className="relative w-full max-w-2xl max-h-[92vh] flex flex-col rounded-3xl glass-panel border border-white/10 shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/10">
          <div className="flex items-center gap-3">
            {selectedPlaylistId && !trackToAdd && (
              <button
                onClick={() => setSelectedPlaylistId(null)}
                className="text-xs font-semibold text-pink-400 hover:text-pink-300 flex items-center gap-1 mr-2"
              >
                ← Back
              </button>
            )}
            <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-pink-500 to-purple-600 flex items-center justify-center shadow-lg shadow-pink-500/20">
              <ListMusic className="w-4 h-4 text-white" />
            </div>
            <div>
              <h2 className="text-base font-bold text-white tracking-tight">
                {trackToAdd
                  ? 'Add to Playlist'
                  : selectedPlaylistId && currentPl
                  ? currentPl.name
                  : 'Playlists'}
              </h2>
              <p className="text-xs text-slate-400">
                {trackToAdd
                  ? `Choose a playlist for "${trackToAdd.title}"`
                  : `${playlists.length} custom ${playlists.length === 1 ? 'playlist' : 'playlists'}`}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {!selectedPlaylistId && !trackToAdd && (
              <>
                <button
                  onClick={handleExportPlaylists}
                  title="Export Playlists"
                  className="p-2 rounded-xl text-slate-400 hover:text-white hover:bg-white/10 transition-colors"
                >
                  <Download className="w-4 h-4" />
                </button>
                <label
                  title="Import Playlists"
                  className="p-2 rounded-xl text-slate-400 hover:text-white hover:bg-white/10 transition-colors cursor-pointer"
                >
                  <Upload className="w-4 h-4" />
                  <input type="file" accept=".json" onChange={handleImportPlaylists} className="hidden" />
                </label>
              </>
            )}
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
        </div>

        {/* Modal Body */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 no-scrollbar space-y-4">
          {/* Create New Playlist Form */}
          {isCreating ? (
            <div className="p-4 sm:p-5 rounded-2xl bg-white/[0.04] border border-white/10 space-y-4 animate-fadeIn">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <FolderPlus className="w-4 h-4 text-pink-400" />
                <span>New Playlist</span>
              </h3>

              <input
                type="text"
                placeholder="Playlist name..."
                value={newPlaylistName}
                onChange={(e) => setNewPlaylistName(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleCreatePlaylist()}
                autoFocus
                className="w-full px-4 py-2.5 rounded-xl bg-white/5 border border-white/10 text-white placeholder-slate-500 text-sm focus:outline-none focus:border-pink-500 transition-colors"
              />

              {/* Cover Gradient Presets */}
              <div>
                <p className="text-xs text-slate-400 mb-2">Cover Gradient:</p>
                <div className="flex items-center gap-2 overflow-x-auto pb-1 no-scrollbar">
                  {GRADIENT_PRESETS.map((grad, i) => (
                    <button
                      key={i}
                      type="button"
                      onClick={() => setSelectedGradientIndex(i)}
                      className={`w-9 h-9 rounded-xl shrink-0 transition-transform active:scale-95 flex items-center justify-center ${
                        selectedGradientIndex === i ? 'ring-2 ring-white scale-105' : 'opacity-70 hover:opacity-100'
                      }`}
                      style={{
                        background: `linear-gradient(135deg, ${grad[0]}, ${grad[1]})`,
                      }}
                    >
                      {selectedGradientIndex === i && <Check className="w-4 h-4 text-white drop-shadow" />}
                    </button>
                  ))}
                </div>
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setIsCreating(false)}
                  className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-400 hover:text-white hover:bg-white/5 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleCreatePlaylist}
                  disabled={!newPlaylistName.trim()}
                  className="px-5 py-2 rounded-xl text-xs font-bold bg-gradient-to-r from-pink-500 to-purple-600 text-white shadow-lg shadow-pink-500/20 disabled:opacity-40 transition-all"
                >
                  Create Playlist
                </button>
              </div>
            </div>
          ) : (
            /* Create Playlist Bar button */
            !selectedPlaylistId && (
              <button
                onClick={() => {
                  triggerHaptic('light');
                  setIsCreating(true);
                }}
                className="w-full py-3 px-4 rounded-2xl bg-white/[0.03] hover:bg-white/[0.07] border border-dashed border-white/15 text-slate-300 hover:text-white flex items-center justify-center gap-2 text-xs font-bold transition-all active:scale-98"
              >
                <Plus className="w-4 h-4 text-pink-400" />
                <span>Create New Playlist</span>
              </button>
            )
          )}

          {/* VIEW: Playlists List (When no single playlist is opened) */}
          {!selectedPlaylistId && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {playlists.map((pl) => {
                const count = pl.trackIds.length;
                const hasCurrentTrack = trackToAdd && pl.trackIds.includes(trackToAdd.id);

                return (
                  <div
                    key={pl.id}
                    onClick={() => {
                      if (trackToAdd) {
                        handleAddTrackToPlaylist(pl);
                      } else {
                        triggerHaptic('light');
                        setSelectedPlaylistId(pl.id);
                      }
                    }}
                    className={`group relative p-3.5 rounded-2xl bg-white/[0.03] hover:bg-white/[0.07] border border-white/5 hover:border-white/15 cursor-pointer transition-all flex items-center gap-3.5 ${
                      hasCurrentTrack ? 'ring-1 ring-pink-500/40 bg-pink-500/10' : ''
                    }`}
                  >
                    {/* Gradient Art */}
                    <div
                      className="w-14 h-14 rounded-xl flex items-center justify-center shadow-lg shrink-0 relative overflow-hidden"
                      style={{
                        background: `linear-gradient(135deg, ${pl.coverGradient[0]}, ${pl.coverGradient[1]})`,
                      }}
                    >
                      <Music className="w-6 h-6 text-white/90" />
                      {hasCurrentTrack && (
                        <div className="absolute inset-0 bg-black/50 flex items-center justify-center">
                          <Check className="w-6 h-6 text-pink-400 drop-shadow" />
                        </div>
                      )}
                    </div>

                    {/* Metadata */}
                    <div className="min-w-0 flex-1">
                      <h4 className="text-sm font-bold text-white truncate group-hover:text-pink-300 transition-colors">
                        {pl.name}
                      </h4>
                      <p className="text-xs text-slate-400 mt-0.5">
                        {count} {count === 1 ? 'song' : 'songs'}
                      </p>
                      {hasCurrentTrack && (
                        <span className="text-[10px] font-semibold text-pink-400">Already added</span>
                      )}
                    </div>

                    {/* Delete action */}
                    {!trackToAdd && (
                      <button
                        onClick={(e) => handleDeletePlaylist(pl.id, e)}
                        className="opacity-0 group-hover:opacity-100 p-2 text-slate-500 hover:text-red-400 transition-opacity"
                        title="Delete Playlist"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {/* VIEW: Single Selected Playlist Content */}
          {selectedPlaylistId && currentPl && (
            <div className="space-y-4 animate-fadeIn">
              {/* Playlist Banner */}
              <div
                className="p-5 rounded-2xl flex items-center gap-4 relative overflow-hidden shadow-2xl border border-white/10"
                style={{
                  background: `linear-gradient(135deg, ${currentPl.coverGradient[0]}33, ${currentPl.coverGradient[1]}15)`,
                }}
              >
                <div
                  className="w-20 h-20 rounded-2xl flex items-center justify-center shadow-xl shrink-0"
                  style={{
                    background: `linear-gradient(135deg, ${currentPl.coverGradient[0]}, ${currentPl.coverGradient[1]})`,
                  }}
                >
                  <ListMusic className="w-9 h-9 text-white" />
                </div>

                <div className="min-w-0 flex-1">
                  <span className="text-[10px] font-bold tracking-widest uppercase text-pink-400">
                    Playlist
                  </span>
                  <h3 className="text-xl font-black text-white truncate">{currentPl.name}</h3>
                  <div className="flex items-center gap-3 text-xs text-slate-300 mt-1">
                    <span>{playlistTracks.length} tracks</span>
                    <span>•</span>
                    <span>{formatTime(totalDuration)} total</span>
                  </div>

                  {/* Play Actions */}
                  {playlistTracks.length > 0 && (
                    <div className="flex items-center gap-2 mt-3">
                      <button
                        onClick={() => {
                          triggerHaptic('medium');
                          onPlayTracks(playlistTracks);
                          onClose();
                        }}
                        className="px-4 py-1.5 rounded-xl text-xs font-bold bg-white text-slate-950 flex items-center gap-1.5 shadow-lg active:scale-95 transition-all"
                      >
                        <Play className="w-3.5 h-3.5 fill-current" />
                        <span>Play All</span>
                      </button>
                      <button
                        onClick={() => {
                          triggerHaptic('medium');
                          const shuffled = [...playlistTracks].sort(() => Math.random() - 0.5);
                          onPlayTracks(shuffled);
                          onClose();
                        }}
                        className="px-4 py-1.5 rounded-xl text-xs font-bold bg-white/10 text-white flex items-center gap-1.5 hover:bg-white/20 active:scale-95 transition-all"
                      >
                        <Shuffle className="w-3.5 h-3.5" />
                        <span>Shuffle</span>
                      </button>
                    </div>
                  )}
                </div>
              </div>

              {/* Tracks in Playlist */}
              <div className="space-y-1">
                {playlistTracks.length === 0 ? (
                  <div className="py-12 text-center text-slate-500 text-xs">
                    This playlist is empty. Tap any song's "•••" menu and select "Add to Playlist" to populate it!
                  </div>
                ) : (
                  playlistTracks.map((track, i) => (
                    <div
                      key={track.id}
                      className="group flex items-center justify-between p-2.5 rounded-xl bg-white/[0.02] hover:bg-white/[0.06] border border-transparent hover:border-white/5 transition-all"
                    >
                      <div
                        className="flex items-center gap-3 min-w-0 flex-1 cursor-pointer"
                        onClick={() => {
                          triggerHaptic('light');
                          onPlayTracks(playlistTracks.slice(i).concat(playlistTracks.slice(0, i)));
                          onClose();
                        }}
                      >
                        <span className="w-5 text-center text-xs font-mono text-slate-500">
                          {i + 1}
                        </span>
                        <div className="w-10 h-10 rounded-lg overflow-hidden bg-slate-900 border border-white/10 shrink-0">
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
                          <p className="text-xs font-semibold text-white truncate">{track.title}</p>
                          <p className="text-[11px] text-slate-400 truncate">{track.artist}</p>
                        </div>
                      </div>

                      <div className="flex items-center gap-2 shrink-0">
                        <span className="text-xs font-mono text-slate-500">{track.duration_str}</span>
                        <button
                          onClick={() => handleRemoveTrackFromPlaylist(track.id)}
                          className="p-1.5 text-slate-500 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity"
                          title="Remove from playlist"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
