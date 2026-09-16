import React from 'react';
import { Music, Heart, Clock, ListMusic, Disc, Mic2 } from 'lucide-react';
import { ActiveTab } from '../types';
import { triggerHaptic } from '../hooks/useAudioPlayer';

interface CategoryTabsProps {
  activeTab: ActiveTab;
  setActiveTab: (tab: ActiveTab) => void;
  counts: {
    all: number;
    favorites: number;
    recent: number;
    playlists: number;
    albums: number;
    artists: number;
  };
}

export const CategoryTabs: React.FC<CategoryTabsProps> = ({
  activeTab,
  setActiveTab,
  counts,
}) => {
  const tabs = [
    { id: 'all' as ActiveTab, label: 'All Songs', icon: Music, count: counts.all },
    { id: 'favorites' as ActiveTab, label: 'Favorites', icon: Heart, count: counts.favorites },
    { id: 'playlists' as ActiveTab, label: 'Playlists', icon: ListMusic, count: counts.playlists },
    { id: 'recent' as ActiveTab, label: 'Recent', icon: Clock, count: counts.recent },
    { id: 'albums' as ActiveTab, label: 'Albums', icon: Disc, count: counts.albums },
    { id: 'artists' as ActiveTab, label: 'Artists', icon: Mic2, count: counts.artists },
  ];

  return (
    <div className="flex items-center gap-2 overflow-x-auto py-2 no-scrollbar scroll-smooth">
      {tabs.map((tab) => {
        const Icon = tab.icon;
        const isActive = activeTab === tab.id;

        return (
          <button
            key={tab.id}
            onClick={() => {
              triggerHaptic('light');
              setActiveTab(tab.id);
            }}
            className={`shrink-0 h-10 px-4 rounded-xl text-xs font-semibold flex items-center gap-2 transition-all active:scale-95 ${
              isActive
                ? 'bg-gradient-to-r from-pink-500 to-purple-600 text-white shadow-lg shadow-pink-500/20'
                : 'bg-white/[0.05] hover:bg-white/[0.09] text-slate-300 border border-white/5'
            }`}
          >
            <Icon className={`w-3.5 h-3.5 ${isActive ? 'text-white' : 'text-slate-400'}`} />
            <span>{tab.label}</span>
            {tab.count > 0 && (
              <span
                className={`text-[10px] px-1.5 py-0.2 rounded-full ${
                  isActive ? 'bg-white/20 text-white' : 'bg-white/10 text-slate-400'
                }`}
              >
                {tab.count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
};
