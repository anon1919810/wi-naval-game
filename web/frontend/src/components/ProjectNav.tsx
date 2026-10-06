// The chapter index. Numbers are static page furniture; the Chinese label stays
// the accessible name of every control, and the English title is the structural
// heading of the chapter itself.
export const CHAPTERS = [
  ['overview', '概览', 'Overview', undefined, '输入读数、当前工况、最新匹配结果与运行记录。'],
  ['hull', '船型与几何', 'Hull & Geometry', undefined, '主尺度只记录已知输入；留空表示未知，不自动补零。'],
  ['weights', '重量与载荷', 'Weights & Loading', undefined, '这里只修改已有条目；新增分组可通过“项目数据”编辑。'],
  ['armour', '装甲与武备', 'Armour & Systems', 'systems', '这里编辑系统事实；质量仍须在所选载荷账本中明确绑定，不能重复计重。'],
  ['guns', '火炮武备', 'Gunnery', 'systems', '声明炮数与每炮携弹数；单发弹重优先取自账本弹药模型，没有模型时可声明仅用于报告的弹丸质量。全舰携带量仍取自账本。'],
  ['weapons', '鱼雷与水雷武备', 'Torpedoes & Mines', 'systems', '声明鱼雷、水雷、深弹及五个杂项位置分区；系统质量取自所选载荷账本，位置分区声明质量仅用于报告，不另加排水量。'],
  ['stability', '浮态与稳性', 'Freeboard & Stability', 'deck', '端点、干舷与参考长度需要独立来源。未知值请保持空缺。'],
  ['propulsion', '动力与性能', 'Propulsion', 'systems', '锅炉、燃料和传动事实来自项目输入；计算结果只出现在运行记录里。'],
  ['performance', '性能与工况', 'Performance & Studies', undefined, '工况定义与研究场景是输入；请求只决定这次运行计算什么。'],
  ['damage', '破损研究', 'Damage', 'flooding_scenarios', '场景声明舱室、连接与开口；它是研究输入，不是第二份重量账本。项目舱室仍决定主带研究范围。'],
  ['json', '项目数据', 'Project Data', undefined, '这里可编辑所有符合 plimsoll-project-1 契约的字段。应用后仍须保存修订。'],
] as const;

export type Chapter = typeof CHAPTERS[number][0];

export interface ChapterDefinition {
  id: Chapter;
  /** Chinese accessible name, unchanged from the previous index. */
  label: string;
  /** English structural heading used as the chapter `h1`. */
  title: string;
  /** Section key of the chapter JSON view, where the contract has one. */
  jsonKey?: string;
  /** One-sentence purpose, shown directly under the heading. */
  purpose?: string;
}

const DEFINITIONS: readonly ChapterDefinition[] = CHAPTERS.map(([id, label, title, jsonKey, purpose]) => ({
  id, label, title, ...(jsonKey ? { jsonKey } : {}), ...(purpose ? { purpose } : {}),
}));

export function chapterOf(chapter: Chapter): ChapterDefinition {
  return DEFINITIONS.find(entry => entry.id === chapter) ?? DEFINITIONS[0];
}

/** Static two-digit index of a chapter; decorative, never part of the name. */
export function chapterNumber(chapter: Chapter): string {
  return String(DEFINITIONS.findIndex(entry => entry.id === chapter) + 1).padStart(2, '0');
}

export function ProjectNav({ name, active, onSelect, onBack }: {
  name: string; active: Chapter; onSelect: (chapter: Chapter) => void; onBack: () => void;
}) {
  return <aside className="project-nav" aria-label="项目章节">
    <button className="nav-return" onClick={onBack}>← 项目库</button>
    <div className="nav-section-label">当前舰船</div>
    <div className="nav-project-name" title={name}>{name}</div>
    <div className="nav-section-label nav-section-label--chapters">研究章节</div>
    <nav>{DEFINITIONS.map(entry => <button key={entry.id}
      className={`nav-item ${active === entry.id ? 'nav-item--active' : ''}`}
      aria-current={active === entry.id ? 'page' : undefined}
      onClick={() => onSelect(entry.id)}>
      {/* The number is page furniture; the Chinese label remains the name. */}
      <span className="nav-index" aria-hidden="true">{chapterNumber(entry.id)}</span>
      <span className="nav-label">{entry.label}</span>
    </button>)}</nav>
    <div className="nav-bottom"><span className="datum-icon" aria-hidden="true" />数据与计算分开保存</div>
  </aside>;
}
