import React from 'react';
import { X, Trash2, Music, Play, Disc } from 'lucide-react';
import { Track } from '../types';
import { triggerHaptic } from '../hooks/useAudioPlayer';

interface QueueDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  queue: Track[];
  queueIndex: number;
  onPlayTrack: (track: Track) => void;
  onRemoveTrack: (index: number) => void;
  onClearQueue: () => void;
}

export const QueueDrawer: React.FC<QueueDrawerProps> = ({
  isOpen,
  onClose,
  queue,
  queueIndex,
  onPlayTrack,
  onRemoveTrack,
  onClearQueue,
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/70 backdrop-blur-md animate-fadeIn">
      <div className="relative w-full max-w-md h-full glass-panel border-l border-white/10 flex flex-col p-5 sm:p-6 shadow-2xl">
        {/* Drawer Header */}
        <div className="flex items-center justify-between pb-4 border-b border-white/10">
          <div>
            <h3 className="text-base font-bold text-white tracking-tight">Playing Queue</h3>
            <p className="text-xs text-slate-400 mt-0.5">
              {queue.length} {queue.length === 1 ? 'track' : 'tracks'} queued
            </p>
          </div>

          <div className="flex items-center gap-2">
            {queue.length > 0 && (
              <button
                onClick={() => {
                  triggerHaptic('light');
                  onClearQueue();
                }}
                className="p-2 rounded-xl text-slate-400 hover:text-red-400 hover:bg-white/5 transition-colors"
                title="Clear queue"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            )}
            <button
              onClick={() => {
                triggerHaptic('light');
                onClose();
              }}
              className="p-2 rounded-xl text-slate-400 hover:text-white hover:bg-white/5 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Queue Items List */}
        <div className="flex-1 overflow-y-auto no-scrollbar py-3 space-y-2">
          {queue.length === 0 ? (
            <div className="text-center py-20 text-slate-500">
              <Music className="w-8 h-8 mx-auto mb-2 opacity-50" />
              <p className="text-xs">Your queue is empty</p>
            </div>
          ) : (
            queue.map((track, idx) => {
              const isCurrent = idx === queueIndex;

              return (
                <div
                  key={`${track.id}-${idx}`}
                  className={`flex items-center justify-between p-2.5 rounded-2xl transition-all ${
                    isCurrent
                      ? 'bg-pink-500/15 border border-pink-500/30'
                      : 'bg-white/[0.03] hover:bg-white/[0.06] border border-transparent'
                  }`}
                >
                  {/* Left: Thumbnail & Info */}
                  <div
                    className="flex items-center gap-3 min-w-0 flex-1 cursor-pointer"
                    onClick={() => {
                      triggerHaptic('light');
                      onPlayTrack(track);
                    }}
                  >
                    <div className="relative w-10 h-10 rounded-xl overflow-hidden bg-slate-900 shrink-0">
                      <img
                        src={track.artwork_url}
                        alt={track.title}
                        onError={(e) => {
                          (e.target as HTMLImageElement).src =
                            'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" fill="%23222"><rect width="40" height="40"/><text x="20" y="24" fill="%23fff" font-size="14" text-anchor="middle">🎵</text></svg>';
                        }}
                        className="w-full h-full object-cover"
                      />
                      {isCurrent && (
                        <div className="absolute inset-0 bg-black/60 flex items-center justify-center">
                          <Play className="w-3.5 h-3.5 text-pink-400 fill-current" />
                        </div>
                      )}
                    </div>

                    <div className="min-w-0 flex-1">
                      <p
                        className={`text-xs font-bold truncate ${
                          isCurrent ? 'text-pink-300' : 'text-slate-200'
                        }`}
                      >
                        {track.title}
                      </p>
                      <p className="text-[11px] text-slate-400 truncate">{track.artist}</p>
                    </div>
                  </div>

                  {/* Right: Remove Button */}
                  <button
                    onClick={() => {
                      triggerHaptic('light');
                      onRemoveTrack(idx);
                    }}
                    className="p-2 text-slate-500 hover:text-red-400 transition-colors ml-2"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
};
