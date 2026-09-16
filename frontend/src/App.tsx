import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { LibraryData, Track, ActiveTab } from './types';
import { useAudioPlayer, triggerHaptic } from './hooks/useAudioPlayer';
import { Navbar } from './components/Navbar';
import { HeroBanner } from './components/HeroBanner';
import { CategoryTabs } from './components/CategoryTabs';
import { TrackList } from './components/TrackList';
import { AlbumCarousel } from './components/AlbumCarousel';
import { MiniPlayer } from './components/MiniPlayer';
import { FullPlayerModal } from './components/FullPlayerModal';
import { QueueDrawer } from './components/QueueDrawer';
import { LyricsDetailsModal } from './components/LyricsDetailsModal';
import { SleepTimerModal } from './components/SleepTimerModal';
import { PlaylistsModal } from './components/PlaylistsModal';
import { AlbumModal } from './components/AlbumModal';
import { ArtistModal } from './components/ArtistModal';
import { getTelegramInitData } from './utils';

export function App() {
  const [library, setLibrary] = useState<LibraryData | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [isSearchOpen, setIsSearchOpen] = useState<boolean>(false);
  const [activeTab, setActiveTab] = useState<ActiveTab>('all');
  const [favorites, setFavorites] = useState<number[]>([]);
  const [recentTrackIds, setRecentTrackIds] = useState<number[]>([]);
  const [selectedFilterName, setSelectedFilterName] = useState<string | null>(null);

  // Modals state
  const [isFullPlayerOpen, setIsFullPlayerOpen] = useState<boolean>(false);
  const [isQueueOpen, setIsQueueOpen] = useState<boolean>(false);
  const [isDetailsOpen, setIsDetailsOpen] = useState<boolean>(false);
  const [isSleepTimerOpen, setIsSleepTimerOpen] = useState<boolean>(false);
  const [detailsTrack, setDetailsTrack] = useState<Track | null>(null);

  // Million-Dollar App Modals
  const [isPlaylistsOpen, setIsPlaylistsOpen] = useState<boolean>(false);
  const [trackToAdd, setTrackToAdd] = useState<Track | null>(null);
  const [selectedAlbum, setSelectedAlbum] = useState<string | null>(null);
  const [selectedArtist, setSelectedArtist] = useState<string | null>(null);
  const [playlistsCount, setPlaylistsCount] = useState<number>(1);

  const player = useAudioPlayer();

  // Telegram WebApp Setup & BackButton Management
  useEffect(() => {
    try {
      const tg = window.Telegram?.WebApp;
      if (tg) {
        tg.ready();
        tg.expand();
      }
    } catch {
      // Browser fallback
    }
  }, []);

  // Telegram native BackButton handling
  useEffect(() => {
    const tg = window.Telegram?.WebApp;
    if (!tg || !tg.BackButton) return;
    const bb = tg.BackButton;

    const anyModalOpen =
      isFullPlayerOpen ||
      isQueueOpen ||
      isDetailsOpen ||
      isSleepTimerOpen ||
      isPlaylistsOpen ||
      !!selectedAlbum ||
      !!selectedArtist;

    if (anyModalOpen) {
      bb.show();
      const onBack = () => {
        if (selectedAlbum) setSelectedAlbum(null);
        else if (selectedArtist) setSelectedArtist(null);
        else if (isPlaylistsOpen) {
          setIsPlaylistsOpen(false);
          setTrackToAdd(null);
        } else if (isDetailsOpen) setIsDetailsOpen(false);
        else if (isSleepTimerOpen) setIsSleepTimerOpen(false);
        else if (isQueueOpen) setIsQueueOpen(false);
        else if (isFullPlayerOpen) setIsFullPlayerOpen(false);
      };
      bb.onClick(onBack);
      return () => bb.offClick(onBack);
    } else {
      bb.hide();
    }
  }, [
    isFullPlayerOpen,
    isQueueOpen,
    isDetailsOpen,
    isSleepTimerOpen,
    isPlaylistsOpen,
    selectedAlbum,
    selectedArtist,
  ]);

  // Load favorites & recent & playlists count from LocalStorage
  useEffect(() => {
    try {
      const favStr = localStorage.getItem('tpmc_favorites');
      if (favStr) setFavorites(JSON.parse(favStr));

      const recStr = localStorage.getItem('tpmc_recent_tracks');
      if (recStr) setRecentTrackIds(JSON.parse(recStr));

      const plStr = localStorage.getItem('tpmc_custom_playlists');
      if (plStr) {
        const parsedPl = JSON.parse(plStr);
        setPlaylistsCount(Array.isArray(parsedPl) ? parsedPl.length : 1);
      }
    } catch {
      // Ignored
    }
  }, [isPlaylistsOpen]);

  // Toggle Favorite
  const handleToggleFavorite = useCallback((trackId: number) => {
    setFavorites((prev) => {
      const next = prev.includes(trackId)
        ? prev.filter((id) => id !== trackId)
        : [...prev, trackId];
      localStorage.setItem('tpmc_favorites', JSON.stringify(next));
      return next;
    });
  }, []);

  // Instant Library Hydration + Background Refresh
  useEffect(() => {
    // 1. Instant hydration from cache (0ms perceived time to interactive)
    try {
      const cached = localStorage.getItem('tpmc_library_cache');
      if (cached) {
        const parsed = JSON.parse(cached);
        setLibrary(parsed);
        setIsLoading(false);
      }
    } catch {
      // Ignored
    }

    // 2. Background fresh fetch
    const fetchLibrary = async () => {
      try {
        const initData = getTelegramInitData();
        const urlParams = new URLSearchParams(window.location.search);
        const userIdParam = urlParams.get('user_id');

        let fetchUrl = '/api/library';
        const params = new URLSearchParams();
        if (initData) params.set('initData', initData);
        if (userIdParam) params.set('user_id', userIdParam);
        if (params.toString()) fetchUrl += `?${params.toString()}`;

        const headers: Record<string, string> = {};
        if (initData) headers['X-Telegram-Init-Data'] = initData;
        if (userIdParam) headers['X-User-Id'] = userIdParam;

        const res = await fetch(fetchUrl, { headers });
        if (res.ok) {
          const data: LibraryData = await res.json();
          setLibrary(data);
          localStorage.setItem('tpmc_library_cache', JSON.stringify(data));
        }
      } catch (err) {
        console.warn('Library refresh notice:', err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchLibrary();
  }, []);

  // Filtered tracks calculation
  const allTracks = library?.tracks || [];

  const filteredTracks = useMemo(() => {
    let list = allTracks;

    // 1. Category Tab Filter
    if (activeTab === 'favorites') {
      list = list.filter((t) => favorites.includes(t.id) || t.is_favorite);
    } else if (activeTab === 'recent') {
      list = recentTrackIds
        .map((id) => allTracks.find((t) => t.id === id))
        .filter((t): t is Track => !!t);
    }

    // 2. Specific Album or Artist Filter (if clicked from carousel)
    if (selectedFilterName) {
      list = list.filter(
        (t) =>
          t.album.toLowerCase() === selectedFilterName.toLowerCase() ||
          t.artist.toLowerCase() === selectedFilterName.toLowerCase()
      );
    }

    // 3. Search Query Filter
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      list = list.filter(
        (t) =>
          t.title.toLowerCase().includes(q) ||
          t.artist.toLowerCase().includes(q) ||
          t.album.toLowerCase().includes(q) ||
          t.genre.toLowerCase().includes(q)
      );
    }

    return list;
  }, [allTracks, activeTab, favorites, recentTrackIds, selectedFilterName, searchQuery]);

  const featuredTrack = allTracks.length > 0 ? allTracks[0] : null;

  return (
    <div className="relative min-h-screen bg-obsidian text-white flex flex-col font-sans selection:bg-pink-500/30 selection:text-pink-200">
      {/* Ambient Color Glow reacting to active track */}
      <div
        className="ambient-glow"
        style={
          {
            '--glow-color': player.currentTrack
              ? `${player.currentTrack.palette.primary}25`
              : 'rgba(255, 42, 109, 0.15)',
          } as React.CSSProperties
        }
      />

      {/* Top Navigation Bar */}
      <Navbar
        searchQuery={searchQuery}
        setSearchQuery={setSearchQuery}
        isSearchOpen={isSearchOpen}
        setIsSearchOpen={setIsSearchOpen}
        totalTracks={allTracks.length}
      />

      {/* Main Content Area */}
      <main className="flex-1 w-full max-w-4xl mx-auto px-4 py-4 space-y-6 safe-pb-dock relative z-10">
        {/* Active Filter Pill (if clicked from carousel) */}
        {selectedFilterName && (
          <div className="flex items-center justify-between px-4 py-2 rounded-xl bg-pink-500/15 border border-pink-500/30 text-xs font-semibold text-pink-300">
            <span>Filtered by: "{selectedFilterName}"</span>
            <button
              onClick={() => setSelectedFilterName(null)}
              className="text-slate-400 hover:text-white"
            >
              Clear Filter
            </button>
          </div>
        )}

        {/* Hero Banner Spotlight */}
        {!searchQuery && !selectedFilterName && activeTab === 'all' && (
          <HeroBanner
            featuredTrack={featuredTrack}
            isPlaying={player.isPlaying}
            isCurrent={player.currentTrack?.id === featuredTrack?.id}
            onPlay={(t) => player.playTrack(t, allTracks)}
            onAddToQueue={player.addToQueue}
          />
        )}

        {/* Album & Artist Carousel Section (Clicking opens rich dedicated modal!) */}
        {!searchQuery && !selectedFilterName && activeTab === 'all' && library && (
          <div className="space-y-6 pt-1">
            {library.albums.length > 0 && (
              <AlbumCarousel
                title="Top Albums"
                items={library.albums}
                type="album"
                onSelect={(name) => {
                  triggerHaptic('medium');
                  setSelectedAlbum(name);
                }}
              />
            )}
            {library.artists.length > 0 && (
              <AlbumCarousel
                title="Featured Artists"
                items={library.artists}
                type="artist"
                onSelect={(name) => {
                  triggerHaptic('medium');
                  setSelectedArtist(name);
                }}
              />
            )}
          </div>
        )}

        {/* Category Filter Chips */}
        <div className="pt-2">
          <CategoryTabs
            activeTab={activeTab}
            setActiveTab={(tab) => {
              if (tab === 'playlists') {
                triggerHaptic('light');
                setIsPlaylistsOpen(true);
              } else {
                setActiveTab(tab);
                setSelectedFilterName(null);
              }
            }}
            counts={{
              all: allTracks.length,
              favorites: favorites.length,
              recent: recentTrackIds.length,
              playlists: playlistsCount,
              albums: library?.albums.length || 0,
              artists: library?.artists.length || 0,
            }}
          />
        </div>

        {/* Tracks List Section */}
        <section className="space-y-3 pt-1">
          <div className="flex items-center justify-between px-1">
            <h3 className="text-sm font-bold tracking-tight text-slate-300 uppercase">
              {activeTab === 'favorites'
                ? 'Your Favorites'
                : activeTab === 'recent'
                ? 'Recently Played'
                : 'Music Catalog'}
            </h3>
            <span className="text-xs text-slate-500 font-medium font-mono">
              {filteredTracks.length} {filteredTracks.length === 1 ? 'song' : 'songs'}
            </span>
          </div>

          {/* Skeletons on cold load */}
          {isLoading && !library ? (
            <div className="space-y-2">
              {[1, 2, 3, 4, 5].map((i) => (
                <div key={i} className="h-16 rounded-2xl skeleton-box" />
              ))}
            </div>
          ) : (
            <TrackList
              tracks={filteredTracks}
              currentTrack={player.currentTrack}
              isPlaying={player.isPlaying}
              favorites={favorites}
              onToggleFavorite={handleToggleFavorite}
              onPlay={(t) => player.playTrack(t, filteredTracks)}
              onPlayNext={player.playNext}
              onAddToQueue={player.addToQueue}
              onAddToPlaylist={(t) => {
                triggerHaptic('light');
                setTrackToAdd(t);
                setIsPlaylistsOpen(true);
              }}
              onSelectAlbum={(alb) => {
                triggerHaptic('light');
                setSelectedAlbum(alb);
              }}
              onSelectArtist={(art) => {
                triggerHaptic('light');
                setSelectedArtist(art);
              }}
              onOpenDetails={(t) => {
                setDetailsTrack(t);
                setIsDetailsOpen(true);
              }}
              onPrefetch={player.prefetchTrack}
            />
          )}
        </section>
      </main>

      {/* Floating Bottom Mini-Player */}
      <MiniPlayer
        currentTrack={player.currentTrack}
        isPlaying={player.isPlaying}
        currentTime={player.currentTime}
        duration={player.duration}
        onTogglePlay={player.togglePlay}
        onNext={player.nextTrack}
        onOpenFullPlayer={() => {
          triggerHaptic('light');
          setIsFullPlayerOpen(true);
        }}
        onOpenQueue={() => {
          triggerHaptic('light');
          setIsQueueOpen(true);
        }}
      />

      {/* Fullscreen Expandable Luxury Player Sheet */}
      <FullPlayerModal
        isOpen={isFullPlayerOpen}
        onClose={() => setIsFullPlayerOpen(false)}
        currentTrack={player.currentTrack}
        isPlaying={player.isPlaying}
        currentTime={player.currentTime}
        duration={player.duration}
        buffered={player.buffered}
        volume={player.volume}
        isMuted={player.isMuted}
        playbackRate={player.playbackRate}
        shuffle={player.shuffle}
        repeatMode={player.repeatMode}
        isFavorite={
          player.currentTrack ? favorites.includes(player.currentTrack.id) : false
        }
        sleepTimerRemaining={player.sleepTimerRemaining}
        onTogglePlay={player.togglePlay}
        onSeek={player.seek}
        onNext={player.nextTrack}
        onPrev={player.prevTrack}
        onSetVolume={player.setVolume}
        onToggleMute={player.toggleMute}
        onSetPlaybackRate={player.setPlaybackRate}
        onToggleShuffle={player.toggleShuffle}
        onCycleRepeat={player.cycleRepeat}
        onToggleFavorite={() => {
          if (player.currentTrack) handleToggleFavorite(player.currentTrack.id);
        }}
        onOpenQueue={() => setIsQueueOpen(true)}
        onOpenSleepTimer={() => setIsSleepTimerOpen(true)}
        onOpenDetails={() => {
          setDetailsTrack(player.currentTrack);
          setIsDetailsOpen(true);
        }}
        onOpenAddToPlaylist={() => {
          if (player.currentTrack) {
            setTrackToAdd(player.currentTrack);
            setIsPlaylistsOpen(true);
          }
        }}
      />

      {/* Slide-over Queue Drawer */}
      <QueueDrawer
        isOpen={isQueueOpen}
        onClose={() => setIsQueueOpen(false)}
        queue={player.queue}
        queueIndex={player.queueIndex}
        onPlayTrack={(t) => player.playTrack(t)}
        onRemoveTrack={player.removeFromQueue}
        onClearQueue={player.clearQueue}
      />

      {/* Playlists Manager Modal */}
      <PlaylistsModal
        isOpen={isPlaylistsOpen}
        onClose={() => {
          setIsPlaylistsOpen(false);
          setTrackToAdd(null);
        }}
        allTracks={allTracks}
        trackToAdd={trackToAdd}
        onPlayTracks={(tracks) => {
          if (tracks.length > 0) {
            player.playTrack(tracks[0], tracks);
          }
        }}
        onTrackAdded={() => {
          triggerHaptic('medium');
        }}
      />

      {/* Album Showcase Modal */}
      <AlbumModal
        isOpen={!!selectedAlbum}
        onClose={() => setSelectedAlbum(null)}
        albumName={selectedAlbum}
        allTracks={allTracks}
        currentTrack={player.currentTrack}
        isPlaying={player.isPlaying}
        onPlayTrack={(t, q) => player.playTrack(t, q)}
        onSelectArtist={(art) => {
          setSelectedAlbum(null);
          setSelectedArtist(art);
        }}
        favorites={favorites}
        onToggleFavorite={handleToggleFavorite}
      />

      {/* Artist Profile Modal */}
      <ArtistModal
        isOpen={!!selectedArtist}
        onClose={() => setSelectedArtist(null)}
        artistName={selectedArtist}
        allTracks={allTracks}
        currentTrack={player.currentTrack}
        isPlaying={player.isPlaying}
        onPlayTrack={(t, q) => player.playTrack(t, q)}
        onSelectAlbum={(alb) => {
          setSelectedArtist(null);
          setSelectedAlbum(alb);
        }}
        favorites={favorites}
        onToggleFavorite={handleToggleFavorite}
      />

      {/* Track Specs & Lyrics Modal */}
      <LyricsDetailsModal
        isOpen={isDetailsOpen}
        onClose={() => setIsDetailsOpen(false)}
        track={detailsTrack}
      />

      {/* Sleep Timer Preset Modal */}
      <SleepTimerModal
        isOpen={isSleepTimerOpen}
        onClose={() => setIsSleepTimerOpen(false)}
        sleepTimerRemaining={player.sleepTimerRemaining}
        onSetTimer={player.setSleepTimer}
      />
    </div>
  );
}
