import type { ReactNode } from 'react';
import { useLanguage } from './LanguageProvider';
import { cfX, cfY, CF_HI, CF_LO, CF_TOP, connCf, PLOT } from './scrollStudies';

/** Static studies: these coordinates never describe the archived vessel. */
const pt = (x: number, y: number) => `${Math.round(x * 100) / 100} ${Math.round(y * 100) / 100}`;

export function ShellField() {
  return <div className="ff-field ff-field--shell" aria-hidden="true">
   <svg className="ff-field-draw" viewBox="0 0 1440 960" preserveAspectRatio="xMidYMin slice" focusable="false">
    <path className="ff-paper-rule" d="M24 0v960M1416 0v960M0 108h1440M0 828h1440M1080 0v960"/>
    <circle className="ff-paper-arc" cx="1180" cy="330" r="570"/><circle className="ff-paper-arc" cx="1180" cy="330" r="740"/>
    <path className="ff-paper-rule" d={Array.from({length:41},(_,i)=>`M24 ${i*24}h${i%4===0?8:4}`).join('')}/>
   </svg>
  </div>;
}

/* ---- Work: the compass study ----------------------------------------------- */

/**
 * Eccentric focal point, above the page and right of centre, with a radius wider
 * than the page. The rings are cropped by the viewport, so what shows is the
 * lower arc crossing the exposed margin below the work rows and continuing into
 * the navigation's column — never a closed arc hidden behind the exhibit.
 */
const FOCAL = { x: 1180, y: -60 };
const RADII = [800, 660, 520];
const MAIN_R = RADII[0];
/** The broad draft: same centre, further out, barely there. */
const DRAFT = [980, 1160];
/** The datum the main ring crosses, inside the exposed lower margin. */
const DATUM = 720;
const MEET = { x: FOCAL.x - Math.sqrt(MAIN_R ** 2 - (DATUM - FOCAL.y) ** 2), y: DATUM };
/** Radius to the meeting point, and the tangent there: perpendicular to it. */
const MEET_DY = MEET.y - FOCAL.y;
const MEET_DX = MEET.x - FOCAL.x;
const tangent = (reach: number) => [
  `M${pt(MEET.x - reach * MEET_DY / MAIN_R, MEET.y + reach * MEET_DX / MAIN_R)}`,
  `L${pt(MEET.x + reach * MEET_DY / MAIN_R, MEET.y - reach * MEET_DX / MAIN_R)}`,
].join('');
const arcTicks = Array.from({ length: 61 }, (_, i) => {
  const a = (12 + i * 3) * Math.PI / 180, r = MAIN_R - (i % 5 === 0 ? 14 : 6);
  return `M${pt(FOCAL.x + Math.cos(a) * r, FOCAL.y + Math.sin(a) * r)}L${pt(FOCAL.x + Math.cos(a) * MAIN_R, FOCAL.y + Math.sin(a) * MAIN_R)}`;
}).join('');
const datumTicks = Array.from({ length: 73 }, (_, i) => `M${i * 20} ${DATUM + 40}v${i % 5 === 0 ? 11 : 5}`).join('');

function WorkField() {
  return <div className="ff-field ff-field--work" data-ff-study="compass" aria-hidden="true">
   <svg className="ff-field-draw" viewBox="0 0 1440 900" preserveAspectRatio="xMidYMin slice" focusable="false">
    <path className="ff-field-rule" d={`M0 ${DATUM}h1440M0 ${FOCAL.y}h1440M${FOCAL.x} 0v900`} />
    <path className="ff-field-tick" d={datumTicks}/>
    {/* One measured group: the sweep and the drift are written onto the ring, its
        ticks, the tangent and the point they cross together, about the study's
        own focal point, so their relationship to one another holds through the
        whole move. The faint draft arcs and the datum stay where they are: they
        are the fixed reference the ring is read against. Nothing here carries
        text, so nothing can be turned by it. */}
    {DRAFT.map(r => <circle key={r} className="ff-field-arc ff-field-arc--draft" cx={FOCAL.x} cy={FOCAL.y} r={r}/>)}
    <g>
     <g data-ff-motion>
      {RADII.map(r => <circle key={r} className={r === MAIN_R ? 'ff-field-arc ff-field-arc--main' : 'ff-field-arc'} cx={FOCAL.x} cy={FOCAL.y} r={r}/>)}
      <path className="ff-field-tick ff-field-tick--arc" d={arcTicks}/>
      <path className="ff-field-tangent" d={tangent(150)}/>
      <path className="ff-field-cross" d={`M${pt(MEET.x - 9, MEET.y)}h18M${MEET.x} ${MEET.y - 9}v18`}/>
      <circle className="ff-field-point" cx={MEET.x} cy={MEET.y} r="3"/>
     </g>
    </g>
   </svg>
  </div>;
}

