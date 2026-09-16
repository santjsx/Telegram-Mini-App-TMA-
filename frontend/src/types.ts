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

export type ActiveTab = 'all' | 'favorites' | 'recent' | 'albums' | 'artists';
