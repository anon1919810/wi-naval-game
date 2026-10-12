/**
 * The public shell's bilingual interface.
 *
 * Two languages, one flat dictionary each, and nothing between them: no
 * framework, no runtime lookup, no DOM rewriting. Every string a visitor can
 * read on a public page lives here, in the same order, under the same keys — so
 * a missing translation is a type error rather than a blank line, and a renamed
 * key is caught by the build instead of by a reader.
 *
 * Four rules the copy itself follows:
 *
 * - **English is the source.** The `en` dictionary is the literal one the shell
 *   already printed, character for character, so the English site is unchanged
 *   in meaning and in wording wherever it has nothing better to say.
 * - **Names stay names.** `Y's Formfield`, `Plimsoll`, `Space Grotesk`,
 *   `Molland, Turnock & Hudson`, `SPS`, `Taylor-Gertler` and every equation,
 *   symbol and citation are left exactly as they were. What is translated is the
 *   prose around them, never the thing being named.
 * - **No claim is added or softened.** A Chinese row says what the English row
 *   says — the same limits, the same "not a certified design tool", the same
 *   distinction between what is known, what is estimated and what is unknown.
 * - **Names are never translated.** `Yang Duanming` is a person's confirmed
 *   public name and stays `Yang Duanming` in both languages; no other spelling
 *   of it is invented for the Chinese edition. Wherever a deliberately English
 *   span survives inside a Chinese sentence — a folio, a product name, a
 *   citation, a formula — it is marked `lang="en"` at the point of use, so a
 *   screen reader pronounces it as what it is instead of reading Latin letters
 *   with Mandarin phonetics.
 *
 * Keys are dotted and flat on purpose: `t('about.built.noApi.text')` is greppable
 * from the component that uses it and type-checked against the English
 * dictionary, which is what keeps the two files from drifting apart.
 */

/** The two interfaces this shell speaks. */
export type SiteLanguage = 'zh-CN' | 'en';

/**
 * The stored preference's key.
 *
 * Versioned and local to this shell, like `formfield-theme`: a later change to
 * the accepted values can then leave an old preference behind harmlessly
 * instead of being read as one of them.
 */
export const LANGUAGE_KEY = 'formfield-language-v1';

/** One interpolation slot. `{id}` in a message becomes the sheet's own number. */
export type CopyParams = Readonly<Record<string, string | number>>;

/* ------------------------------------------------------------------------- */
/* English — the source dictionary                                            */
/* ------------------------------------------------------------------------- */