function AboutField() {
  return <div className="ff-field ff-field--about" aria-hidden="true">
   <svg className="ff-field-draw" viewBox="0 0 1000 1800" preserveAspectRatio="xMaxYMin meet" focusable="false">
    <path className="ff-field-rule" d="M975 0v1800M0 450h1000M0 950h1000M0 1480h1000"/>
    <circle className="ff-field-arc ff-field-arc--draft" cx="980" cy="220" r="520"/><circle className="ff-field-arc ff-field-arc--draft" cx="980" cy="220" r="760"/>
   </svg>
  </div>;
}

export function PageField({ page }: { page: 'work' | 'about' }) { return page === 'work' ? <WorkField /> : <AboutField />; }

/* ---- typeset mathematics ---------------------------------------------------- */

/** `role="img"` names the formula: a fraction of spans is otherwise read as a
 *  run of unrelated letters. Nothing is rendered by a library.
 *
 *  Two languages are in play on one node, and they are deliberately separated.
 *  The *name* of the formula is prose and follows the reader, so the accessible
 *  node carries the active language and a Chinese visitor hears a Chinese
 *  description of an equation that has not changed. The *formula* is not prose:
 *  it is mathematical notation, identical in both editions, and is marked
 *  `lang="en"` on the spans that hold it so it is typeset and announced as Latin
 *  symbols rather than as Chinese text. */
function MathLine({ label, compact, children }: { label: string; compact?: boolean; children: ReactNode }) {
  const { language } = useLanguage();
  return <p className={compact ? 'ff-math ff-math--compact' : 'ff-math'} role="img" aria-label={label} lang={language}>{children}</p>;
}

/* ---- About: the Lissajous hero --------------------------------------------- */

const FAMILIES = [{ a: 3, b: 2, p: Math.PI / 2 }, { a: 3, b: 2, p: 0 }, { a: 3, b: 2, p: Math.PI / 4 }, { a: 5, b: 4, p: 0 }, { a: 5, b: 4, p: Math.PI / 3 }];
const PLOTS = FAMILIES.map(({ a, b, p }) => Array.from({ length: 481 }, (_, i) => {
  const t = i / 480 * Math.PI * 2;
  return `${i === 0 ? 'M' : 'L'}${pt(160 + 140 * Math.sin(a * t + p), 160 - 140 * Math.sin(b * t))}`;
}).join('') + 'Z');

export function AboutFigure() {
  const { t } = useLanguage();
  return <figure className="ff-about-figure" data-ff-study="harmonic">
   <span className="ff-study-caption">{t('figure.harmonic')}</span>
   <svg className="ff-curve" viewBox="0 0 320 320" aria-hidden="true" focusable="false">
    <path className="ff-curve-ruler" d="M20 20h280v280H20zM160 10v300M10 160h300"/><circle className="ff-curve-ruler" cx="160" cy="160" r="140"/>
    <path className="ff-curve-tick" d={Array.from({length:17},(_,i)=>`M${20+i*17.5} 20v${i%4===0?7:3}M20 ${20+i*17.5}h${i%4===0?7:3}`).join('')}/>
    {PLOTS.slice(1).map((d, i) => <path key={i} className="ff-curve-soft" d={d}/>)}<path className="ff-curve-main" d={PLOTS[0]}/>
    {/* The whole graph stays, faint, through the whole scroll: the trace is an
        added reading of it, never a replacement for it. The trace and its cursor
        are written from that equation rather than from a stored path. */}
    <path className="ff-curve-trace" data-ff-motion="trace" d="" style={{ opacity: 0 }}/>
    <circle className="ff-curve-cursor" data-ff-motion="cursor" cx="160" cy="20" r="3" style={{ opacity: 0 }}/>
    <circle className="ff-field-point" cx="300" cy="160" r="3"/>
   </svg>
   <MathLine compact label={t('math.harmonic1')}>
    <span lang="en"><i>x</i> = sin(<i>at</i> + <i>φ</i>)</span>
    <span lang="en"><i>y</i> = sin(<i>bt</i>)</span>
    <span lang="en">0 ≤ <i>t</i> &lt; 2π</span>
   </MathLine>
   <MathLine compact label={t('math.harmonic2')}>
    <span lang="en">(<i>a</i>, <i>b</i>) = (3, 2) · <i>φ</i> = π/2, 0, π/4</span>
    <span lang="en">(<i>a</i>, <i>b</i>) = (5, 4) · <i>φ</i> = 0, π/3</span>
   </MathLine>
  </figure>;
}

/* ---- About: three naval studies -------------------------------------------- */

