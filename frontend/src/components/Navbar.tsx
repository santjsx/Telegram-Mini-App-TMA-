import React from 'react';
import { Disc3, Search, Sparkles, X } from 'lucide-react';
import { triggerHaptic } from '../hooks/useAudioPlayer';

interface NavbarProps {
  searchQuery: string;
  setSearchQuery: (query: string) => void;
  isSearchOpen: boolean;
  setIsSearchOpen: (open: boolean) => void;
  totalTracks: number;
}

export const Navbar: React.FC<NavbarProps> = ({
  searchQuery,
  setSearchQuery,
  isSearchOpen,
  setIsSearchOpen,
  totalTracks,
}) => {
  return (
    <header className="sticky top-0 z-30 w-full px-4 py-3 backdrop-blur-xl bg-obsidian/70 border-b border-white/5 transition-all">
      <div className="max-w-4xl mx-auto flex items-center justify-between gap-3">
        {/* Brand Logo & Status */}
        <div className="flex items-center gap-2.5">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-pink-500/20 to-purple-600/20 border border-pink-500/30 flex items-center justify-center shadow-lg shadow-pink-500/10">
            <Disc3 className="w-5 h-5 text-pink-400 animate-spin-slow" />
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <span className="text-base font-bold tracking-tight bg-gradient-to-r from-white via-slate-100 to-slate-400 bg-clip-text text-transparent">
                TPMC CLOUD
              </span>
              <span className="text-[10px] uppercase font-bold tracking-wider px-1.5 py-0.5 rounded-full bg-pink-500/10 border border-pink-500/20 text-pink-400">
                PRO
              </span>
            </div>
            <p className="text-[11px] text-slate-400 font-medium">
              {totalTracks > 0 ? `${totalTracks} tracks online` : 'Syncing Library...'}
            </p>
          </div>
        </div>

        {/* Right Action Icons */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => {
              triggerHaptic('light');
              setIsSearchOpen(!isSearchOpen);
            }}
            aria-label="Toggle search"
            className={`w-9 h-9 rounded-xl flex items-center justify-center transition-all ${
              isSearchOpen
                ? 'bg-pink-500 text-white shadow-lg shadow-pink-500/25'
                : 'bg-white/5 hover:bg-white/10 text-slate-300 border border-white/10'
            }`}
          >
            {isSearchOpen ? <X className="w-4 h-4" /> : <Search className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Expanded Search Bar */}
      {isSearchOpen && (
        <div className="max-w-4xl mx-auto mt-2.5 pt-2 border-t border-white/5 animate-fadeIn">
          <div className="relative flex items-center">
            <Search className="absolute left-3.5 w-4 h-4 text-slate-400 pointer-events-none" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search tracks, artists, or albums..."
              autoFocus
              className="w-full h-11 pl-10 pr-10 rounded-xl bg-white/[0.07] border border-white/10 text-sm text-white placeholder-slate-400 focus:outline-none focus:border-pink-500/60 focus:ring-1 focus:ring-pink-500/60 transition-all"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                className="absolute right-3 p-1 rounded-full text-slate-400 hover:text-white"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        </div>
      )}
    </header>
  );
};
