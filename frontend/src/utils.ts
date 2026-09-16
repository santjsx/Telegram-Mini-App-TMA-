export function formatTime(seconds: number): string {
  if (isNaN(seconds) || seconds < 0 || seconds === Infinity) return '0:00';
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

export function formatFileSize(bytes: number): string {
  if (!bytes || bytes <= 0) return '0 MB';
  const mb = bytes / (1024 * 1024);
  return `${mb.toFixed(1)} MB`;
}

export function getTelegramInitData(): string {
  try {
    return (
      (window as any).Telegram?.WebApp?.initData ||
      new URLSearchParams(window.location.search).get('initData') ||
      ''
    );
  } catch {
    return '';
  }
}