function ScaleFigure() {
  const { t } = useLanguage();
  return <figure className="ff-about-study-figure" data-ff-study="scale">
   <span className="ff-study-caption">{t('figure.scale')}</span>
   <svg className="ff-study-draw" viewBox="0 0 340 160" aria-hidden="true" focusable="false">
    <path className="ff-study-guide" d="M20 74h300"/>
    <path className="ff-study-wave" d={Array.from({ length: 25 }, (_, i) => `M${20 + i * 12} 74q6 -7 12 0`).join('')}/>
    <path className="ff-study-body" d="M74 92h192l-26 -12H100z"/>
    {/* The guides are emphasised in turn as the study crosses the viewport. The
        drawing itself never moves and never disappears. */}
    <path className="ff-study-vector ff-study-emphasis" data-ff-emphasis="velocity" d="M46 40h250M296 40l-11 -6M296 40l-11 6"/>
    <path className="ff-study-dimension ff-study-emphasis" data-ff-emphasis="length" d="M74 132h192M74 124v16M266 124v16"/>
    <text className="ff-study-tag" x="300" y="32" textAnchor="end">V</text>
    <text className="ff-study-tag" x="170" y="152" textAnchor="middle">L</text>
   </svg>
   <figcaption>{t('figure.scaleCaption')}</figcaption>
  </figure>;
}

/** Cf as `tools/plimsoll/resistance.py` computes it, evaluated rather than
 *  tabulated, so the plot cannot drift from the formula it claims to show. Both
 *  the curve below and the marker that follows it read the same definition, in
 *  scrollStudies.ts, so the two cannot disagree. */
const DECADES = [{ log: 6, label: '10⁶' }, { log: 7, label: '10⁷' }, { log: 8, label: '10⁸' }, { log: 9, label: '10⁹' }];
const MILLI = [1, 2, 3, 4, 5];
const CF_CURVE = Array.from({ length: 145 }, (_, i) => {
  const logRe = CF_LO + (CF_HI - CF_LO) * i / 144;
  return `${i === 0 ? 'M' : 'L'}${pt(cfX(logRe), cfY(connCf(10 ** logRe)))}`;
}).join('');

function FrictionFigure() {
  const { t } = useLanguage();
  return <figure className="ff-about-study-figure" data-ff-study="friction">
   <span className="ff-study-caption">{t('figure.friction')}</span>
   <svg className="ff-study-draw" viewBox="0 0 340 200" aria-hidden="true" focusable="false">
    <path className="ff-study-guide" d={`M${PLOT.x} ${PLOT.y}h${PLOT.w}v${PLOT.h}h${-PLOT.w}Z`}/>
    {MILLI.map(n => <path key={n} className="ff-study-grid" d={`M${PLOT.x} ${cfY(n / 1000).toFixed(2)}h${PLOT.w}`}/>)}
    <path className="ff-study-curve" d={CF_CURVE}/>
    {/* The marker and its two projections are written onto the axes the curve is
        read against: the coefficient on the left, Re along the bottom. */}
    <path className="ff-study-projection" data-ff-motion="across" d="" style={{ opacity: 0 }}/>
    <path className="ff-study-projection" data-ff-motion="up" d="" style={{ opacity: 0 }}/>
    <circle className="ff-study-marker" data-ff-motion="marker" cx={PLOT.x} cy={PLOT.y + PLOT.h} r="3.2" style={{ opacity: 0 }}/>
    {DECADES.map(({ log }) => <path key={log} className="ff-study-tick" d={`M${cfX(log)} ${PLOT.y}v${PLOT.h}M${cfX(log)} ${PLOT.y + PLOT.h}v6`}/>)}
    {DECADES.map(({ log, label }) => <text key={`x${log}`} className="ff-study-tag" x={cfX(log)} y={PLOT.y + PLOT.h + 18} textAnchor="middle">{label}</text>)}
    {MILLI.map(n => <text key={`y${n}`} className="ff-study-tag" x={PLOT.x - 8} y={cfY(n / 1000) + 3.5} textAnchor="end">{(n / 1000).toFixed(3).slice(1)}</text>)}
    <text className="ff-study-tag ff-study-tag--name" x={PLOT.x + 6} y={PLOT.y + 16}>Cf</text>
    <text className="ff-study-tag ff-study-tag--name" x={PLOT.x + PLOT.w} y={PLOT.y + PLOT.h + 32} textAnchor="end">Re</text>
   </svg>
   <figcaption>{t('figure.frictionCaption')}</figcaption>
  </figure>;
}

