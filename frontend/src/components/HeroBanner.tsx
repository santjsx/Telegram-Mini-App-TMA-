import React from 'react';
import { Play, Pause, Plus, Sparkles, Disc } from 'lucide-react';
import { Track } from '../types';
import { triggerHaptic } from '../hooks/useAudioPlayer';

interface HeroBannerProps {
  featuredTrack: Track | null;
  isPlaying: boolean;
  isCurrent: boolean;
  onPlay: (track: Track) => void;
  onAddToQueue: (track: Track) => void;
}

export const HeroBanner: React.FC<HeroBannerProps> = ({
  featuredTrack,
  isPlaying,
  isCurrent,
  onPlay,
  onAddToQueue,
}) => {
  if (!featuredTrack) return null;

  const isThisPlaying = isCurrent && isPlaying;

  return (
    <div className="relative w-full rounded-2xl sm:rounded-3xl overflow-hidden p-5 sm:p-7 border border-white/10 shadow-2xl bg-gradient-to-br from-white/[0.08] via-white/[0.03] to-transparent backdrop-blur-xl">
      {/* Background dynamic glow */}
      <div
        className="absolute -right-10 -bottom-10 w-72 h-72 rounded-full blur-3xl opacity-30 pointer-events-none"
        style={{
          background: `radial-gradient(circle, ${featuredTrack.palette.primary}, ${featuredTrack.palette.secondary})`,
        }}
      />

      <div className="relative z-10 flex flex-col sm:flex-row items-center sm:items-stretch gap-5">
        {/* Artwork with Vinyl Peek */}
        <div className="relative group shrink-0">
          <div className="relative w-36 h-36 sm:w-44 sm:h-44 rounded-2xl overflow-hidden shadow-2xl border border-white/10 z-10 bg-slate-900">
            <img
              src={featuredTrack.artwork_url}
              alt={featuredTrack.title}
              onError={(e) => {
                (e.target as HTMLImageElement).src =
                  'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" fill="%23222"><rect width="100" height="100"/><text x="50" y="55" fill="%23fff" font-size="30" text-anchor="middle">🎵</text></svg>';
              }}
              className={`w-full h-full object-cover transition-transform duration-700 group-hover:scale-105 ${
                isThisPlaying ? 'scale-105' : ''
              }`}
            />
          </div>

          {/* Vinyl behind cover */}
          <div
            className={`absolute top-2 -right-4 sm:-right-6 w-32 h-32 sm:w-40 sm:h-40 rounded-full border-4 border-black/80 bg-neutral-900 flex items-center justify-center shadow-2xl transition-all duration-700 ${
              isThisPlaying ? 'spin-vinyl translate-x-2 sm:translate-x-4' : 'opacity-80'
            }`}
          >
            <div className="w-10 h-10 rounded-full border border-white/20 bg-slate-800 flex items-center justify-center">
              <div className="w-3 h-3 rounded-full bg-pink-500" />
            </div>
          </div>
        </div>

        {/* Info & Action Controls */}
        <div className="flex flex-col justify-between flex-1 text-center sm:text-left">
          <div>
            <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-pink-500/15 border border-pink-500/25 text-pink-300 text-xs font-semibold mb-2">
              <Sparkles className="w-3.5 h-3.5" />
              <span>FEATURED TRACK</span>
            </div>

            <h2 className="text-xl sm:text-2xl font-black tracking-tight text-white line-clamp-1">
              {featuredTrack.title}
            </h2>
            <p className="text-sm font-medium text-slate-300 mt-1 line-clamp-1">
              {featuredTrack.artist} • <span className="text-slate-400">{featuredTrack.album}</span>
            </p>

            <div className="flex flex-wrap items-center justify-center sm:justify-start gap-2 mt-3 text-xs text-slate-400">
              <span className="px-2 py-0.5 rounded-md bg-white/5 border border-white/5 font-mono">
                {featuredTrack.audio_format}
              </span>
              <span className="px-2 py-0.5 rounded-md bg-white/5 border border-white/5">
                {featuredTrack.file_size_str}
              </span>
              <span className="px-2 py-0.5 rounded-md bg-white/5 border border-white/5 font-mono">
                {featuredTrack.duration_str}
              </span>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex items-center justify-center sm:justify-start gap-3 mt-4 pt-1">
            <button
              onClick={() => {
                triggerHaptic('medium');
                onPlay(featuredTrack);
              }}
              className="h-11 px-6 rounded-xl bg-gradient-to-r from-pink-500 to-purple-600 hover:from-pink-600 hover:to-purple-700 text-white font-bold text-sm shadow-lg shadow-pink-500/25 flex items-center gap-2 active:scale-95 transition-all"
            >
              {isThisPlaying ? <Pause className="w-4 h-4 fill-current" /> : <Play className="w-4 h-4 fill-current" />}
              <span>{isThisPlaying ? 'Pause' : 'Play Now'}</span>
            </button>

            <button
              onClick={() => {
                triggerHaptic('light');
                onAddToQueue(featuredTrack);
              }}
              className="h-11 px-4 rounded-xl bg-white/10 hover:bg-white/15 text-white text-sm font-medium border border-white/10 flex items-center gap-2 active:scale-95 transition-all"
            >
              <Plus className="w-4 h-4" />
              <span className="hidden sm:inline">Add to Queue</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
