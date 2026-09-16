import React, { useState } from 'react';
import {
  ChevronDown,
  Play,
  Pause,
  SkipBack,
  SkipForward,
  Shuffle,
  Repeat,
  Repeat1,
  Volume2,
  VolumeX,
  Heart,
  ListMusic,
  Clock,
  Gauge,
  FileText,
  Share2,
  FolderPlus,
  Sparkles,
  Check,
} from 'lucide-react';
import { Track, RepeatMode } from '../types';
import { formatTime } from '../utils';
import { triggerHaptic } from '../hooks/useAudioPlayer';

interface FullPlayerModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentTrack: Track | null;
  isPlaying: boolean;
  currentTime: number;
  duration: number;
  buffered: number;
  volume: number;
  isMuted: boolean;
  playbackRate: number;
  shuffle: boolean;
  repeatMode: RepeatMode;
  isFavorite: boolean;
  sleepTimerRemaining: number | null;
  onTogglePlay: () => void;
  onSeek: (time: number) => void;
  onNext: () => void;
  onPrev: () => void;
  onSetVolume: (vol: number) => void;
  onToggleMute: () => void;
  onSetPlaybackRate: (rate: number) => void;
  onToggleShuffle: () => void;
  onCycleRepeat: () => void;
  onToggleFavorite: () => void;
  onOpenQueue: () => void;
  onOpenSleepTimer: () => void;
  onOpenDetails: () => void;
  onOpenAddToPlaylist?: () => void;
}