function PowerFigure() {
  const { t } = useLanguage();
  return <figure className="ff-about-study-figure" data-ff-study="power">
   <span className="ff-study-caption">{t('figure.power')}</span>
   <svg className="ff-study-draw" viewBox="0 0 340 160" aria-hidden="true" focusable="false">
    <path className="ff-study-guide" d="M24 96h292"/>
    <path className="ff-study-body" d="M118 96V78h104v18"/>
    {/* Velocity first, then the resistance opposing it: the two quantities whose
        product the equation below them states. Both stay on the drawing. */}
    <path className="ff-study-vector ff-study-emphasis" data-ff-emphasis="velocity" d="M60 44h210M270 44l-11 -6M270 44l-11 6"/>
    <path className="ff-study-vector ff-study-vector--back ff-study-emphasis" data-ff-emphasis="resistance" d="M280 128H96M96 128l11 -6M96 128l11 6"/>
    <text className="ff-study-tag" x="282" y="36" textAnchor="end">V</text>
    <text className="ff-study-tag" x="58" y="136" textAnchor="end">R</text>
   </svg>
   <figcaption>{t('figure.powerCaption')}</figcaption>
  </figure>;
}

export function ScaleStudy() {
  const { t } = useLanguage();
  return <section className="ff-about-study" aria-labelledby="ff-about-scale" data-ff-section={t('study.scale.section')}>
   <div className="ff-about-study-text">
    <span className="ff-eyebrow">{t('study.scale.eyebrow')}</span>
    <h2 id="ff-about-scale" tabIndex={-1}>{t('study.scale.title')}</h2>
    <p>{t('study.scale.body')}</p>
    <MathLine label={t('math.scale')}>
     <span className="ff-equation" lang="en">
      <span><i>Fr</i></span><span>=</span>
      <span className="ff-frac"><span className="ff-frac-num"><i>V</i></span><span className="ff-frac-den"><span className="ff-radic"><span className="ff-radic-in"><i>gL</i></span></span></span></span>
     </span>
     <span className="ff-equation" lang="en">
      <span><i>Re</i></span><span>=</span>
      <span className="ff-frac"><span className="ff-frac-num"><i>VL</i></span><span className="ff-frac-den"><i>ν</i></span></span>
     </span>
    </MathLine>
    <ul className="ff-legend">
     <li><i>V</i> {t('study.scale.speed')}</li><li><i>L</i> {t('study.scale.length')}</li><li><i>g</i> {t('study.scale.gravity')}</li><li><i>ν</i> {t('study.scale.viscosity')}</li>
    </ul>
    {/* The book and its authors are named the same way in either language; the
        sentence introducing them is prose and is translated. */}
    <p className="ff-study-note">{t('study.scale.note')}</p>
   </div>
   <ScaleFigure />
  </section>;
}

export function FrictionStudy() {
  const { t } = useLanguage();
  return <section className="ff-about-study ff-about-study--flip" aria-labelledby="ff-about-friction" data-ff-section={t('study.friction.section')}>
   <div className="ff-about-study-text">
    <span className="ff-eyebrow">{t('study.friction.eyebrow')}</span>
    <h2 id="ff-about-friction" tabIndex={-1}>{t('study.friction.title')}</h2>
    <p>{t('study.friction.body')}</p>
    <MathLine label={t('math.friction')}>
     <span className="ff-equation" lang="en">
      <span><i>C</i><sub>f</sub></span><span>=</span>
      <span className="ff-frac"><span className="ff-frac-num">0.4631</span><span className="ff-frac-den">(log<sub>10</sub> <i>Re</i>)<sup>2.6</sup></span></span>
     </span>
    </MathLine>
    <p className="ff-study-note">{t('study.friction.note')}</p>
   </div>
   <FrictionFigure />
  </section>;
}

export function PowerStudy() {
  const { t } = useLanguage();
  return <section className="ff-about-study" aria-labelledby="ff-about-power" data-ff-section={t('study.power.section')}>
   <div className="ff-about-study-text">
    <span className="ff-eyebrow">{t('study.power.eyebrow')}</span>
    <h2 id="ff-about-power" tabIndex={-1}>{t('study.power.title')}</h2>
    <p>{t('study.power.body')}</p>
    <MathLine label={t('math.power')}>
     <span className="ff-equation" lang="en">
      <span><i>P</i><sub>E</sub></span><span>=</span>
      <span><i>R</i><sub>T</sub> · <i>V</i></span>
     </span>
     <span className="ff-equation" lang="en">
      <span><i>R</i><sub>T</sub></span><span>=</span>
      <span><i>R</i><sub>f</sub> + <i>R</i><sub>r</sub></span>
     </span>
    </MathLine>
    <ul className="ff-legend">
     <li><i>R</i><sub>T</sub> {t('study.power.total')}</li><li><i>R</i><sub>f</sub> {t('study.power.friction')}</li><li><i>R</i><sub>r</sub> {t('study.power.residual')}</li><li><i>V</i> {t('study.power.speed')}</li>
    </ul>
    <p className="ff-study-note">{t('study.power.note')}</p>
   </div>
   <PowerFigure />
  </section>;
}
