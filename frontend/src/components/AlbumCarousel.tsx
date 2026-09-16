import React from 'react';
import { Disc, Mic2 } from 'lucide-react';
import { Album, Artist } from '../types';
import { triggerHaptic } from '../hooks/useAudioPlayer';

interface AlbumCarouselProps {
  title: string;
  items: (Album | Artist)[];
  type: 'album' | 'artist';
  onSelect: (name: string) => void;
}

export const AlbumCarousel: React.FC<AlbumCarouselProps> = ({
  title,
  items,
  type,
  onSelect,
}) => {
  if (!items || items.length === 0) return null;

  return (
    <div className="w-full">
      <div className="flex items-center justify-between mb-3 px-1">
        <h3 className="text-sm font-bold tracking-tight text-slate-200 uppercase flex items-center gap-2">
          {type === 'album' ? <Disc className="w-4 h-4 text-pink-400" /> : <Mic2 className="w-4 h-4 text-purple-400" />}
          <span>{title}</span>
        </h3>
      </div>

      <div className="flex gap-3.5 overflow-x-auto no-scrollbar pb-2">
        {items.map((item, idx) => {
          const isAlbum = type === 'album';
          const name = isAlbum ? (item as Album).name : (item as Artist).name;
          const artUrl = isAlbum ? (item as Album).artwork_url : undefined;
          const subtitle = isAlbum ? (item as Album).artist : `${item.track_count} tracks`;

          return (
            <div
              key={idx}
              onClick={() => {
                triggerHaptic('light');
                onSelect(name);
              }}
              className="shrink-0 w-32 sm:w-36 group cursor-pointer"
            >
              {/* Artwork Box */}
              <div
                className={`relative w-32 h-32 sm:w-36 sm:h-36 overflow-hidden bg-slate-900 border border-white/10 shadow-lg group-hover:border-pink-500/40 transition-all duration-300 ${
                  isAlbum ? 'rounded-2xl' : 'rounded-full'
                }`}
              >
                {artUrl ? (
                  <img
                    src={artUrl}
                    alt={name}
                    loading="lazy"
                    onError={(e) => {
                      (e.target as HTMLImageElement).src =
                        'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" fill="%23222"><rect width="100" height="100"/><text x="50" y="55" fill="%23fff" font-size="30" text-anchor="middle">🎵</text></svg>';
                    }}
                    className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                  />
                ) : (
                  <div
                    className="w-full h-full flex items-center justify-center"
                    style={{
                      background: `linear-gradient(135deg, ${item.palette.primary}40, ${item.palette.secondary}40)`,
                    }}
                  >
                    <Mic2 className="w-10 h-10 text-white/70" />
                  </div>
                )}
              </div>

              {/* Title & Subtitle */}
              <div className="mt-2 text-center sm:text-left">
                <p className="text-xs font-bold text-slate-200 truncate group-hover:text-pink-300 transition-colors">
                  {name}
                </p>
                <p className="text-[11px] text-slate-400 truncate mt-0.5">{subtitle}</p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
