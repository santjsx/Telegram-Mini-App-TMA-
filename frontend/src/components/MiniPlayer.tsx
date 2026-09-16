import React from 'react';
import { Play, Pause, SkipForward, ListMusic, Sparkles } from 'lucide-react';
import { Track } from '../types';
import { triggerHaptic } from '../hooks/useAudioPlayer';

interface MiniPlayerProps {
  currentTrack: Track | null;
  isPlaying: boolean;
  currentTime: number;
  duration: number;
  onTogglePlay: () => void;
  onNext: () => void;
  onOpenFullPlayer: () => void;
  onOpenQueue: () => void;
}

export const MiniPlayer: React.FC<MiniPlayerProps> = ({
  currentTrack,
  isPlaying,
  currentTime,
  duration,
  onTogglePlay,
  onNext,
  onOpenFullPlayer,
  onOpenQueue,
}) => {
  if (!currentTrack) return null;

  const progressPercent = duration > 0 ? (currentTime / duration) * 100 : 0;
  const isLossless = currentTrack.audio_format === 'FLAC' || currentTrack.mime_type.includes('flac');

  return (
    <div className="fixed bottom-3 sm:bottom-5 left-0 right-0 z-40 px-3 sm:px-6 max-w-2xl mx-auto pointer-events-none">
      <div
        onClick={onOpenFullPlayer}
        className="pointer-events-auto relative w-full h-16 rounded-2xl glass-panel shadow-2xl border border-white/15 flex items-center justify-between px-3 sm:px-4 cursor-pointer overflow-hidden group hover:border-pink-500/40 transition-all active:scale-[0.99]"
        style={{
          boxShadow: `0 12px 36px -8px rgba(0, 0, 0, 0.7), 0 0 24px ${currentTrack.palette.primary}25`,
        }}
      >
        {/* Real-time Progress Bar on Top Border */}
        <div className="absolute top-0 left-0 right-0 h-[2.5px] bg-white/10">
          <div
            className="h-full bg-gradient-to-r from-pink-500 via-purple-500 to-cyan-400 transition-all duration-150"
            style={{ width: `${progressPercent}%` }}
          />
        </div>

        {/* Left: Thumbnail & Animated EQ Wave */}
        <div className="flex items-center gap-3 min-w-0 flex-1">
          <div className="relative w-11 h-11 rounded-xl overflow-hidden bg-slate-900 border border-white/10 shrink-0">
            <img
              src={currentTrack.artwork_url}
              alt={currentTrack.title}
              onError={(e) => {
                (e.target as HTMLImageElement).src =
                  'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="44" height="44" fill="%23222"><rect width="44" height="44"/><text x="22" y="26" fill="%23fff" font-size="16" text-anchor="middle">🎵</text></svg>';
              }}
              className="w-full h-full object-cover"
            />
            {isPlaying && (
              <div className="absolute inset-0 bg-black/40 flex items-center justify-center gap-0.5">
                <div className="w-0.5 h-3 bg-white rounded-full eq-bar-1" />
                <div className="w-0.5 h-3 bg-white rounded-full eq-bar-2" />
                <div className="w-0.5 h-3 bg-white rounded-full eq-bar-3" />
              </div>
            )}
          </div>

          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-1.5">
              <p className="text-sm font-bold text-white truncate group-hover:text-pink-300 transition-colors">
                {currentTrack.title}
              </p>
              {isLossless && (
                <span className="text-[9px] font-mono px-1 py-0.2 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 shrink-0 hidden sm:inline">
                  LOSSLESS
                </span>
              )}
            </div>
            <p className="text-xs text-slate-400 truncate">{currentTrack.artist}</p>
          </div>
        </div>

        {/* Right: Controls (Play/Pause, Next, Queue) */}
        <div
          className="flex items-center gap-1 sm:gap-2 shrink-0 ml-2"
          onClick={(e) => e.stopPropagation()}
        >
          <button
            onClick={() => {
              triggerHaptic('medium');
              onTogglePlay();
            }}
            aria-label={isPlaying ? 'Pause' : 'Play'}
            className="w-10 h-10 rounded-xl bg-gradient-to-r from-pink-500 to-purple-600 text-white flex items-center justify-center shadow-md shadow-pink-500/25 active:scale-95 transition-all"
          >
            {isPlaying ? (
              <Pause className="w-4 h-4 fill-current" />
            ) : (
              <Play className="w-4 h-4 fill-current ml-0.5" />
            )}
          </button>

          <button
            onClick={() => {
              triggerHaptic('medium');
              onNext();
            }}
            aria-label="Next track"
            className="w-9 h-9 rounded-xl hover:bg-white/10 text-slate-300 flex items-center justify-center active:scale-95 transition-all"
          >
            <SkipForward className="w-4 h-4" />
          </button>

          <button
            onClick={() => {
              triggerHaptic('light');
              onOpenQueue();
            }}
            aria-label="Open queue"
            className="w-9 h-9 rounded-xl hover:bg-white/10 text-slate-300 flex items-center justify-center active:scale-95 transition-all"
          >
            <ListMusic className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
};
