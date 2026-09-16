/**
 * Telegram Mini App Music Player — Production Engine
 * Modern, luxury dark-mode audio player with radial arc gauge,
 * real album artwork extraction, dancing waveform visualizer,
 * and direct MTProto byte-range streaming.
 */

document.addEventListener("DOMContentLoaded", () => {
  const tg = window.Telegram?.WebApp;

  // 1. Initialize Telegram WebApp
  if (tg) {
    tg.ready();
    tg.expand();
    try {
      tg.setHeaderColor("#0B0B10");
      tg.setBackgroundColor("#0B0B10");
      tg.enableClosingConfirmation();
    } catch (e) {
      console.warn("Telegram WebApp color config:", e);
    }
  }

  function triggerHaptic(type = "light") {
    if (tg?.HapticFeedback) {
      if (type === "impact") tg.HapticFeedback.impactOccurred("medium");
      else if (type === "light") tg.HapticFeedback.impactOccurred("light");
      else if (type === "success") tg.HapticFeedback.notificationOccurred("success");
    }
  }

  function escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  // 2. State
  let allTracks = [];
  let currentPlaylist = [];
  let currentIndex = -1;
  let isPlaying = false;
  let isShuffle = false;
  let repeatMode = 0; // 0: off, 1: all, 2: one
  let favorites = new Set(JSON.parse(localStorage.getItem("tpmc_favorites") || "[]"));

  // 3. DOM Elements
  const audio = document.getElementById("audio-engine");
  const discoverView = document.getElementById("discover-view");
  const nowPlayingOverlay = document.getElementById("now-playing-overlay");
  
  // Mini Player
  const miniPlayer = document.getElementById("mini-player");
  const miniPlayerBar = document.getElementById("mini-player-bar");
  const miniPlayBtn = document.getElementById("mini-btn-play");
  const miniProgressFill = document.getElementById("mini-progress-fill");
  const miniTitle = document.getElementById("mini-title");
  const miniArtist = document.getElementById("mini-artist");
  const miniThumbImg = document.getElementById("mini-thumb-img");

  // Full Player Elements
  const playerTitle = document.getElementById("player-title");
  const playerArtist = document.getElementById("player-artist");
  const playerContext = document.getElementById("player-context");
  const vinylDisc = document.getElementById("vinyl-disc");
  const vinylArtworkImg = document.getElementById("vinyl-artwork-img");
  const radialProgressCircle = document.getElementById("radial-progress-circle");
  const timeCurrent = document.getElementById("time-current");
  const timeTotal = document.getElementById("time-total");
  const mainPlayBtn = document.getElementById("btn-main-play");
  const prevBtn = document.getElementById("btn-prev");
  const nextBtn = document.getElementById("btn-next");
  const shuffleBtn = document.getElementById("btn-shuffle");
  const repeatBtn = document.getElementById("btn-repeat");
  const favoriteBtn = document.getElementById("btn-favorite");
  const collapseBtn = document.getElementById("btn-collapse-player");
  const waveformBarsContainer = document.getElementById("waveform-bars");
  const centerNavBtn = document.getElementById("nav-center-action");
  const playerFormatBadge = document.getElementById("player-format-badge");
  const playerFilesizeBadge = document.getElementById("player-filesize-badge");

  // Discover Sections
  const albumsCarousel = document.getElementById("albums-carousel");
  const tracklistContainer = document.getElementById("tracklist-container");
  const heroCard = document.getElementById("hero-card");
  const heroBackdrop = document.getElementById("hero-backdrop");
  const heroTitle = document.getElementById("hero-title");
  const heroArtist = document.getElementById("hero-artist");
  const heroPlayBtn = document.getElementById("hero-play-btn");
  const searchInput = document.getElementById("search-input");
  const clearSearchBtn = document.getElementById("btn-clear-search");
  const trackCountBadge = document.getElementById("track-count-badge");
  const ambientGlow = document.getElementById("ambient-glow");
  const seeAllAlbumsBtn = document.getElementById("see-all-albums");

  // Modals
  const settingsBtn = document.getElementById("btn-settings");
  const settingsModal = document.getElementById("settings-modal");
  const closeSettingsBtn = document.getElementById("btn-close-settings");
  const settingsTrackCount = document.getElementById("settings-track-count");
  const settingsArtStatus = document.getElementById("settings-art-status");

  const notifBtn = document.getElementById("btn-notifications");
  const activityModal = document.getElementById("activity-modal");
  const closeActivityBtn = document.getElementById("btn-close-activity");
  const modalStatTracks = document.getElementById("modal-stat-tracks");
  const modalStatAlbums = document.getElementById("modal-stat-albums");
  const modalStatFavs = document.getElementById("modal-stat-favs");

  // Filter Chips
  const filterBtn = document.getElementById("btn-filter");
  const filterChipsContainer = document.getElementById("filter-chips");
  const chips = document.querySelectorAll(".chip");

  // 4. Generate 32-bar Equalizer Waveform
  const NUM_BARS = 32;
  const waveformBars = [];
  waveformBarsContainer.innerHTML = "";
  for (let i = 0; i < NUM_BARS; i++) {
    const bar = document.createElement("div");
    bar.className = "waveform-bar";
    const height = Math.floor(Math.sin((i / NUM_BARS) * Math.PI) * 28 + Math.random() * 10 + 6);
    bar.style.height = `${Math.max(6, height)}px`;
    waveformBarsContainer.appendChild(bar);
    waveformBars.push(bar);
  }

  // Waveform scrubbing
  waveformBarsContainer.addEventListener("click", (e) => {
    if (!audio.duration) return;
    const rect = waveformBarsContainer.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const pct = Math.max(0, Math.min(1, clickX / rect.width));
    audio.currentTime = pct * audio.duration;
    triggerHaptic("light");
  });

  // 5. Load Library from Backend
  async function fetchLibrary() {
    try {
      const headers = {};
      if (tg?.initData) {
        headers["X-Telegram-Init-Data"] = tg.initData;
      }

      const res = await fetch("/api/library", { headers });
      if (res.status === 403) {
        showUnauthorizedScreen();
        return;
      }
      const data = await res.json();
      allTracks = data.tracks || [];
      currentPlaylist = [...allTracks];

      renderAlbums(data.albums || []);
      renderTracklist(allTracks);

      if (allTracks.length > 0) {
        setupHero(allTracks[0]);
      }

      // Update modal stats
      if (modalStatTracks) modalStatTracks.textContent = allTracks.length;
      if (modalStatAlbums) modalStatAlbums.textContent = (data.albums || []).length;
      if (modalStatFavs) modalStatFavs.textContent = favorites.size;
      if (settingsTrackCount) settingsTrackCount.textContent = `${allTracks.length} Lossless Tracks`;
      if (settingsArtStatus) settingsArtStatus.textContent = `${allTracks.length} Album Covers Online`;
    } catch (err) {
      console.error("Failed to load library:", err);
      tracklistContainer.innerHTML = `<div class="tracklist-placeholder">⚠️ Could not load library. Please refresh.</div>`;
    }
  }

  function showUnauthorizedScreen() {
    discoverView.innerHTML = `
      <div style="display:flex; flex-direction:column; align-items:center; justify-content:center; height:80vh; text-align:center; padding:24px;">
        <div style="width:72px; height:72px; border-radius:50%; background:rgba(255,75,114,0.15); display:flex; align-items:center; justify-content:center; margin-bottom:20px; font-size:32px;">🔒</div>
        <h2 style="font-size:22px; font-weight:800; margin-bottom:8px;">Private Music Cloud</h2>
        <p style="color:var(--text-secondary); max-width:300px; line-height:1.5; margin-bottom:24px;">This music library is private. Please message the bot and request access from the owner.</p>
        <button onclick="window.Telegram?.WebApp?.close()" style="background:var(--accent-gradient); color:#fff; border:none; padding:12px 28px; border-radius:24px; font-weight:700; cursor:pointer; font-family:var(--font-family);">Return to Chat</button>
      </div>
    `;
  }

  // 6. Render Functions with Real Album Art
  function setupHero(track) {
    heroTitle.textContent = track.title;
    heroArtist.textContent = track.artist ? `Song by ${track.artist}` : "Lossless Audio";
    if (heroBackdrop && track.artwork_url) {
      heroBackdrop.style.backgroundImage = `url('${track.artwork_url}')`;
    }

    heroCard.onclick = () => {
      triggerHaptic("impact");
      const idx = currentPlaylist.findIndex(t => t.id === track.id);
      playTrack(idx !== -1 ? idx : 0);
      openFullPlayer();
    };

    heroPlayBtn.onclick = (e) => {
      e.stopPropagation();
      triggerHaptic("impact");
      const idx = currentPlaylist.findIndex(t => t.id === track.id);
      playTrack(idx !== -1 ? idx : 0);
      openFullPlayer();
    };
  }

  function renderAlbums(albums) {
    if (!albums || albums.length === 0) {
      albumsCarousel.innerHTML = `<div class="carousel-placeholder">No albums found</div>`;
      return;
    }

    albumsCarousel.innerHTML = "";
    albums.forEach(album => {
      const card = document.createElement("div");
      card.className = "album-card";
      const artUrl = album.artwork_url || "/static/default_cover.svg";

      card.innerHTML = `
        <div class="album-cover">
          <img class="album-cover-img" src="${artUrl}" alt="${escapeHtml(album.name)}" loading="lazy" onerror="this.onerror=null;this.src='/static/default_cover.svg';">
        </div>
        <div class="album-name" title="${escapeHtml(album.name)}">${escapeHtml(album.name)}</div>
        <div class="album-artist" title="${escapeHtml(album.artist || "Various Artists")}">${escapeHtml(album.artist || "Various Artists")}</div>
      `;

      card.addEventListener("click", () => {
        triggerHaptic("light");
        filterByAlbum(album.name);
      });
      albumsCarousel.appendChild(card);
    });
  }

  function renderTracklist(tracks) {
    trackCountBadge.textContent = `${tracks.length} Track${tracks.length === 1 ? '' : 's'}`;
    if (!tracks || tracks.length === 0) {
      tracklistContainer.innerHTML = `<div class="tracklist-placeholder">No songs match your selection</div>`;
      return;
    }

    tracklistContainer.innerHTML = "";
    tracks.forEach((track, idx) => {
      const row = document.createElement("div");
      row.className = "track-item";
      if (currentIndex >= 0 && currentPlaylist[currentIndex]?.id === track.id) {
        row.classList.add("playing");
      }

      const artUrl = track.artwork_url || "/static/default_cover.svg";

      row.innerHTML = `
        <div class="track-thumb">
          <img class="track-thumb-img" src="${artUrl}" alt="${escapeHtml(track.title)}" loading="lazy" onerror="this.onerror=null;this.src='/static/default_cover.svg';">
        </div>
        <div class="track-item-info">
          <div class="track-item-title">${escapeHtml(track.title)}</div>
          <div class="track-item-subtitle">${escapeHtml(track.artist)} • ${escapeHtml(track.album)}</div>
        </div>
        <div class="track-item-right">
          <span class="track-duration">${track.duration_str || "0:00"}</span>
        </div>
      `;

      row.addEventListener("click", () => {
        triggerHaptic("impact");
        currentPlaylist = tracks;
        playTrack(idx);
        openFullPlayer();
      });

      tracklistContainer.appendChild(row);
    });
  }

  function filterByAlbum(albumName) {
    const matches = allTracks.filter(t => t.album.toLowerCase() === albumName.toLowerCase());
    if (matches.length > 0) {
      currentPlaylist = matches;
      renderTracklist(matches);
      searchInput.value = albumName;
      clearSearchBtn.style.display = "block";
    }
  }

  // 7. Audio Engine & Controls
  function playTrack(index) {
    if (index < 0 || index >= currentPlaylist.length) return;
    currentIndex = index;
    const track = currentPlaylist[currentIndex];

    audio.src = track.stream_url;
    audio.play().then(() => {
      isPlaying = true;
      updatePlayState();
    }).catch(err => {
      console.warn("Autoplay deferred:", err);
      isPlaying = false;
      updatePlayState();
    });

    updateTrackUI(track);
  }

  function togglePlay() {
    triggerHaptic("impact");
    if (!audio.src) {
      if (currentPlaylist.length > 0) playTrack(0);
      return;
    }
    if (audio.paused) {
      audio.play().then(() => {
        isPlaying = true;
        updatePlayState();
      }).catch(err => console.warn(err));
    } else {
      audio.pause();
      isPlaying = false;
      updatePlayState();
    }
  }

  function playNext() {
    triggerHaptic("light");
    if (currentPlaylist.length === 0) return;
    if (isShuffle) {
      const rand = Math.floor(Math.random() * currentPlaylist.length);
      playTrack(rand);
    } else {
      let next = currentIndex + 1;
      if (next >= currentPlaylist.length) next = 0;
      playTrack(next);
    }
  }

  function playPrev() {
    triggerHaptic("light");
    if (audio.currentTime > 3) {
      audio.currentTime = 0;
      return;
    }
    let prev = currentIndex - 1;
    if (prev < 0) prev = currentPlaylist.length - 1;
    playTrack(prev);
  }

  function updatePlayState() {
    const playIcons = document.querySelectorAll(".play-icon");
    const pauseIcons = document.querySelectorAll(".pause-icon");

    if (isPlaying) {
      playIcons.forEach(el => el.style.display = "none");
      pauseIcons.forEach(el => el.style.display = "block");
      vinylDisc.classList.add("playing");
      if (centerNavBtn) centerNavBtn.classList.add("playing");
    } else {
      playIcons.forEach(el => el.style.display = "block");
      pauseIcons.forEach(el => el.style.display = "none");
      vinylDisc.classList.remove("playing");
      if (centerNavBtn) centerNavBtn.classList.remove("playing");
    }

    // Highlight playing track in list
    const items = tracklistContainer.querySelectorAll(".track-item");
    items.forEach((item, idx) => {
      if (idx === currentIndex) item.classList.add("playing");
      else item.classList.remove("playing");
    });
  }

  function updateTrackUI(track) {
    miniPlayer.style.display = "block";
    miniTitle.textContent = track.title;
    miniArtist.textContent = track.artist;
    if (miniThumbImg) {
      miniThumbImg.src = track.artwork_url || "/static/default_cover.svg";
      miniThumbImg.onerror = () => { miniThumbImg.src = "/static/default_cover.svg"; };
    }

    playerTitle.textContent = track.title;
    playerArtist.textContent = track.artist;
    playerContext.textContent = track.album || "Now Playing";

    if (playerFormatBadge) {
      playerFormatBadge.textContent = track.audio_format ? `${track.audio_format} LOSSLESS` : "LOSSLESS FLAC";
    }
    if (playerFilesizeBadge) {
      playerFilesizeBadge.textContent = track.file_size_str || "High Fidelity";
    }

    if (vinylArtworkImg) {
      vinylArtworkImg.src = track.artwork_url || "/static/default_cover.svg";
      vinylArtworkImg.onerror = () => { vinylArtworkImg.src = "/static/default_cover.svg"; };
    }

    // Dynamic ambient background glow matching track
    const p1 = track.palette?.primary || "#FF4B72";
    const p2 = track.palette?.secondary || "#FD3A69";
    if (ambientGlow) {
      ambientGlow.style.background = `radial-gradient(circle, ${p1}44 0%, ${p2}22 45%, transparent 70%)`;
    }

    // Favorite heart state
    if (favorites.has(track.id)) {
      favoriteBtn.classList.add("liked");
    } else {
      favoriteBtn.classList.remove("liked");
    }

    // MediaSession lock screen integration
    if ("mediaSession" in navigator) {
      navigator.mediaSession.metadata = new MediaMetadata({
        title: track.title,
        artist: track.artist,
        album: track.album,
        artwork: track.artwork_url ? [{ src: track.artwork_url, sizes: "512x512", type: "image/jpeg" }] : [],
      });
      navigator.mediaSession.setActionHandler("play", togglePlay);
      navigator.mediaSession.setActionHandler("pause", togglePlay);
      navigator.mediaSession.setActionHandler("previoustrack", playPrev);
      navigator.mediaSession.setActionHandler("nexttrack", playNext);
    }
  }

  // 8. Time & Progress Updates
  audio.addEventListener("timeupdate", () => {
    if (!audio.duration) return;
    const cur = audio.currentTime;
    const dur = audio.duration;
    const pct = cur / dur;

    // Timeline labels
    timeCurrent.textContent = formatTime(cur);
    timeTotal.textContent = formatTime(dur);

    // Mini player progress fill
    if (miniProgressFill) miniProgressFill.style.width = `${pct * 100}%`;

    // Radial Progress Arc (circumference = 829)
    const circumference = 829;
    const offset = circumference - (pct * circumference);
    radialProgressCircle.style.strokeDashoffset = offset;

    // Waveform bars passed color
    const passedBars = Math.floor(pct * NUM_BARS);
    waveformBars.forEach((bar, idx) => {
      if (idx <= passedBars) {
        bar.classList.add("passed");
      } else {
        bar.classList.remove("passed");
      }
    });
  });

  audio.addEventListener("ended", () => {
    if (repeatMode === 2) {
      audio.currentTime = 0;
      audio.play();
    } else if (repeatMode === 1 || currentIndex < currentPlaylist.length - 1) {
      playNext();
    } else {
      isPlaying = false;
      updatePlayState();
    }
  });

  function formatTime(sec) {
    if (isNaN(sec)) return "00:00";
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  }

  // 9. Event Listeners
  mainPlayBtn.addEventListener("click", togglePlay);
  miniPlayBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    togglePlay();
  });
  prevBtn.addEventListener("click", playPrev);
  nextBtn.addEventListener("click", playNext);

  // Mini player bar tap -> Open Full Player
  miniPlayerBar.addEventListener("click", () => {
    triggerHaptic("light");
    openFullPlayer();
  });

  // Center Nav Button -> Toggle/Open Full Player
  centerNavBtn.addEventListener("click", () => {
    triggerHaptic("impact");
    if (nowPlayingOverlay.classList.contains("open")) {
      closeFullPlayer();
    } else {
      if (currentIndex === -1 && currentPlaylist.length > 0) {
        playTrack(0);
      }
      openFullPlayer();
    }
  });

  collapseBtn.addEventListener("click", () => {
    triggerHaptic("light");
    closeFullPlayer();
  });

  function openFullPlayer() {
    nowPlayingOverlay.classList.add("open");
  }

  function closeFullPlayer() {
    nowPlayingOverlay.classList.remove("open");
  }

  // Shuffle toggle
  shuffleBtn.addEventListener("click", () => {
    triggerHaptic("light");
    isShuffle = !isShuffle;
    shuffleBtn.classList.toggle("active", isShuffle);
  });

  // Repeat toggle (0 -> 1 -> 2 -> 0)
  repeatBtn.addEventListener("click", () => {
    triggerHaptic("light");
    repeatMode = (repeatMode + 1) % 3;
    repeatBtn.classList.toggle("active", repeatMode !== 0);
  });

  // Favorite toggle
  favoriteBtn.addEventListener("click", () => {
    triggerHaptic("success");
    if (currentIndex === -1) return;
    const track = currentPlaylist[currentIndex];
    if (favorites.has(track.id)) {
      favorites.delete(track.id);
      favoriteBtn.classList.remove("liked");
    } else {
      favorites.add(track.id);
      favoriteBtn.classList.add("liked");
    }
    localStorage.setItem("tpmc_favorites", JSON.stringify([...favorites]));
    if (modalStatFavs) modalStatFavs.textContent = favorites.size;
  });

  // Search input live filtering
  searchInput.addEventListener("input", (e) => {
    const q = e.target.value.toLowerCase().trim();
    if (q) {
      clearSearchBtn.style.display = "block";
      const filtered = allTracks.filter(t =>
        t.title.toLowerCase().includes(q) ||
        t.artist.toLowerCase().includes(q) ||
        t.album.toLowerCase().includes(q) ||
        t.genre.toLowerCase().includes(q)
      );
      renderTracklist(filtered);
    } else {
      clearSearchBtn.style.display = "none";
      renderTracklist(allTracks);
    }
  });

  clearSearchBtn.addEventListener("click", () => {
    searchInput.value = "";
    clearSearchBtn.style.display = "none";
    renderTracklist(allTracks);
  });

  // Filter Chips Logic
  filterBtn?.addEventListener("click", () => {
    triggerHaptic("light");
    if (filterChipsContainer) {
      filterChipsContainer.style.display = filterChipsContainer.style.display === "none" ? "flex" : "none";
    }
  });

  chips.forEach(chip => {
    chip.addEventListener("click", () => {
      triggerHaptic("light");
      chips.forEach(c => c.classList.remove("active"));
      chip.classList.add("active");
      const f = chip.dataset.filter;

      if (f === "all") {
        currentPlaylist = [...allTracks];
        renderTracklist(allTracks);
      } else if (f === "lossless") {
        const lossless = allTracks.filter(t => t.audio_format === "FLAC" || t.mime_type?.includes("flac"));
        currentPlaylist = lossless;
        renderTracklist(lossless);
      } else if (f === "favorites") {
        const favs = allTracks.filter(t => favorites.has(t.id));
        currentPlaylist = favs;
        renderTracklist(favs);
      } else if (f === "artists") {
        const sorted = [...allTracks].sort((a, b) => a.artist.localeCompare(b.artist));
        currentPlaylist = sorted;
        renderTracklist(sorted);
      }
    });
  });

  // "See All" button on albums
  seeAllAlbumsBtn?.addEventListener("click", () => {
    triggerHaptic("light");
    const albumsTab = document.querySelector('.nav-item[data-tab="albums"]');
    albumsTab?.click();
  });

  // Settings Modal Handlers
  settingsBtn?.addEventListener("click", () => {
    triggerHaptic("light");
    if (settingsModal) settingsModal.style.display = "flex";
  });
  closeSettingsBtn?.addEventListener("click", () => {
    if (settingsModal) settingsModal.style.display = "none";
  });
  settingsModal?.addEventListener("click", (e) => {
    if (e.target === settingsModal) settingsModal.style.display = "none";
  });

  // Activity Modal Handlers
  notifBtn?.addEventListener("click", () => {
    triggerHaptic("light");
    if (activityModal) activityModal.style.display = "flex";
  });
  closeActivityBtn?.addEventListener("click", () => {
    if (activityModal) activityModal.style.display = "none";
  });
  activityModal?.addEventListener("click", (e) => {
    if (e.target === activityModal) activityModal.style.display = "none";
  });

  // Bottom Navigation Tabs
  const navItems = document.querySelectorAll(".nav-item");
  navItems.forEach(item => {
    item.addEventListener("click", () => {
      triggerHaptic("light");
      navItems.forEach(n => n.classList.remove("active"));
      item.classList.add("active");
      const tab = item.dataset.tab;

      if (tab === "discover") {
        currentPlaylist = [...allTracks];
        renderTracklist(allTracks);
      } else if (tab === "favorites") {
        const favTracks = allTracks.filter(t => favorites.has(t.id));
        currentPlaylist = favTracks;
        renderTracklist(favTracks);
      } else if (tab === "artists") {
        const sorted = [...allTracks].sort((a, b) => a.artist.localeCompare(b.artist));
        currentPlaylist = sorted;
        renderTracklist(sorted);
      } else if (tab === "albums") {
        const sorted = [...allTracks].sort((a, b) => a.album.localeCompare(b.album));
        currentPlaylist = sorted;
        renderTracklist(sorted);
      }
    });
  });

  // Initial fetch
  fetchLibrary();
});
