export const INTRO_DURATION = 2500;
export type IntroPhase = 'black' | 'reveal' | 'hold' | 'reverse' | 'settle' | 'done';
const clamp = (n: number) => Math.max(0, Math.min(1, n));
export function introFrame(elapsed: number) {
  const phase: IntroPhase = elapsed < 100 ? 'black' : elapsed < 900 ? 'reveal' : elapsed < 1100 ? 'hold' : elapsed < 1800 ? 'reverse' : elapsed < INTRO_DURATION ? 'settle' : 'done';
  const settle = clamp((elapsed - 1800) / 700);
  const eased = 1 - Math.pow(1 - settle, 3);
  return { phase, reveal: clamp((elapsed - 100) / 800), reverse: clamp((elapsed - 1100) / 700), settle: eased, angle: -28 + 16 * eased, scale: 1.85 - .85 * eased };
}
/** Half-plane x+y<=2p (reveal), or x+y>=2(1-p) (reverse). */
export function diagonalClip(progress: number, reverse = false): string {
  const p = clamp(progress);
  const s = 2 * (reverse ? 1 - p : p);
  const point = (x: number, y: number) => `${x * 100}% ${y * 100}%`;
  const points = reverse
    ? s >= 1 ? [[s - 1, 1], [1, s - 1], [1, 1]] : [[s, 0], [1, 0], [1, 1], [0, 1], [0, s]]
    : s <= 1 ? [[0, 0], [s, 0], [0, s]] : [[0, 0], [1, 0], [1, s - 1], [s - 1, 1], [0, 1]];
  return `polygon(${points.map(([x, y]) => point(x, y)).join(', ')})`;
}
