import React, { useState } from 'react';
import { X, FileText, Info, Share2, Check, Music } from 'lucide-react';
import { Track } from '../types';
import { triggerHaptic } from '../hooks/useAudioPlayer';

interface LyricsDetailsModalProps {
  isOpen: boolean;
  onClose: () => void;
  track: Track | null;
}

export const LyricsDetailsModal: React.FC<LyricsDetailsModalProps> = ({
  isOpen,
  onClose,
  track,
}) => {
  const [copied, setCopied] = useState(false);
  const [activeTab, setActiveTab] = useState<'info' | 'lyrics'>('info');

  if (!isOpen || !track) return null;

  const handleShare = () => {
    triggerHaptic('light');
    if (navigator.clipboard) {
      navigator.clipboard.writeText(window.location.href);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-fadeIn">
      <div className="relative w-full max-w-md rounded-3xl glass-panel border border-white/10 p-6 shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-white/10">
          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                triggerHaptic('light');
                setActiveTab('info');
              }}
              className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all ${
                activeTab === 'info'
                  ? 'bg-pink-500 text-white shadow-lg shadow-pink-500/20'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              Track Specs
            </button>
            <button
              onClick={() => {
                triggerHaptic('light');
                setActiveTab('lyrics');
              }}
              className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all ${
                activeTab === 'lyrics'
                  ? 'bg-pink-500 text-white shadow-lg shadow-pink-500/20'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              Lyrics
            </button>
          </div>

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

        {/* Tab 1: Technical Specs */}
        {activeTab === 'info' && (
          <div className="py-4 space-y-3">
            <div className="flex items-center gap-3 p-3 rounded-2xl bg-white/[0.04] border border-white/5">
              <img
                src={track.artwork_url}
                alt={track.title}
                className="w-14 h-14 rounded-xl object-cover bg-slate-900 border border-white/10"
              />
              <div className="min-w-0 flex-1">
                <h4 className="text-sm font-bold text-white truncate">{track.title}</h4>
                <p className="text-xs text-slate-400 truncate">{track.artist}</p>
                <p className="text-xs text-pink-400 truncate mt-0.5">{track.album}</p>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2 text-xs">
              <div className="p-3 rounded-2xl bg-white/[0.03] border border-white/5">
                <span className="text-[10px] uppercase font-bold text-slate-500">Format</span>
                <p className="font-mono font-bold text-slate-200 mt-0.5">{track.audio_format}</p>
              </div>
              <div className="p-3 rounded-2xl bg-white/[0.03] border border-white/5">
                <span className="text-[10px] uppercase font-bold text-slate-500">Duration</span>
                <p className="font-mono font-bold text-slate-200 mt-0.5">{track.duration_str}</p>
              </div>
              <div className="p-3 rounded-2xl bg-white/[0.03] border border-white/5">
                <span className="text-[10px] uppercase font-bold text-slate-500">File Size</span>
                <p className="font-mono font-bold text-slate-200 mt-0.5">{track.file_size_str}</p>
              </div>
              <div className="p-3 rounded-2xl bg-white/[0.03] border border-white/5">
                <span className="text-[10px] uppercase font-bold text-slate-500">Storage ID</span>
                <p className="font-mono font-bold text-slate-200 mt-0.5">#{track.id}</p>
              </div>
            </div>

            <button
              onClick={handleShare}
              className="w-full mt-2 h-11 rounded-2xl bg-white/10 hover:bg-white/15 text-white font-semibold text-xs border border-white/10 flex items-center justify-center gap-2 active:scale-95 transition-all"
            >
              {copied ? <Check className="w-4 h-4 text-green-400" /> : <Share2 className="w-4 h-4" />}
              <span>{copied ? 'Link Copied to Clipboard' : 'Share Track'}</span>
            </button>
          </div>
        )}

        {/* Tab 2: Lyrics View */}
        {activeTab === 'lyrics' && (
          <div className="py-6 text-center text-slate-400 space-y-4 max-h-[50vh] overflow-y-auto no-scrollbar">
            <Music className="w-8 h-8 mx-auto text-pink-400 opacity-60" />
            <p className="text-sm font-semibold text-white">Lyrics for "{track.title}"</p>
            <div className="space-y-3 text-xs leading-relaxed text-slate-300 font-medium">
              <p>♪ Synchronized stream audio playing ♪</p>
              <p className="text-slate-400 italic">
                (Embedded lyrics from ID3 tags or Telegram metadata will appear here)
              </p>
              <p>Feel the rhythm of the soundscape</p>
              <p>Streaming direct from Telegram Cloud</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
