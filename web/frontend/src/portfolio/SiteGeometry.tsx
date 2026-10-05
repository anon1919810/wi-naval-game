/** Decorative construction marks; no measurements, interaction or animation. */
export function SiteGeometry({ variant = 'section' }: { variant?: 'section' | 'rule' | 'margin' }) {
  if (variant === 'rule') return <svg className="ff-site-geometry ff-site-geometry--rule" viewBox="0 0 120 20" aria-hidden="true" focusable="false">
    <path d="M1 19V1h118 M8 1v7 M16 1v4 M24 1v7 M32 1v4 M96 1v7 M104 1v4 M112 1v7" />
  </svg>;
  if (variant === 'margin') return <svg className="ff-site-geometry ff-site-geometry--margin" viewBox="0 0 220 270" aria-hidden="true" focusable="false">
    <path d="M8 250 200 210 M50 262V34h148 M4 146h212" />
    <circle cx="128" cy="146" r="72" /><path d="M118 146h20 M128 136v20 M50 54h8 M50 66h4 M50 78h8" />
  </svg>;
  return <svg className="ff-site-geometry ff-site-geometry--section" viewBox="0 0 100 36" aria-hidden="true" focusable="false">
    <path d="M1 29h98 M64 1v34 M8 29v-5 M18 29v-3 M28 29v-5 M38 29v-3 M48 29v-5 M54 14h20" />
    <circle cx="64" cy="14" r="10" /><path d="M3 21 96 1" />
  </svg>;
}