const EN = {
  /* ---- document -------------------------------------------------------- */
  'doc.title.home': 'Y’s Formfield — Tools & Experiments',
  'doc.title.project': 'Plimsoll — Y’s Formfield',
  'doc.title.credits': 'Credits — Y’s Formfield',

  /* ---- header ---------------------------------------------------------- */
  'header.home': 'Y’s Formfield home',
  'header.languageGroup': 'Language',
  'header.languageZh': '中文',
  'header.languageZhTitle': 'Chinese interface',
  'header.languageEn': 'EN',
  'header.languageEnTitle': 'English interface',
  'header.themeDark': 'Switch to dark theme',
  'header.themeLight': 'Switch to light theme',
  'header.replay': 'Replay intro',
  'header.sound': 'Sound',
  'header.soundOn': 'Turn sound on',
  'header.soundOff': 'Mute sound',

  /* ---- footer ---------------------------------------------------------- */
  'footer.tagline': 'PRECISE. MODERN. INTERACTIVE.',

  /* ---- the rail and the reading ruler ---------------------------------- */
  'nav.label': 'Main navigation',
  'nav.work': 'Work',
  'nav.about': 'About',
  'nav.credits': 'Credits',
  'ruler.label': 'Reading position',
  'ruler.reading': 'READING',

  /* ---- Work: the exhibit ----------------------------------------------- */
  'work.label': 'Selected work',
  'work.exhibitHead': 'SELECTED WORK',
  /* The folio is an intentionally English span: a volume mark, not prose. It is
     rendered inside `<span lang="en">` so it is announced as Latin. */
  'work.exhibitMeta': 'TOOLS & EXPERIMENTS',
  'work.exhibitFolio': 'VOL. 01',
  'work.lede': 'Naval design, made explorable.',
  'work.openTool': 'Open Plimsoll',
  'work.viewProject': 'VIEW PROJECT',
  'work.drawingIdle': 'Interactive top-view drawing. Use arrow keys to explore, Home to reset.',
  'work.drawingInspect': 'Interactive top-view drawing. Inspection on: arrow keys move the 2× lens over the same rendered scan, Home resets the lens, Escape leaves inspection.',
  'work.inspectOn': 'Inspect On',
  'work.inspectOff': 'Inspect Off',
  'work.inspectIdleTitle': 'Inspect drawing · 2×',
  'work.inspectActiveTitle': 'Leave inspection',
  'work.reset': 'Reset view',
  'work.sheetGroup': 'Reference drawing',
  'work.sheetLabel': 'Reference sheet {id}',
  'work.sheetTitle': 'View drawing {id}',
  'work.boardCaption': 'DRAWING {id} / 03',
  'work.sheetError': 'Reference {id} could not be loaded, so {kept} stays on the exhibit. ',
  'work.sheetErrorRetry': 'RETRY {id}',
  'work.sheetErrorRest': ' or choose another reference.',
  'work.imageError': 'The reference could not be loaded. Choose another reference or use Replay Intro to retry.',
  'work.loadingStatus': 'Loading reference',
  'work.preparing': 'PREPARING THE DRAWING',
  'work.skipIntro': 'SKIP INTRO',
  'splash.status': 'Opening Y’s Formfield',

  /* ---- About ------------------------------------------------------------ */
  'about.label': 'About Y’s Formfield',
  'about.eyebrow': 'ABOUT THE COLLECTION',
  'about.titleLead': 'A field for',
  'about.titleTail': 'useful ideas.',
  'about.intro': 'Yang Duanming’s collection of tools and experiments: naval design work you can open and run, with the drawings it came from.',
  'about.sectionCollection': 'Collection',
  'about.sectionPerson': 'Person',
  'about.sectionPlimsoll': 'Plimsoll',
  'about.sectionBuilt': 'Technology stack',
  'about.authorTitle': 'The person behind it',
  'about.authorP1': 'My name is Yang Duanming. I build tools and explore interface design.',
  'about.authorP2': 'Working software, and the drawings it came from. Plimsoll is the first featured project.',
  'about.workLabel': 'FIRST WORK / 01',
  'about.workTitle': 'Plimsoll',
  'about.workText': 'Plimsoll covers ship loading, hydrostatics, stability and resistance, with a damage laboratory that connects simplified module and crew effects to flooding and remaining stability. The browser and CLI share one Python core and export results as JSON or CSV.',
  'about.viewProject': 'VIEW THE PROJECT',
  'about.builtTitle': 'Technology stack',
  'about.built.react.label': 'React · TypeScript · Vite',
  'about.built.react.text': 'The public shell and the workspace interface: one hash router, the exhibit, this page, the work detail and every form in the tool.',
  'about.built.svg.label': 'SVG and CSS',
  'about.built.svg.text': 'Framing, construction lines, the inspection lens and page transitions. The exhibit’s surrounding geometry is decorative, not measured engineering data.',
  'about.built.fonts.label': 'Space Grotesk · Inter',
  'about.built.fonts.text': 'Self-hosted variable fonts, Latin subset, SIL OFL 1.1. Space Grotesk for headings, Inter for body text.',
  'about.built.noApi.label': 'Public pages and workspace',
  'about.built.noApi.text': 'These public pages never call the Plimsoll service and never create a workspace. Open Plimsoll is the only thing that reaches the tool.',
  /* What the tool itself is made of. Named products are named as they are
     shipped; the sentence beside each is what this project does with it. */
  'about.built.three.label': 'Three.js',
  'about.built.three.text': 'The laboratory viewer uses the core’s hull geometry to show compartments, modules and saved damage events. Three.js handles inspection and replay; the Python core performs the calculations.',
  'about.built.python.label': 'Python · FastAPI · PostgreSQL',
  'about.built.python.text': 'One Python core handles hull, loading, hydrostatics, equilibrium, stability, resistance and flooding. FastAPI serves the tool; PostgreSQL stores projects and results.',

  /* ---- About: the studies ---------------------------------------------- */
  'study.scale.eyebrow': '01 / SCALE',
  'study.scale.title': 'Scale',
  'study.scale.section': 'Scale',
  'study.scale.body': 'Froude compares inertia with gravity. Reynolds compares inertia with viscosity.',
  'study.scale.speed': 'speed',
  'study.scale.length': 'waterline length',
  'study.scale.gravity': 'gravity',
  'study.scale.viscosity': 'kinematic viscosity',
  'study.scale.note': 'Residual-coefficient atlas: Molland, Turnock and Hudson, Ship Resistance and Propulsion, Appendix A3, after Gertler (1954).',
  'study.friction.eyebrow': '02 / FRICTION',
  'study.friction.title': 'Friction',
  'study.friction.section': 'Friction',
  'study.friction.body': 'Skin friction is quoted as a dimensionless coefficient. Plimsoll uses Conn’s 1953 explicit approximation to the Kármán–Schoenherr line.',
  'study.friction.note': 'Shown for 10⁶ ≤ Re ≤ 10⁹.',
  'study.power.eyebrow': '03 / POWER',
  'study.power.title': 'Power',
  'study.power.section': 'Power',
  'study.power.body': 'Effective power is resistance times speed. Plimsoll splits total resistance into friction and residual, within its own model.',
  'study.power.total': 'total',
  'study.power.friction': 'friction',
  'study.power.residual': 'residual',
  'study.power.speed': 'speed',
  'study.power.note': 'Effective power in watts; kilowatts divide by 1000. Computed once resistance and speed are known.',

  /* ---- About: the figures ----------------------------------------------- */
  'figure.harmonic': 'FIG. 01 / HARMONIC STUDIES',
  'figure.scale': 'FIG. 02 / SPEED, LENGTH, GRAVITY, VISCOSITY',
  'figure.scaleCaption': 'Speed and waterline length. Schematic.',
  'figure.friction': 'FIG. 03 / SKIN FRICTION AGAINST REYNOLDS NUMBER',
  'figure.frictionCaption': 'Conn, 1953 / Schoenherr approximation, over the interval Plimsoll declares valid.',
  'figure.power': 'FIG. 04 / RESISTANCE AGAINST SPEED',
  'figure.powerCaption': 'The two quantities whose product is effective power.',

  /* ---- About: the typeset mathematics ------------------------------------ */
  /* The formula on screen is unchanged in both languages: these are the spoken
     names of equations, not the equations themselves. */
  'math.harmonic1': 'x equals sine of a t plus phi; y equals sine of b t; t from zero up to two pi.',
  'math.harmonic2': 'Two families: a and b are 3 and 2 with phase pi over 2, 0 and pi over 4; a and b are 5 and 4 with phase 0 and pi over 3.',
  'math.scale': 'Froude number equals speed divided by the square root of g times L; Reynolds number equals speed times L divided by nu.',
  'math.friction': 'Cf equals 0.4631 divided by log base ten of Re raised to the power 2.6.',
  'math.power': 'Effective power equals total resistance times speed; total resistance is friction resistance plus residual resistance.',

  /* ---- About: contact ---------------------------------------------------- */
  'contact.section': 'Contact',
  'contact.title': 'Get in touch',
  'contact.note': 'About the work, a bug in one of the tools, or something worth building together — email is the surest way.',
  'contact.copy': 'COPY EMAIL',
  'contact.github': 'GITHUB',
  'contact.copied': 'COPIED — {email} is on your clipboard.',
  'contact.failed': 'NOT COPIED — this browser did not give the page clipboard access. The address above is a plain mail link: select it, or open it directly.',

  /* ---- Credits ----------------------------------------------------------- */
  'credits.label': 'Credits',
  'credits.eyebrow': 'CREDITS',
  'credits.title': 'With thanks.',
  'credits.sectionThanks': 'Acknowledgements',
  'credits.sectionColophon': 'Colophon',
  'credits.sectionSources': 'Sources',
  'credits.thanks.0': 'For thoughtful suggestions on the art direction and visual style of this website.',
  'credits.thanks.1': 'For generously providing Coding Plan credits that supported its development.',
  'credits.colophon.0': 'Concept, planning & design direction',
  'credits.colophon.1': 'Review',
  'credits.colophon.2': 'Implementation assistance',
  /* The one printed source and its authors. A book and its authors are named the
     same way in either language; both rows are marked `lang="en"` at the call
     site rather than translated into something they are not. */
  'credits.sourceBook': 'Ship Resistance and Propulsion',
  'credits.sourceAuthors': 'Molland, Turnock & Hudson.',
  'credits.licence': 'Licence',
  'credits.openSource': 'Open source',
  /* The three Work drawings: what they are, and that nothing was redrawn. */
  'credits.sheets.label': 'Reference drawings',
  'credits.sheets.text': 'The three line drawings on Work are archived scans, cropped and toned per theme without redrawing, tracing or generation. They are reference sheets for one featured project, not three projects or verified specifications of a single vessel.',

  /* ---- Work detail -------------------------------------------------------- */
  'detail.label': 'Plimsoll, project detail',
  'detail.back': 'BACK TO WORK',
  'detail.eyebrow': 'WORK / 01 · NAVAL DESIGN WORKBENCH',
  'detail.openTool': 'Open Plimsoll',
  'detail.lede': 'A workbench for studying ship projects — loading, stability, resistance and simplified damage — built on one Python calculation core with a browser interface in front of it.',
  'detail.heroNote': 'REFERENCE {id} / SAME DRAWING AS THE EXHIBIT',
  'detail.overview': 'Overview',
  'detail.capabilities': 'Capabilities',
  'detail.workflow': 'Quick start',
  'detail.technology': 'Technology',
  'detail.limits': 'Methods & Limits',

  'detail.overview.0.label': 'What it is',
  'detail.overview.0.text': 'A naval design and analysis workbench for studying ship projects: loading conditions, stability, resistance and simplified damage. Projects are edited in the browser, saved as immutable revisions, and calculated by one Python core that also runs from a command line, with no interface at all.',
  'detail.overview.1.label': 'How it is organised',
  'detail.overview.1.text': 'One weight ledger per loading condition, then a request for the calculation stages you actually need. Each result records the revision, condition, scenario and request it belongs to, so a stored number always says what produced it.',
  'detail.overview.2.label': 'One work, three drawings',
  'detail.overview.2.text': 'The three reference line sheets on the Work page are alternatives inside this single project, not three projects and not interchangeable verified specifications of one vessel.',

  'detail.capabilities.0.label': 'Weight ledger',
  'detail.capabilities.0.text': 'One ledger is the only mass authority. Every item keeps its own identity, source and estimate flag, and two items claiming the same weight block a complete total rather than counting it twice.',
  'detail.capabilities.1.label': 'Loading conditions',
  'detail.capabilities.1.text': 'Normal, full and custom loadings, with mass and the three axis moments. A present zero is known zero, a present null is unknown, and missing mass is never replaced by a residual invented to match a reference displacement.',
  'detail.capabilities.2.label': 'Hydrostatics',
  'detail.capabilities.2.text': 'A parameterized hull or a strictly imported offsets table, plus Bonjean and hydrostatic curves, deck freeboard and opening checks. A deck coverage percentage is reported only when both areas have sources; otherwise it stays unknown.',
  'detail.capabilities.3.label': 'Equilibrium and stability',
  'detail.capabilities.3.text': 'Draft, trim and heel calculations with liquid-load effects, GM and sampled GZ curves, including opening-immersion checks.',
  'detail.capabilities.4.label': 'Resistance and endurance',
  'detail.capabilities.4.text': 'Taylor-Gertler, Schoenherr, Holtrop-Mennen, fixed power and QPC sensitivity, with each method’s validity range, its estimated inputs and any historical comparison condition kept explicit in the result.',
  'detail.capabilities.5.label': 'Simplified damage',
  'detail.capabilities.5.text': 'Connected quasi-static flooding of declared compartments over time, with mass conservation, remaining GZ, and explicit completed, partial, failed and cancelled states.',
  'detail.capabilities.6.label': 'Interfaces',
  'detail.capabilities.6.text': 'A Python API, single-case, batch and parameter-scan commands, and JSON plus CSV export. The calculation core does not depend on the web service, the database or this site.',
  'detail.capabilities.7.label': 'Damage laboratory',
  'detail.capabilities.7.text': 'Declare a hit position to inspect module damage and aggregate crew effects. An optional declared detonation traces representative fragments through bulkhead shielding. Simplified breaches generated by these rules feed the existing connected-flooding, equilibrium and remaining-GZ calculations, with replay on the 3D hull. Damage parameters remain explicit game approximations.',

  'detail.workflow.0.label': '1 · Open',
  'detail.workflow.0.text': 'Open Plimsoll from the title above and you land in the project library with an anonymous workspace bound to this browser — no account, and nothing shared with other visitors. For a first run, start from 通用试验船 (Generic Steamer): it arrives with a full hull and loading condition as demonstration data, not measured values from a real vessel. The workspace controls are currently in Chinese.',
  'detail.workflow.1.label': '2 · Run',
  'detail.workflow.1.text': 'Leave the sample condition and the calculation request exactly as they are, then use 运行计算 (Run calculation). Afterward, open 查看完整报告 (View full report). The eight default stages cover loading, systems, design baseline, geometry, equilibrium, hydrostatics, deck and propulsion. GZ, resistance, endurance and flooding need separate requests.',
  'detail.workflow.2.label': '3 · Read status first',
  'detail.workflow.2.text': 'In the report, read the status row, then the diagnostics, then the saved revision, condition and request fingerprint — before reading any number. Unknown is not zero: a field with no result shows as unknown with its reason rather than as 0. A partial run is not a complete conclusion.',
  'detail.workflow.3.label': '4 · Change one thing',
  'detail.workflow.3.text': 'Edit a single known input, keeping its source or estimate flag, then press 保存修订 (Save revision) before running again. Saving creates a new revision rather than rewriting the old one, so every stored result stays tied to the inputs it was actually calculated from.',
  'detail.workflow.4.label': '5 · Keep and export',
  'detail.workflow.4.text': 'Download project JSON (下载项目 JSON) backs up the project’s inputs — use it to restore or move a project. The report’s JSON and CSV exports are the calculation results, not a project backup. When you want to see the damage laboratory, the library offers it as an explicitly labelled demonstration case; nothing is imported into your project automatically.',

  'detail.technology.0.label': 'React · TypeScript · Vite',
  'detail.technology.0.text': 'The public shell: one hash router, the exhibit, this detail and About. The workspace is a separate chunk fetched on demand, so no page here can reach the API.',
  'detail.technology.1.label': 'Python calculation core',
  'detail.technology.1.text': 'Project, loading, hydrostatics, stability, resistance and flooding kernels. The API, the command line and the web service all call this one module.',
  'detail.technology.2.label': 'FastAPI · SQLAlchemy · Alembic',
  'detail.technology.2.text': 'FastAPI serves the application; SQLAlchemy manages stored data, and Alembic versions the database schema.',
  'detail.technology.3.label': 'PostgreSQL',
  'detail.technology.3.text': 'Project storage, immutable revisions, the calculation queue and stored results.',
  'detail.technology.4.label': 'Independent worker',
  'detail.technology.4.text': 'A separate process that claims each queued run, enforces the time and result-size limits, supports cancellation, and marks a lost worker’s run failed instead of leaving it running forever.',
  'detail.technology.5.label': 'Three.js',
  'detail.technology.5.text': 'The laboratory viewer uses the core’s hull geometry to show compartments, modules and saved damage events. Three.js handles inspection and replay; the Python core performs the calculations.',

  'detail.limits.0.label': 'Not a full SPS reproduction',
  'detail.limits.0.text': 'An independent implementation of comparable ideas. Field-for-field equivalence with SPS is not claimed, and proprietary SPS scoring is not implemented.',
  'detail.limits.1.label': 'Damage is a game approximation',
  'detail.limits.1.text': 'The hit position is declared rather than solved, fragment paths are representative and seeded, and bulkhead transmission is a value you state. None of this is physical armour penetration, a fuse solver, blast pressure, calibrated fragment or injury physics, fire or structural breakup, and it is not a complete combat simulator.',
  'detail.limits.2.label': 'Outside the current scope',
  'detail.limits.2.text': 'Full seakeeping, structural strength, historical cost and a complete combat-damage simulation are not modelled.',
  'detail.limits.3.label': 'Not a certified design tool',
  'detail.limits.3.text': '“Completed” means the requested calculation stages finished. It does not mean the inputs are historically verified or that a vessel is seaworthy.',
  'detail.limits.4.label': 'Inputs carry declared gaps',
  'detail.limits.4.text': 'Historical ship inputs are partly estimated. A model’s bounding box is not a real armour spread area, and no tonnage is reconciled with an arbitrary balancing weight. Missing historical data is reported as unknown rather than filled in.',
  'detail.limits.5.label': 'Method boundaries are enforced',
  'detail.limits.5.text': 'A locked-CG proxy with no free surface cannot drive a connected flood; the interface blocks that combination up front with a stated reason instead of letting the kernel stop mid-run and keep partial results.',
  'detail.limits.6.label': 'A result belongs to its identity',
  'detail.limits.6.text': 'Results are valid for the revision, condition, scenario and request fingerprint they were computed with. A trace shorter than the requested duration must be read together with its stop reason; a partial result is not a complete or safe conclusion.',
} as const;

