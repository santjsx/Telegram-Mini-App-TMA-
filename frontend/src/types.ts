export interface Track {
  id: number;
  title: string;
  artist: string;
  album: string;
  genre: string;
  duration: number;
  duration_str: string;
  is_favorite: boolean;
  mime_type: string;
  audio_format: string;
  file_size: number;
  file_size_str: string;
  artwork_url: string;
  stream_url: string;
  palette: {
    primary: string;
    secondary: string;
  };
}

export interface Album {
  name: string;
  artist: string;
  track_count: number;
  artwork_url: string;
  palette: {
    primary: string;
    secondary: string;
  };
}

export interface Artist {
  name: string;
  track_count: number;
  palette: {
    primary: string;
    secondary: string;
  };
}

export interface LibraryData {
  total_tracks: number;
  tracks: Track[];
  albums: Album[];
  artists: Artist[];
  authenticated_user_id?: number | null;
}

export type RepeatMode = 'off' | 'all' | 'one';

export type ActiveTab = 'all' | 'favorites' | 'recent' | 'playlists' | 'albums' | 'artists';

export type SortOption = 'default' | 'title_asc' | 'title_desc' | 'artist_asc' | 'duration_desc' | 'recent';

export type FilterOption = 'all' | 'flac' | 'mp3' | 'm4a';

export interface Playlist {
  id: string;
  name: string;
  description?: string;
  coverGradient: [string, string];
  trackIds: number[];
  createdAt: number;
  updatedAt: number;
}

export interface ArtistDetail {
  name: string;
  tracks: Track[];
  albums: string[];
  track_count: number;
  palette: { primary: string; secondary: string };
}

export interface AlbumDetail {
  name: string;
  artist: string;
  tracks: Track[];
  track_count: number;
  artwork_url: string;
  duration: number;
  palette: { primary: string; secondary: string };
}
