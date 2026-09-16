import { useState, useEffect, useRef, useCallback } from 'react';
import { Track, RepeatMode } from '../types';

declare global {
  interface Window {
    Telegram?: {
      WebApp?: {
        expand: () => void;
        ready: () => void;
        HapticFeedback?: {
          impactOccurred: (style: 'light' | 'medium' | 'heavy' | 'rigid' | 'soft') => void;
          notificationOccurred: (type: 'error' | 'success' | 'warning') => void;
          selectionChanged: () => void;
        };
        themeParams?: Record<string, string>;
        BackButton?: {
          show: () => void;
          hide: () => void;
          onClick: (cb: () => void) => void;
          offClick: (cb: () => void) => void;
        };
      };
    };
  }
}

export function triggerHaptic(style: 'light' | 'medium' | 'heavy' = 'light') {
  try {
    window.Telegram?.WebApp?.HapticFeedback?.impactOccurred(style);
  } catch {
    // Non-telegram browser fallback
  }
}

export function useAudioPlayer() {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [currentTrack, setCurrentTrack] = useState<Track | null>(null);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [currentTime, setCurrentTime] = useState<number>(0);
  const [duration, setDuration] = useState<number>(0);
  const [buffered, setBuffered] = useState<number>(0);
  const [volume, setVolumeState] = useState<number>(0.9);
  const [isMuted, setIsMuted] = useState<boolean>(false);
  const [playbackRate, setPlaybackRateState] = useState<number>(1.0);
  const [shuffle, setShuffle] = useState<boolean>(false);
  const [repeatMode, setRepeatMode] = useState<RepeatMode>('off');
  const [queue, setQueue] = useState<Track[]>([]);
  const [queueIndex, setQueueIndex] = useState<number>(-1);
  const [sleepTimerRemaining, setSleepTimerRemaining] = useState<number | null>(null);

  // Initialize audio element
  useEffect(() => {
    let audio = document.getElementById('audio-engine') as HTMLAudioElement | null;
    if (!audio) {
      audio = new Audio();
      audio.id = 'audio-engine';
      document.body.appendChild(audio);
    }
    audioRef.current = audio;
    audio.volume = 0.9;

    const onTimeUpdate = () => {
      if (!audio) return;
      setCurrentTime(audio.currentTime);
      if (audio.duration && !isNaN(audio.duration) && audio.duration !== Infinity) {
        setDuration(audio.duration);
      }
    };

    const onProgress = () => {
      if (!audio || !audio.duration || isNaN(audio.duration)) return;
      try {
        if (audio.buffered.length > 0) {
          const loaded = audio.buffered.end(audio.buffered.length - 1);
          setBuffered(Math.min(1, loaded / audio.duration));
        }
      } catch {
        // Ignored
      }
    };

    const onPlay = () => setIsPlaying(true);
    const onPause = () => setIsPlaying(false);

    audio.addEventListener('timeupdate', onTimeUpdate);
    audio.addEventListener('progress', onProgress);
    audio.addEventListener('play', onPlay);
    audio.addEventListener('pause', onPause);

    return () => {
      audio?.removeEventListener('timeupdate', onTimeUpdate);
      audio?.removeEventListener('progress', onProgress);
      audio?.removeEventListener('play', onPlay);
      audio?.removeEventListener('pause', onPause);
    };
  }, []);

  // Sleep Timer countdown
  useEffect(() => {
    if (sleepTimerRemaining === null) return;
    if (sleepTimerRemaining <= 0) {
      // Fade out audio and pause
      if (audioRef.current) {
        audioRef.current.pause();
        setIsPlaying(false);
      }
      setSleepTimerRemaining(null);
      return;
    }

    const timer = setInterval(() => {
      setSleepTimerRemaining((prev) => (prev !== null && prev > 0 ? prev - 1 : null));
    }, 1000);

    return () => clearInterval(timer);
  }, [sleepTimerRemaining]);

  // Handle Track Finished
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    const onEnded = () => {
      if (repeatMode === 'one') {
        audio.currentTime = 0;
        audio.play().catch(() => {});
      } else if (repeatMode === 'all' || queueIndex < queue.length - 1) {
        nextTrack();
      } else {
        setIsPlaying(false);
      }
    };

    audio.addEventListener('ended', onEnded);
    return () => audio.removeEventListener('ended', onEnded);
  });

  // Play a specific track
  const playTrack = useCallback(
    (track: Track, newQueue?: Track[]) => {
      const audio = audioRef.current;
      if (!audio) return;

      triggerHaptic('medium');
      setCurrentTrack(track);

      // Manage Queue
      if (newQueue && newQueue.length > 0) {
        setQueue(newQueue);
        const idx = newQueue.findIndex((t) => t.id === track.id);
        setQueueIndex(idx !== -1 ? idx : 0);
      } else if (queue.length === 0) {
        setQueue([track]);
        setQueueIndex(0);
      } else {
        const idx = queue.findIndex((t) => t.id === track.id);
        if (idx !== -1) {
          setQueueIndex(idx);
        } else {
          setQueue((prev) => [...prev, track]);
          setQueueIndex(queue.length);
        }
      }

      // Record Recently Played to localStorage
      try {
        const recentStr = localStorage.getItem('tpmc_recent_tracks');
        const recentList: number[] = recentStr ? JSON.parse(recentStr) : [];
        const updatedRecent = [track.id, ...recentList.filter((id) => id !== track.id)].slice(0, 30);
        localStorage.setItem('tpmc_recent_tracks', JSON.stringify(updatedRecent));
      } catch {
        // Ignored
      }

      // Setup audio source and initiate playback
      audio.src = track.stream_url;
      audio.playbackRate = playbackRate;
      audio.currentTime = 0;
      setCurrentTime(0);
      setDuration(track.duration || 0);

      audio.play().then(() => {
        setIsPlaying(true);
      }).catch((err) => {
        console.warn('Playback initiation error (waiting for user interaction):', err);
      });

      // Update MediaSession for native OS controls
      if ('mediaSession' in navigator) {
        navigator.mediaSession.metadata = new MediaMetadata({
          title: track.title,
          artist: track.artist,
          album: track.album,
          artwork: [{ src: track.artwork_url, sizes: '512x512', type: 'image/jpeg' }],
        });

        navigator.mediaSession.setActionHandler('play', () => {
          audio.play();
          setIsPlaying(true);
        });
        navigator.mediaSession.setActionHandler('pause', () => {
          audio.pause();
          setIsPlaying(false);
        });
        navigator.mediaSession.setActionHandler('previoustrack', () => prevTrack());
        navigator.mediaSession.setActionHandler('nexttrack', () => nextTrack());
        navigator.mediaSession.setActionHandler('seekto', (details) => {
          if (details.seekTime !== undefined) seek(details.seekTime);
        });
      }
    },
    [queue, playbackRate]
  );

  const togglePlay = useCallback(() => {
    const audio = audioRef.current;
    if (!audio) return;

    triggerHaptic('light');
    if (isPlaying) {
      audio.pause();
      setIsPlaying(false);
    } else {
      if (!currentTrack && queue.length > 0) {
        playTrack(queue[0]);
      } else {
        audio.play().then(() => setIsPlaying(true)).catch(() => {});
      }
    }
  }, [isPlaying, currentTrack, queue, playTrack]);

  const seek = useCallback((time: number) => {
    const audio = audioRef.current;
    if (!audio) return;
    triggerHaptic('light');
    const target = Math.max(0, Math.min(time, duration || audio.duration || 0));
    audio.currentTime = target;
    setCurrentTime(target);
  }, [duration]);

  const nextTrack = useCallback(() => {
    if (queue.length === 0) return;
    triggerHaptic('medium');

    let nextIdx: number;
    if (shuffle) {
      nextIdx = Math.floor(Math.random() * queue.length);
    } else {
      nextIdx = queueIndex + 1;
      if (nextIdx >= queue.length) {
        if (repeatMode === 'all') {
          nextIdx = 0;
        } else {
          setIsPlaying(false);
          return;
        }
      }
    }

    setQueueIndex(nextIdx);
    const nextT = queue[nextIdx];
    if (nextT) playTrack(nextT);
  }, [queue, queueIndex, shuffle, repeatMode, playTrack]);

  const prevTrack = useCallback(() => {
    const audio = audioRef.current;
    if (!audio) return;
    triggerHaptic('medium');

    if (currentTime > 3) {
      audio.currentTime = 0;
      setCurrentTime(0);
      return;
    }

    let prevIdx = queueIndex - 1;
    if (prevIdx < 0) {
      prevIdx = repeatMode === 'all' ? queue.length - 1 : 0;
    }
    setQueueIndex(prevIdx);
    const prevT = queue[prevIdx];
    if (prevT) playTrack(prevT);
  }, [currentTime, queue, queueIndex, repeatMode, playTrack]);

  const setVolume = useCallback((vol: number) => {
    const audio = audioRef.current;
    if (!audio) return;
    const clamped = Math.max(0, Math.min(1, vol));
    audio.volume = clamped;
    setVolumeState(clamped);
    if (clamped > 0 && isMuted) setIsMuted(false);
  }, [isMuted]);

  const toggleMute = useCallback(() => {
    const audio = audioRef.current;
    if (!audio) return;
    triggerHaptic('light');
    if (isMuted) {
      audio.volume = volume || 0.8;
      setIsMuted(false);
    } else {
      audio.volume = 0;
      setIsMuted(true);
    }
  }, [isMuted, volume]);

  const setPlaybackRate = useCallback((rate: number) => {
    const audio = audioRef.current;
    if (!audio) return;
    triggerHaptic('light');
    audio.playbackRate = rate;
    setPlaybackRateState(rate);
  }, []);

  const toggleShuffle = useCallback(() => {
    triggerHaptic('light');
    setShuffle((prev) => !prev);
  }, []);

  const cycleRepeat = useCallback(() => {
    triggerHaptic('light');
    setRepeatMode((prev) => {
      if (prev === 'off') return 'all';
      if (prev === 'all') return 'one';
      return 'off';
    });
  }, []);

  const addToQueue = useCallback((track: Track) => {
    triggerHaptic('light');
    setQueue((prev) => [...prev, track]);
  }, []);

  const playNext = useCallback((track: Track) => {
    triggerHaptic('light');
    setQueue((prev) => {
      const nextIdx = queueIndex + 1;
      const copy = [...prev];
      copy.splice(nextIdx, 0, track);
      return copy;
    });
  }, [queueIndex]);

  const removeFromQueue = useCallback((index: number) => {
    triggerHaptic('light');
    setQueue((prev) => prev.filter((_, i) => i !== index));
    if (index < queueIndex) {
      setQueueIndex((prev) => prev - 1);
    }
  }, [queueIndex]);

  const clearQueue = useCallback(() => {
    triggerHaptic('light');
    if (currentTrack) {
      setQueue([currentTrack]);
      setQueueIndex(0);
    } else {
      setQueue([]);
      setQueueIndex(-1);
    }
  }, [currentTrack]);

  const setSleepTimer = useCallback((minutes: number | null) => {
    triggerHaptic('medium');
    if (minutes === null) {
      setSleepTimerRemaining(null);
    } else {
      setSleepTimerRemaining(minutes * 60);
    }
  }, []);

  return {
    currentTrack,
    isPlaying,
    currentTime,
    duration,
    buffered,
    volume: isMuted ? 0 : volume,
    isMuted,
    playbackRate,
    shuffle,
    repeatMode,
    queue,
    queueIndex,
    sleepTimerRemaining,
    playTrack,
    togglePlay,
    seek,
    nextTrack,
    prevTrack,
    setVolume,
    toggleMute,
    setPlaybackRate,
    toggleShuffle,
    cycleRepeat,
    addToQueue,
    playNext,
    removeFromQueue,
    clearQueue,
    setSleepTimer,
  };
}