/** Every string a public page can print. */
export type TranslationKey = keyof typeof EN;

/**
 * The shape both dictionaries must have.
 *
 * `string` rather than the literal type English happens to infer, so the Chinese
 * side is checked for *completeness and shape* — which is the thing that
 * actually goes wrong — and not for being the identical string.
 */
export type Dictionary = Readonly<Record<TranslationKey, string>>;

/* ------------------------------------------------------------------------- */
/* Chinese                                                                     */
/* ------------------------------------------------------------------------- */

/**
 * The Simplified Chinese edition.
 *
 * Plain, short sentences; no marketing voice, no invented biography and no
 * qualification the English page does not also carry. Navy, armour and blast
 * physics are nowhere claimed as certified here, exactly as they are not there.
 */
const ZH: Dictionary = {
  /* ---- document -------------------------------------------------------- */
  'doc.title.home': 'Y’s Formfield — 工具与实验',
  'doc.title.project': 'Plimsoll — Y’s Formfield',
  'doc.title.credits': '致谢 — Y’s Formfield',

  /* ---- header ---------------------------------------------------------- */
  'header.home': '返回 Y’s Formfield 首页',
  'header.languageGroup': '语言',
  'header.languageZh': '中文',
  'header.languageZhTitle': '中文界面',
  'header.languageEn': 'EN',
  'header.languageEnTitle': '英文界面',
  'header.themeDark': '切换到深色主题',
  'header.themeLight': '切换到浅色主题',
  'header.replay': '重播开场',
  'header.sound': '音效',
  'header.soundOn': '开启音效',
  'header.soundOff': '关闭音效',

  /* ---- footer ---------------------------------------------------------- */
  'footer.tagline': '精准 · 现代 · 互动',

  /* ---- the rail and the reading ruler ---------------------------------- */
  'nav.label': '主导航',
  'nav.work': '作品',
  'nav.about': '关于',
  'nav.credits': '致谢',
  'ruler.label': '阅读进度',
  'ruler.reading': '阅读中',

  /* ---- Work: the exhibit ----------------------------------------------- */
  'work.label': '精选作品',
  'work.exhibitHead': '精选作品',
  'work.exhibitMeta': '工具与实验',
  'work.exhibitFolio': 'VOL. 01',
  'work.lede': '动手探索船舶设计。',
  'work.openTool': '打开 Plimsoll',
  'work.viewProject': '查看项目',
  'work.drawingIdle': '交互式俯视图。用方向键移动图纸，按 Home 键复位。',
  'work.drawingInspect': '交互式俯视图，已开启 2 倍放大，显示当前扫描图的局部。用方向键移动放大镜，按 Home 键复位，按 Esc 键退出。',
  'work.inspectOn': '放大镜已开启',
  'work.inspectOff': '放大镜已关闭',
  'work.inspectIdleTitle': '放大查看 · 2×',
  'work.inspectActiveTitle': '关闭放大镜',
  'work.reset': '重置视图',
  'work.sheetGroup': '参考图纸',
  'work.sheetLabel': '参考图纸 {id}',
  'work.sheetTitle': '查看图纸 {id}',
  'work.boardCaption': '图纸 {id} / 03',
  'work.sheetError': '图纸 {id} 加载失败，当前仍显示图纸 {kept}。',
  'work.sheetErrorRetry': '重试 {id}',
  'work.sheetErrorRest': '，或选择其他图纸。',
  'work.imageError': '图纸加载失败。请选择其他图纸，或点击“重播开场”重试。',
  'work.loadingStatus': '正在加载参考图纸',
  'work.preparing': '图纸准备中',
  'work.skipIntro': '跳过开场',
  'splash.status': '正在打开 Y’s Formfield',

  /* ---- About ------------------------------------------------------------ */
  'about.label': '关于 Y’s Formfield',
  'about.eyebrow': '关于本站',
  'about.titleLead': '让想法',
  'about.titleTail': '派上用场。',
  'about.intro': '这里收录了 Yang Duanming 制作的工具与实验项目。你可以直接使用船舶设计工具，也可以翻阅相关的参考图纸。',
  'about.sectionCollection': '本站介绍',
  'about.sectionPerson': '作者',
  'about.sectionPlimsoll': 'Plimsoll',
  'about.sectionBuilt': '技术栈',
  'about.authorTitle': '关于作者',
  'about.authorP1': '我是 Yang Duanming。我制作工具，也探索界面设计。',
  'about.authorP2': '这里既有可以实际使用的软件，也有相关的参考图纸。Plimsoll 是首个展示的项目。',
  'about.workLabel': '首件作品 / 01',
  'about.workTitle': 'Plimsoll',
  'about.workText': 'Plimsoll 用于研究船舶的装载、静水力、稳性与阻力，也提供损伤实验室，将模块与人员影响的游戏近似接入进水和剩余稳性计算。浏览器和命令行共用一套 Python 核心，结果可导出为 JSON、CSV。',
  'about.viewProject': '查看项目',
  'about.builtTitle': '技术栈',
  'about.built.react.label': 'React · TypeScript · Vite',
  'about.built.react.text': '负责本站公开页面与工具界面：页面之间通过哈希路由切换，工具内的所有表单也在此实现。',
  'about.built.svg.label': 'SVG 与 CSS',
  'about.built.svg.text': '用于展板边框、辅助线、放大镜和页面转场。船体周围的装饰几何不代表实测工程数据。',
  'about.built.fonts.label': 'Space Grotesk · Inter',
  'about.built.fonts.text': '标题使用 Space Grotesk，正文使用 Inter。两款可变字体均由本站托管，采用拉丁字符子集，遵循 SIL OFL 1.1 许可。',
  'about.built.noApi.label': '介绍页与工作区',
  'about.built.noApi.text': '浏览这些页面不会调用 Plimsoll 服务，也不会创建工作空间。只有打开 Plimsoll 后，才会进入工具。',
  'about.built.three.label': 'Three.js',
  'about.built.three.text': '基于计算核心的船体几何，显示舱室、模块与已保存的损伤事件。Three.js 负责三维查看与回放，计算仍由 Python 核心完成。',
  'about.built.python.label': 'Python · FastAPI · PostgreSQL',
  'about.built.python.text': '船型、装载、静水力、平衡、稳性、阻力与进水共用一套 Python 计算核心，由 FastAPI 提供服务，数据存入 PostgreSQL。',

  /* ---- About: the studies ---------------------------------------------- */
  'study.scale.eyebrow': '01 / 尺度',
  'study.scale.title': '尺度',
  'study.scale.section': '尺度',
  'study.scale.body': '傅汝德数描述惯性与重力的相对作用，雷诺数描述惯性与黏性的相对作用。',
  'study.scale.speed': '航速',
  'study.scale.length': '水线长',
  'study.scale.gravity': '重力加速度',
  'study.scale.viscosity': '运动黏度',
  'study.scale.note': '残余阻力系数图谱见 Molland, Turnock and Hudson《Ship Resistance and Propulsion》附录 A3，依据 Gertler（1954）的资料。',
  'study.friction.eyebrow': '02 / 摩擦',
  'study.friction.title': '摩擦',
  'study.friction.section': '摩擦',
  'study.friction.body': '摩擦阻力用无量纲系数表示。Plimsoll 采用 Conn 于 1953 年提出的显式近似式，逼近 Kármán–Schoenherr 摩擦线。',
  'study.friction.note': '图示范围：10⁶ ≤ Re ≤ 10⁹。',
  'study.power.eyebrow': '03 / 功率',
  'study.power.title': '功率',
  'study.power.section': '功率',
  'study.power.body': '有效功率是总阻力与航速的乘积。Plimsoll 将总阻力分为摩擦阻力和残余阻力两部分。',
  'study.power.total': '总阻力',
  'study.power.friction': '摩擦阻力',
  'study.power.residual': '残余阻力',
  'study.power.speed': '航速',
  'study.power.note': '已知阻力和航速，即可计算有效功率。结果以瓦为单位，除以 1000 可换算为千瓦。',

  /* ---- About: the figures ----------------------------------------------- */
  'figure.harmonic': '图 01 / 谐波曲线',
  'figure.scale': '图 02 / 航速、水线长、重力与黏性',
  'figure.scaleCaption': '航速与水线长示意。',
  'figure.friction': '图 03 / 摩擦系数与雷诺数',
  'figure.frictionCaption': 'Conn（1953）的 Schoenherr 近似式，绘于 Plimsoll 设定的有效区间内。',
  'figure.power': '图 04 / 阻力与航速',
  'figure.powerCaption': '阻力与航速的乘积，就是有效功率。',

  /* ---- About: the typeset mathematics ------------------------------------ */
  'math.harmonic1': 'x 等于 a 乘 t 加 φ 的正弦；y 等于 b 乘 t 的正弦；t 大于等于零，小于二倍 π。',
  'math.harmonic2': '两组参数：第一组，a 为 3、b 为 2，相位依次为 π/2、0、π/4；第二组，a 为 5、b 为 4，相位依次为 0、π/3。',
  'math.scale': '傅汝德数等于航速除以 g 与 L 乘积的平方根；雷诺数等于航速乘以 L 再除以 ν。',
  'math.friction': '先取 Re 以 10 为底的对数，再求其 2.6 次方；用 0.4631 除以这个值，即得摩擦系数 Cf。',
  'math.power': '有效功率等于总阻力乘以航速；总阻力为摩擦阻力与残余阻力之和。',

  /* ---- About: contact ---------------------------------------------------- */
  'contact.section': '联系方式',
  'contact.title': '联系方式',
  'contact.note': '想聊聊作品、反馈工具的问题，或讨论合作，都可以发邮件给我。',
  'contact.copy': '复制邮箱',
  'contact.github': 'GITHUB',
  'contact.copied': '{email} 已复制到剪贴板。',
  'contact.failed': '复制失败，浏览器未允许访问剪贴板。你可以手动复制上方地址，或点击地址直接发邮件。',

  /* ---- Credits ----------------------------------------------------------- */
  'credits.label': '致谢',
  'credits.eyebrow': '致谢',
  'credits.title': '谢谢你们。',
  'credits.sectionThanks': '特别感谢',
  'credits.sectionColophon': '制作信息',
  'credits.sectionSources': '资料来源',
  'credits.thanks.0': '为本站的艺术设计与视觉风格提供了宝贵建议。',
  'credits.thanks.1': '提供了宝贵的 Coding Plan 额度，支持网站开发。',
  'credits.colophon.0': '构思、规划与设计方向',
  'credits.colophon.1': '审查与复核',
  'credits.colophon.2': '代码实现协助',
  'credits.sourceBook': 'Ship Resistance and Propulsion',
  'credits.sourceAuthors': 'Molland, Turnock & Hudson.',
  'credits.licence': '许可证',
  'credits.openSource': '开源组件',
  'credits.sheets.label': '参考图纸',
  'credits.sheets.text': '作品页的三张型线图均为存档扫描件，仅作裁切并随主题调整色调，未重绘、描摹或生成。它们作为 Plimsoll 的展览参考图，不是三个独立项目，也不代表同一艘船的经核实参数。',

  /* ---- Work detail -------------------------------------------------------- */
  'detail.label': 'Plimsoll 项目详情',
  'detail.back': '返回作品',
  'detail.eyebrow': '作品 / 01 · 船舶设计工作台',
  'detail.openTool': '打开 Plimsoll',
  'detail.lede': '面向船舶设计研究的工作台，可分析装载、稳性、阻力与简化破损。通过浏览器操作，由同一套 Python 核心完成计算。',
  'detail.heroNote': '参考图纸 {id} / 与作品页展板一致',
  'detail.overview': '概述',
  'detail.capabilities': '功能',
  'detail.workflow': '首次使用',
  'detail.technology': '技术构成',
  'detail.limits': '方法与限制',

  'detail.overview.0.label': '项目简介',
  'detail.overview.0.text': 'Plimsoll 是一个船舶设计与分析工作台，用于研究装载工况、稳性、阻力和简化破损。你可以在浏览器中编辑项目，保存为不可改写的修订版本，再交由 Python 核心计算；也可以直接通过命令行使用同一套核心。',
  'detail.overview.1.label': '数据如何组织',
  'detail.overview.1.text': '每个装载工况各有一份重量账本，计算时只需选择所需阶段。结果会记录对应的项目版本、装载工况、破损情景和计算请求，便于追溯每个数值的来处。',
  'detail.overview.2.label': '一个作品，三张图纸',
  'detail.overview.2.text': '作品页的三张参考型线图都属于 Plimsoll 这个项目，可切换展示。它们不代表三个独立项目，也不能作为同一艘船经过验证、可互换使用的设计数据。',

  'detail.capabilities.0.label': '重量账本',
  'detail.capabilities.0.text': '所有质量数据统一以重量账本为准。每一项都保留标识、来源和估算标记；若同一份重量被重复申报，系统不会给出完整总量，以免重复计入。',
  'detail.capabilities.1.label': '装载工况',
  'detail.capabilities.1.text': '支持正常、满载和自定义装载，计算质量及三个坐标方向的质量矩。0 表示已知为零，null 表示未知；缺失项保留为未知，不会为凑齐参考排水量而补入重量。',
  'detail.capabilities.2.label': '静水力计算',
  'detail.capabilities.2.text': '支持参数化船型，也可导入经过严格校验的型值表，生成 Bonjean 曲线与静水力曲线，并检查甲板干舷和开口。只有计算覆盖率所需的两个面积都有数据来源时，才给出甲板覆盖率；否则标为未知。',
  'detail.capabilities.3.label': '平衡与稳性',
  'detail.capabilities.3.text': '计算吃水、纵倾和横倾，考虑液体载荷的影响，给出 GM 和逐点计算的 GZ 曲线，并检查开口是否浸没。',
  'detail.capabilities.4.label': '阻力与航程',
  'detail.capabilities.4.text': '支持 Taylor-Gertler、Schoenherr、Holtrop-Mennen 方法，以及定功率和 QPC 敏感性分析。结果会注明方法适用范围、估算输入和历史数据的对照条件。',
  'detail.capabilities.5.label': '简化破损',
  'detail.capabilities.5.text': '对已定义的连通舱室进行随时间推进的准静态进水计算，跟踪质量守恒与剩余 GZ，并区分完成、部分完成、失败和取消状态。',
  'detail.capabilities.6.label': '调用与导出',
  'detail.capabilities.6.text': '提供 Python API，以及单次计算、批量计算和参数扫描命令，支持 JSON、CSV 导出。计算核心可独立运行，不依赖 Web 服务、数据库或本网站。',
  'detail.capabilities.7.label': '损伤实验室',
  'detail.capabilities.7.text': '设定命中位置，查看模块损伤与人员影响；也可指定起爆点，追踪受舱壁遮挡的代表性弹片路径。按设定规则生成的简化破口会接入原有的连通进水、平衡和剩余 GZ 计算，结果可在三维船体上回放。各项损伤参数均为明确标注的游戏近似。',

  'detail.workflow.0.label': '1 · 打开工具',
  'detail.workflow.0.text': '点击上方的标题进入 Plimsoll，会直接打开项目库，并为本浏览器建立一个匿名工作空间：无需注册，也不与其他访客共享。第一次使用建议从「通用试验船」开始，它自带完整型线与装载工况，属于明确标注的演示数据，并非真实船型的实测值。工作区控件目前为中文。',
  'detail.workflow.1.label': '2 · 运行计算',
  'detail.workflow.1.text': '保留案例工况与默认计算请求不作修改，点击「运行计算」，完成后打开「查看完整报告」。默认的八个阶段包括装载、系统、设计基线、型线、平衡、静水力、甲板与推进。稳性曲线（GZ）、阻力、续航与进水需要另行发起请求。',
  'detail.workflow.2.label': '3 · 先看状态',
  'detail.workflow.2.text': '阅读报告时，请先看状态栏，再看诊断信息，最后确认已保存的修订、工况与请求指纹，然后再看数值。未知不等于零：没有结果的字段会显示为未知并给出原因，而不是 0。部分完成的结果不能当作完整结论。',
  'detail.workflow.3.label': '4 · 修改一项再计算',
  'detail.workflow.3.text': '修改一项已知的输入，并保留其来源或估算标记，然后先点击「保存修订」再重新计算。保存会生成新的修订，而不是改写旧的，因此每个已保存的结果始终对应它当时实际使用的输入。',
  'detail.workflow.4.label': '5 · 备份与导出',
  'detail.workflow.4.text': '「下载项目 JSON」备份的是项目输入，可用于恢复或转移项目；报告中的 JSON、CSV 导出的是计算结果，不是项目备份。想体验损伤实验室，可从项目库进入，按提示导入演示案例。演示数据会明确标注，导入由你主动确认。',

  'detail.technology.0.label': 'React · TypeScript · Vite',
  'detail.technology.0.text': '公开页面采用哈希路由，包含作品展板、项目详情与关于页。工作空间代码按需加载；这些公开页面不调用 Plimsoll API。',
  'detail.technology.1.label': 'Python 计算核心',
  'detail.technology.1.text': '负责船型、装载、静水力、稳性、阻力和进水计算。API、命令行与 Web 服务都使用同一套核心。',
  'detail.technology.2.label': 'FastAPI · SQLAlchemy · Alembic',
  'detail.technology.2.text': 'FastAPI 提供应用服务，SQLAlchemy 管理数据读写，Alembic 管理数据库结构的版本变更。',
  'detail.technology.3.label': 'PostgreSQL',
  'detail.technology.3.text': '存储项目、不可改写的修订版本、计算队列和计算结果。',
  'detail.technology.4.label': '独立工作进程',
  'detail.technology.4.text': '独立处理队列中的计算任务，限制运行时间与输出大小，并支持取消。如果工作进程失联，任务会标记为失败，避免一直显示运行中。',
  'detail.technology.5.label': 'Three.js',
  'detail.technology.5.text': '基于计算核心的船体几何，显示舱室、模块与已保存的损伤事件。Three.js 负责三维查看与回放，计算仍由 Python 核心完成。',

  'detail.limits.0.label': '与 SPS 的关系',
  'detail.limits.0.text': 'Plimsoll 借鉴相近思路独立开发，并非 SPS 的完整复刻，也不保证功能与字段逐项对应。SPS 的专有评分体系未在此实现。',
  'detail.limits.1.label': '破损属于游戏尺度的近似',
  'detail.limits.1.text': '命中位置是人为声明的，并非由解算得到；弹片路径是具有确定性与代表性的示意；舱壁传递率也由使用者声明。以上都不是真实的装甲穿透、引信计时、爆炸压力、经过标定的弹片与人员伤害物理，也不涉及火灾与结构解体，更不是完整的战斗模拟。',
  'detail.limits.2.label': '尚未涵盖的内容',
  'detail.limits.2.text': '目前尚未建立完整的耐波性、结构强度、历史造价模型，也没有完整的战斗损伤仿真。',
  'detail.limits.3.label': '计算完成不代表设计获认证',
  'detail.limits.3.text': 'Plimsoll 不是经认证的船舶设计工具。“已完成”仅表示选定的计算阶段已结束，不代表输入符合史实，也不代表船舶具备适航性。',
  'detail.limits.4.label': '明确标出数据缺口',
  'detail.limits.4.text': '历史船舶参数中，有些来自估算。模型的包围盒不能代表实际装甲面积，也不会用任意配重凑齐参考吨位。缺失的历史数据会标为未知，不会擅自补全。',
  'detail.limits.5.label': '不适用的组合会提前拦截',
  'detail.limits.5.text': '固定重心且不考虑自由液面的简化模型，不能用于连通舱室进水计算。界面会提前阻止这种组合并说明原因，避免计算中途停止、只留下部分结果。',
  'detail.limits.6.label': '结果仅对应本次输入',
  'detail.limits.6.text': '每份结果只对应计算时的项目版本、装载工况、破损情景和请求指纹。若模拟未达到设定时长，应结合停止原因阅读结果；部分结果不能当作完整结论，也不能用来确认安全性。',
};

