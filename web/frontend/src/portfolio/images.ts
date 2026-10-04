export const IMAGE_TIMEOUT = 8000;
export type ImageCache = Map<string, Promise<void>>;

/** The cache belongs to a mounted portfolio; failed requests can be retried. */
export function readyImage(href: string, cache: ImageCache): Promise<void> {
  const existing = cache.get(href);
  if (existing) return existing;
  const pending = new Promise<void>((resolve, reject) => {
    const image = new Image();
    let ended = false;
    const end = (error?: Error) => {
      if (ended) return;
      ended = true;
      clearTimeout(timer);
      image.onload = image.onerror = null;
      if (error) reject(error); else resolve();
    };
    const timer = setTimeout(() => end(new Error('Image loading timed out')), IMAGE_TIMEOUT);
    image.onerror = () => end(new Error('Image could not be loaded'));
    image.onload = () => { if (!image.decode) end(); };
    image.src = href;
    if (image.decode) {
      image.decode().then(() => end(), () => end(new Error('Image could not be decoded')));
    } else if (image.complete && image.naturalWidth > 0) end();
  });
  cache.set(href, pending);
  void pending.catch(() => { if (cache.get(href) === pending) cache.delete(href); });
  return pending;
}
