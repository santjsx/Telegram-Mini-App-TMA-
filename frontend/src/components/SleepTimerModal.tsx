import React from 'react';
import { X, Clock, Check } from 'lucide-react';
import { triggerHaptic } from '../hooks/useAudioPlayer';

interface SleepTimerModalProps {
  isOpen: boolean;
  onClose: () => void;
  sleepTimerRemaining: number | null;
  onSetTimer: (minutes: number | null) => void;
}

export const SleepTimerModal: React.FC<SleepTimerModalProps> = ({
  isOpen,
  onClose,
  sleepTimerRemaining,
  onSetTimer,
}) => {
  if (!isOpen) return null;

  const options = [
    { label: '15 Minutes', minutes: 15 },
    { label: '30 Minutes', minutes: 30 },
    { label: '45 Minutes', minutes: 45 },
    { label: '60 Minutes (1 Hour)', minutes: 60 },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-fadeIn">
      <div className="relative w-full max-w-xs rounded-3xl glass-panel border border-white/10 p-6 shadow-2xl">
        <div className="flex items-center justify-between pb-3 border-b border-white/10">
          <div className="flex items-center gap-2">
            <Clock className="w-4 h-4 text-purple-400" />
            <h3 className="text-sm font-bold text-white">Sleep Timer</h3>
          </div>
          <button
            onClick={() => {
              triggerHaptic('light');
              onClose();
            }}
            className="p-1.5 rounded-xl text-slate-400 hover:text-white"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="py-4 space-y-2">
          {options.map((opt) => (
            <button
              key={opt.minutes}
              onClick={() => {
                triggerHaptic('medium');
                onSetTimer(opt.minutes);
                onClose();
              }}
              className="w-full h-11 px-4 rounded-2xl bg-white/[0.04] hover:bg-white/[0.09] text-xs font-semibold text-slate-200 flex items-center justify-between transition-colors"
            >
              <span>{opt.label}</span>
              {sleepTimerRemaining && Math.ceil(sleepTimerRemaining / 60) === opt.minutes && (
                <Check className="w-4 h-4 text-pink-400" />
              )}
            </button>
          ))}

          {sleepTimerRemaining !== null && (
            <button
              onClick={() => {
                triggerHaptic('light');
                onSetTimer(null);
                onClose();
              }}
              className="w-full h-11 px-4 rounded-2xl bg-red-500/10 hover:bg-red-500/20 text-xs font-semibold text-red-400 flex items-center justify-center transition-colors"
            >
              Cancel Sleep Timer
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