/** The whole dictionary for one language. */
export function dictionary(language: SiteLanguage): Dictionary {
  return language === 'zh-CN' ? ZH : EN;
}

/**
 * One message, with its `{slot}`s filled.
 *
 * An unknown key returns the key itself rather than an empty string, so a typo
 * shows up on screen as something obviously wrong instead of as a missing line.
 */
export function translate(language: SiteLanguage, key: TranslationKey, params?: CopyParams): string {
  const text: string = (dictionary(language) as Record<string, string>)[key] ?? key;
  if (!params) return text;
  return text.replace(/\{(\w+)\}/g, (match, slot: string) =>
    Object.hasOwn(params, slot) ? String(params[slot]) : match);
}

/* ------------------------------------------------------------------------- */
/* Preference                                                                  */
/* ------------------------------------------------------------------------- */

/** What the stored preference says, or `null` when it says nothing usable. */
export function storedLanguage(): SiteLanguage | null {
  try {
    const raw = localStorage.getItem(LANGUAGE_KEY);
    return raw === 'zh-CN' || raw === 'en' ? raw : null;
  } catch {
    // A refused `localStorage` is a browser's answer, not an error to raise.
    return null;
  }
}

/**
 * Remember a choice that was actually made.
 *
 * Only ever called from a press on one of the two buttons, so a stored value
 * always records a choice this visitor actually made and nothing else. A refused
 * write is ignored exactly as the theme preference ignores it.
 */
export function rememberLanguage(language: SiteLanguage): void {
  try { localStorage.setItem(LANGUAGE_KEY, language); }
  catch { /* The choice still applies to this page without being stored. */ }
}

/**
 * The language this shell starts in: a valid stored choice, and otherwise English.
 *
 * The default does not follow the browser. A visitor is served English first
 * whatever locale their browser reports, and Chinese is something they ask for
 * here rather than something inferred about them: the header's 中文 / EN pair is
 * the way in, and the choice it makes is remembered. So there is exactly one
 * unchosen state and it is English, which also means no visitor ever lands on a
 * page assembled from half of one language and half of the other.
 *
 * Anything unreadable, absent or left over from another version reads as "no
 * choice made" and therefore as English, never as a third language.
 */
export function initialLanguage(): SiteLanguage {
  return storedLanguage() ?? 'en';
}
