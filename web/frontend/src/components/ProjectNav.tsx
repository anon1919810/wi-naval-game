export const CHAPTERS = [
  ['overview', '概览'], ['hull', '船型与几何'], ['weights', '重量与载荷'],
  ['armour', '装甲与武备'], ['guns', '火炮武备'], ['weapons', '鱼雷与水雷武备'], ['stability', '浮态与稳性'],
  ['propulsion', '动力与性能'], ['damage', '破损研究'], ['json', '项目数据'],
] as const;

export type Chapter = typeof CHAPTERS[number][0];

export function ProjectNav({ name, active, onSelect, onBack }: {
  name: string; active: Chapter; onSelect: (chapter: Chapter) => void; onBack: () => void;
}) {
  return <aside className="project-nav" aria-label="项目章节">
    <button className="nav-return" onClick={onBack}>← 项目库</button>
    <div className="nav-section-label">当前舰船</div>
    <div className="nav-project-name" title={name}>{name}</div>
    <div className="nav-section-label nav-section-label--chapters">研究章节</div>
    <nav>{CHAPTERS.map(([key, label]) => <button key={key} className={`nav-item ${active === key ? 'nav-item--active' : ''}`} aria-current={active === key ? 'page' : undefined} onClick={() => onSelect(key)}>{label}</button>)}</nav>
    <div className="nav-bottom"><span className="datum-icon" aria-hidden="true" />数据与计算分开保存</div>
  </aside>;
}