export const FullPlayerModal: React.FC<FullPlayerModalProps> = ({
  isOpen,
  onClose,
  currentTrack,
  isPlaying,
  currentTime,
  duration,
  buffered,
  volume,
  isMuted,
  playbackRate,
  shuffle,
  repeatMode,
  isFavorite,
  sleepTimerRemaining,
  onTogglePlay,
  onSeek,
  onNext,
  onPrev,
  onSetVolume,
  onToggleMute,
  onSetPlaybackRate,
  onToggleShuffle,
  onCycleRepeat,
  onToggleFavorite,
  onOpenQueue,
  onOpenSleepTimer,
  onOpenDetails,
  onOpenAddToPlaylist,
}) => {
  const [isSeeking, setIsSeeking] = useState(false);
  const [seekVal, setSeekVal] = useState(0);
  const [showSpeedMenu, setShowSpeedMenu] = useState(false);
  const [copiedShare, setCopiedShare] = useState(false);

  if (!isOpen || !currentTrack) return null;

  const displayTime = isSeeking ? seekVal : currentTime;
  const progressPercent = duration > 0 ? (displayTime / duration) * 100 : 0;
  const bufferedPercent = buffered * 100;
  const remainingTime = Math.max(0, duration - displayTime);
  const isLossless = currentTrack.audio_format === 'FLAC' || currentTrack.mime_type.includes('flac');

  const speeds = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0];

  const handleShare = () => {
    triggerHaptic('medium');
    const shareText = `🎵 Listening to "${currentTrack.title}" by ${currentTrack.artist} on Telegram Music Cloud!`;
    if (navigator.clipboard) {
      navigator.clipboard.writeText(shareText).then(() => {
        setCopiedShare(true);
        setTimeout(() => setCopiedShare(false), 2000);
      }).catch(() => {});
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex flex-col justify-end sm:justify-center items-center bg-black/85 backdrop-blur-2xl transition-all duration-300">
      {/* Dynamic Background Aura */}
      <div
        className="absolute inset-0 opacity-30 pointer-events-none blur-3xl transition-all duration-1000"
        style={{
          background: `radial-gradient(circle at center 30%, ${currentTrack.palette.primary}, ${currentTrack.palette.secondary} 40%, transparent 80%)`,
        }}
      />

      {/* Main Player Sheet */}
      <div className="relative z-10 w-full max-w-lg h-[92vh] sm:h-auto sm:max-h-[90vh] flex flex-col justify-between p-6 sm:p-8 rounded-t-3xl sm:rounded-3xl glass-panel border border-white/10 shadow-2xl overflow-y-auto no-scrollbar">
        {/* Header Bar */}
        <div className="flex items-center justify-between">
          <button
            onClick={() => {
              triggerHaptic('light');
              onClose();
            }}
            className="w-10 h-10 rounded-2xl bg-white/5 hover:bg-white/10 text-slate-300 flex items-center justify-center border border-white/10 active:scale-95 transition-all"
            aria-label="Collapse player"
          >
            <ChevronDown className="w-5 h-5" />
          </button>

          <div className="text-center">
            <span className="text-[11px] font-bold tracking-widest text-slate-400 uppercase">
              Now Playing
            </span>
            <p className="text-xs font-semibold text-pink-400 truncate max-w-[200px]">
              {currentTrack.album || 'Single'}
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleShare}
              className="w-10 h-10 rounded-2xl bg-white/5 hover:bg-white/10 text-slate-300 flex items-center justify-center border border-white/10 active:scale-95 transition-all"
              aria-label="Share track"
              title="Share track"
            >
              {copiedShare ? (
                <Check className="w-4 h-4 text-emerald-400" />
              ) : (
                <Share2 className="w-4 h-4" />
              )}
            </button>

            <button
              onClick={() => {
                triggerHaptic('light');
                onOpenDetails();
              }}
              className="w-10 h-10 rounded-2xl bg-white/5 hover:bg-white/10 text-slate-300 flex items-center justify-center border border-white/10 active:scale-95 transition-all"
              aria-label="Track info and lyrics"
            >
              <FileText className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Artwork & Vinyl Showcase */}
        <div className="relative my-6 flex flex-col items-center justify-center">
          <div className="relative w-64 h-64 sm:w-72 sm:h-72 group">
            {/* Spinning Vinyl */}
            <div
              className={`absolute inset-0 rounded-full border-8 border-black/90 bg-neutral-900 shadow-2xl flex items-center justify-center transition-all ${
                isPlaying ? 'spin-vinyl' : 'spin-vinyl-paused'
              }`}
              style={{
                boxShadow: `0 0 50px ${currentTrack.palette.primary}40`,
              }}
            >
              {/* Vinyl grooves rings */}
              <div className="w-48 h-48 rounded-full border border-white/5" />
              <div className="w-36 h-36 rounded-full border border-white/5" />
              <div className="w-24 h-24 rounded-full border border-white/5" />
            </div>

            {/* Center Cover Art */}
            <div className="absolute inset-8 rounded-full overflow-hidden border-4 border-slate-900 z-10 shadow-inner">
              <img
                src={currentTrack.artwork_url}
                alt={currentTrack.title}
                onError={(e) => {
                  (e.target as HTMLImageElement).src =
                    'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200" fill="%23222"><rect width="200" height="200"/><text x="100" y="110" fill="%23fff" font-size="60" text-anchor="middle">🎵</text></svg>';
                }}
                className={`w-full h-full object-cover ${isPlaying ? 'spin-vinyl' : 'spin-vinyl-paused'}`}
              />
            </div>

            {/* Spindle hole */}
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-7 h-7 rounded-full bg-slate-950 border-2 border-white/40 z-20" />
          </div>

          {/* Animated 12-bar dynamic EQ visualizer */}
          <div className="flex items-center gap-1 mt-4 h-6">
            {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12].map((bar) => {
              const heightClass = isPlaying
                ? bar % 3 === 0
                  ? 'h-5'
                  : bar % 2 === 0
                  ? 'h-3.5'
                  : 'h-2'
                : 'h-1';
              return (
                <div
                  key={bar}
                  className={`w-1 rounded-full bg-gradient-to-t from-pink-500 to-purple-400 transition-all duration-300 ${heightClass}`}
                  style={{
                    animationDelay: `${bar * 80}ms`,
                  }}
                />
              );
            })}
          </div>
        </div>

        {/* Track Title & Artist & Favorite */}
        <div className="flex items-center justify-between gap-4 mt-1">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <h2 className="text-xl sm:text-2xl font-black text-white tracking-tight truncate">
                {currentTrack.title}
              </h2>
              {isLossless && (
                <span className="text-[10px] font-mono font-bold tracking-wider px-2 py-0.5 rounded-full bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 flex items-center gap-1 shrink-0">
                  <Sparkles className="w-2.5 h-2.5" />
                  LOSSLESS
                </span>
              )}
            </div>
            <p className="text-sm font-medium text-slate-400 truncate mt-0.5">
              {currentTrack.artist}
            </p>
          </div>

          <div className="flex items-center gap-2">
            {onOpenAddToPlaylist && (
              <button
                onClick={() => {
                  triggerHaptic('light');
                  onOpenAddToPlaylist();
                }}
                className="p-3 rounded-2xl border bg-white/5 border-white/10 text-slate-400 hover:text-white transition-all active:scale-90"
                title="Add to Playlist"
                aria-label="Add to Playlist"
              >
                <FolderPlus className="w-5 h-5" />
              </button>
            )}

            <button
              onClick={() => {
                triggerHaptic('medium');
                onToggleFavorite();
              }}
              className={`p-3 rounded-2xl border transition-all active:scale-90 ${
                isFavorite
                  ? 'bg-pink-500/20 border-pink-500/40 text-pink-500'
                  : 'bg-white/5 border-white/10 text-slate-400 hover:text-white'
              }`}
              aria-label="Toggle favorite"
            >
              <Heart className={`w-5 h-5 ${isFavorite ? 'fill-current' : ''}`} />
            </button>
          </div>
        </div>

        {/* Apple Music Style Scrubber with Draggable Glowing Knob and Time Tooltip */}
        <div className="mt-6">
          <div className="relative flex items-center group py-2">
            {/* Draggable Time Preview Tooltip */}
            {isSeeking && (
              <div
                className="absolute -top-7 px-2.5 py-1 rounded-lg bg-slate-900 border border-white/20 text-[11px] font-mono font-bold text-white shadow-xl -translate-x-1/2 pointer-events-none z-30"
                style={{ left: `${progressPercent}%` }}
              >
                {formatTime(seekVal)}
              </div>
            )}

            {/* Background track & buffered indicator */}
            <div className="w-full h-2 rounded-full bg-white/10 overflow-hidden relative pointer-events-none">
              <div
                className="absolute top-0 left-0 bottom-0 bg-white/20 transition-all duration-300"
                style={{ width: `${bufferedPercent}%` }}
              />
              <div
                className="absolute top-0 left-0 bottom-0 bg-gradient-to-r from-pink-500 via-purple-500 to-cyan-400"
                style={{ width: `${progressPercent}%` }}
              />
            </div>

            {/* Draggable Glowing Apple-Style Knob */}
            <div
              className={`absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-4 h-4 rounded-full bg-white shadow-lg pointer-events-none transition-transform duration-75 z-20 ${
                isSeeking ? 'scale-125 ring-4 ring-pink-500/40' : 'group-hover:scale-110'
              }`}
              style={{
                left: `${progressPercent}%`,
                boxShadow: `0 0 12px ${currentTrack.palette.primary}`,
              }}
            />

            {/* Native Range Slider */}
            <input
              type="range"
              min={0}
              max={duration || 100}
              step={0.1}
              value={displayTime}
              onMouseDown={() => setIsSeeking(true)}
              onTouchStart={() => setIsSeeking(true)}
              onChange={(e) => setSeekVal(parseFloat(e.target.value))}
              onMouseUp={() => {
                setIsSeeking(false);
                onSeek(seekVal);
              }}
              onTouchEnd={() => {
                setIsSeeking(false);
                onSeek(seekVal);
              }}
              className="absolute inset-0 opacity-0 cursor-pointer w-full h-8 z-20"
              aria-label="Seek track"
            />
          </div>

          {/* Time Labels (Elapsed & Remaining) */}
          <div className="flex justify-between text-xs font-mono text-slate-400 mt-1 px-0.5">
            <span>{formatTime(displayTime)}</span>
            <span>-{formatTime(remainingTime)}</span>
          </div>
        </div>

        {/* Primary Controls (Shuffle, Prev, Play/Pause, Next, Repeat) */}
        <div className="flex items-center justify-between gap-2 mt-4 px-2">
          {/* Shuffle */}
          <button
            onClick={onToggleShuffle}
            className={`p-3 rounded-xl transition-all ${
              shuffle ? 'text-pink-400 bg-pink-500/15' : 'text-slate-500 hover:text-slate-300'
            }`}
            aria-label="Shuffle"
          >
            <Shuffle className="w-5 h-5" />
          </button>

          {/* Previous Track */}
          <button
            onClick={onPrev}
            className="p-3 rounded-2xl hover:bg-white/10 text-slate-200 active:scale-90 transition-all"
            aria-label="Previous track"
          >
            <SkipBack className="w-6 h-6 fill-current" />
          </button>

          {/* Play / Pause Primary Button */}
          <button
            onClick={onTogglePlay}
            className="w-16 h-16 rounded-3xl bg-gradient-to-tr from-pink-500 via-purple-600 to-cyan-400 text-white flex items-center justify-center shadow-xl shadow-pink-500/30 active:scale-95 transition-all"
            aria-label={isPlaying ? 'Pause' : 'Play'}
          >
            {isPlaying ? (
              <Pause className="w-7 h-7 fill-current" />
            ) : (
              <Play className="w-7 h-7 fill-current ml-1" />
            )}
          </button>

          {/* Next Track */}
          <button
            onClick={onNext}
            className="p-3 rounded-2xl hover:bg-white/10 text-slate-200 active:scale-90 transition-all"
            aria-label="Next track"
          >
            <SkipForward className="w-6 h-6 fill-current" />
          </button>

          {/* Repeat */}
          <button
            onClick={onCycleRepeat}
            className={`p-3 rounded-xl transition-all ${
              repeatMode !== 'off'
                ? 'text-pink-400 bg-pink-500/15'
                : 'text-slate-500 hover:text-slate-300'
            }`}
            aria-label="Repeat mode"
          >
            {repeatMode === 'one' ? (
              <Repeat1 className="w-5 h-5" />
            ) : (
              <Repeat className="w-5 h-5" />
            )}
          </button>
        </div>

        {/* iOS-Style Volume Slider Bar */}
        <div className="flex items-center gap-3 mt-6 px-4 py-2.5 rounded-2xl bg-white/[0.04] border border-white/5">
          <button
            onClick={onToggleMute}
            className="text-slate-400 hover:text-white transition-colors"
            aria-label="Mute toggle"
          >
            {isMuted || volume === 0 ? (
              <VolumeX className="w-4 h-4 text-pink-400" />
            ) : (
              <Volume2 className="w-4 h-4" />
            )}
          </button>
          <input
            type="range"
            min={0}
            max={1}
            step={0.01}
            value={volume}
            onChange={(e) => onSetVolume(parseFloat(e.target.value))}
            className="w-full h-1 bg-white/20 rounded-full accent-pink-500 cursor-pointer"
            aria-label="Volume control"
          />
        </div>

        {/* Secondary Action Toolbar (Speed, Timer, Queue) */}
        <div className="flex items-center justify-around mt-4 pt-3 border-t border-white/10">
          {/* Playback Speed */}
          <div className="relative">
            <button
              onClick={() => setShowSpeedMenu(!showSpeedMenu)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold transition-all ${
                playbackRate !== 1.0
                  ? 'bg-pink-500/20 text-pink-400 border border-pink-500/30'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Gauge className="w-3.5 h-3.5" />
              <span>{playbackRate}x</span>
            </button>

            {showSpeedMenu && (
              <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 p-1 rounded-2xl glass-panel shadow-2xl border border-white/15 flex flex-col gap-1 z-50">
                {speeds.map((s) => (
                  <button
                    key={s}
                    onClick={() => {
                      onSetPlaybackRate(s);
                      setShowSpeedMenu(false);
                    }}
                    className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-colors ${
                      playbackRate === s
                        ? 'bg-pink-500 text-white'
                        : 'text-slate-300 hover:bg-white/10'
                    }`}
                  >
                    {s}x
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Sleep Timer */}
          <button
            onClick={onOpenSleepTimer}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold transition-all ${
              sleepTimerRemaining !== null
                ? 'bg-purple-500/20 text-purple-400 border border-purple-500/30'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Clock className="w-3.5 h-3.5" />
            <span>
              {sleepTimerRemaining !== null
                ? `${Math.ceil(sleepTimerRemaining / 60)}m`
                : 'Timer'}
            </span>
          </button>

          {/* Up Next Queue */}
          <button
            onClick={onOpenQueue}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold text-slate-400 hover:text-slate-200 transition-all"
          >
            <ListMusic className="w-3.5 h-3.5" />
            <span>Queue</span>
          </button>
        </div>
      </div>
    </div>
  );
};
