import { useCallback } from 'react';
import { useLanguage } from '../portfolio/LanguageProvider';
import { interpolate } from './terms';
import type { CopyParams, SiteLanguage } from '../portfolio/LanguageProvider';

/**
 * The hull and freeboard dictionary.
 *
 * The hull chapter prints the source's linked normalized dimensions, the
 * design's own length and displacement drivers, its depth-lock declaration and
 * the unified ledger balance. The freeboard chapter prints the eight declared
 * endpoints, the four deck fractions and the drawing's own limits.
 *
 * Three distinctions are kept in the vocabulary itself:
 *
 * - The hull page's overall target is not silently relabelled as feet, and the
 *   source displacement is never printed as a ledger tonne.
 * - A driver or lock that was not declared is unknown, never the control's
 *   default and never the explicit false wording.
 * - A freeboard outline is a declared-endpoint schematic. It is not the real
 *   hull form, the real bow shape or a protected area.
 */
const EN = {
  'hull.kicker': 'LINKED HULL RESULT',
  'hull.title': 'Hull and main dimensions',
  'hull.intro': 'The linked hull dimensions saved by the native method, the design\'s own length and displacement drivers, its depth-lock declaration and the unified ledger balance. Nothing here is recomputed.',

  'hull.state.pending': 'A hull edit is still being confirmed; no linked facts are shown until it settles.',
  'hull.state.failed': 'The hull reading could not be confirmed; no linked facts are shown.',
  'hull.state.absent': 'No native design result is saved for this reading.',
  'hull.state.schema': 'This result does not declare the supported native result shape, so no hull facts are read.',
  'hull.state.method': 'This result does not declare the supported native design method, so no hull facts are read.',
  'hull.state.unavailable': 'This result carries no readable hull or freeboard section.',
  'hull.state.frozen': 'Read-only hull reading of the frozen saved result.',

  'hull.facts.title': 'Linked dimensions',
  'hull.fact.length': 'Waterline length',
  'hull.fact.lengthOA': 'Length overall',
  'hull.fact.beam': 'Moulded beam',
  'hull.fact.beamBulges': 'Beam at bulges',
  'hull.fact.draught': 'Draught (normal)',
  'hull.fact.block': 'Block coefficient',
  'hull.fact.displacement': 'Source displacement',
  'hull.fact.units': 'Lengths are the result\'s normalized feet and follow the reader\'s length unit. The source displacement stays in long tons and is separate from the ledger balance in tonnes below.',

  'hull.driver.title': 'Declared drivers and lock',
  'hull.driver.length': 'Length driver',
  'hull.driver.displacement': 'Displacement driver',
  'hull.driver.depth': 'Depth lock',
  'hull.driver.waterline': 'waterline',
  'hull.driver.overall': 'overall',
  'hull.driver.block': 'block coefficient',
  'hull.driver.displacementChoice': 'displacement',
  'hull.depth.locked': 'locked to saved depth snapshot',
  'hull.depth.unlocked': 'not locked',
  'hull.depth.undeclared': 'depth lock not declared',
  'hull.driver.targetOverall': 'Overall target',
  'hull.driver.targetDisplacement': 'Displacement target',
  'hull.driver.targetNote': 'The overall target is shown exactly as saved on the hull page; it is not converted into feet here. The displacement target is the source long-ton figure.',

  'hull.balance.title': 'Unified ledger balance',
  'hull.balance.selected': 'Selected mass',
  'hull.balance.estimate': 'Estimated mass',
  'hull.balance.target': 'Target displacement',
  'hull.balance.difference': 'Balance difference',
  'hull.balance.note': 'The four balance figures are the managed ledger\'s tonnes, not a second displacement derived from the hull dimensions.',

  'hull.reveal': 'Reveal the field',
  'hull.changed': 'changed',
  'hull.unknown': '—',

  'freeboard.kicker': 'DECLARED ENDPOINTS',
  'freeboard.title': 'Declared endpoint profile',
  'freeboard.intro': 'The eight saved freeboard endpoint heights and the four declared deck fractions. The outline joins only the declared stations; it is not the real hull form, the real bow shape or a protected area.',

  'freeboard.state.pending': 'A freeboard edit is still being confirmed; no profile or facts are shown until it settles.',
  'freeboard.state.failed': 'The freeboard reading could not be confirmed; no profile or facts are shown.',
  'freeboard.state.absent': 'No native design result is saved for this reading.',
  'freeboard.state.schema': 'This result does not declare the supported native result shape, so no freeboard facts are read.',
  'freeboard.state.method': 'This result does not declare the supported native design method, so no freeboard facts are read.',
  'freeboard.state.unavailable': 'This result carries no readable hull or freeboard section.',
  'freeboard.state.frozen': 'Read-only freeboard reading of the frozen saved result.',

  'freeboard.endpoints.title': 'Eight declared endpoints',
  'freeboard.endpoints.note': 'Every endpoint is listed separately, so two coincident stations can still be selected and revealed on its own. A saved zero or negative height is a known source value; a missing height stays unknown.',
  'freeboard.height': 'Freeboard',
  'freeboard.point.freeQDAft': 'Quarterdeck aft',
  'freeboard.point.freeQDFor': 'Quarterdeck fore',
  'freeboard.point.freeADAft': 'Afterdeck aft',
  'freeboard.point.freeADFor': 'Afterdeck fore',
  'freeboard.point.freeFDAft': 'Flat deck aft',
  'freeboard.point.freeFDFor': 'Flat deck fore',
  'freeboard.point.freeFCAft': 'Forecastle aft',
  'freeboard.point.freeFCFor': 'Forecastle fore',

  'freeboard.fraction.title': 'Declared deck fractions',
  'freeboard.fraction.fcLength': 'Forecastle length',
  'freeboard.fraction.fdLength': 'Flat deck length',
  'freeboard.fraction.adLength': 'Afterdeck length',
  'freeboard.fraction.qdLength': 'Quarterdeck length',

  'freeboard.geometry.title': 'Declared station outline',
  'freeboard.problem.length': 'The saved waterline length is missing or not positive, so no outline is drawn.',
  'freeboard.problem.heights': 'An endpoint height is missing or not finite, so no outline is drawn. The known endpoints are still listed.',
  'freeboard.problem.bow': 'The bow angle is missing or not a finite number, so no outline is drawn. The known endpoints are still listed.',
  'freeboard.problem.stern': 'The stern extension is missing, negative or not a finite number, so no outline is drawn. The known endpoints are still listed.',
  'freeboard.problem.fraction': 'The declared deck fractions are outside their 0–1 domain or exceed the hull length together, so no outline is drawn. The saved fractions are still stated as saved.',
  'freeboard.unitNote': 'Endpoint heights are the result\'s normalized feet and follow the reader\'s length unit. The fractions are the source\'s 0–1 declarations, printed as percentages.',

  'freeboard.select.list': 'Endpoint list',
  'freeboard.select.hint': 'Select an endpoint here or in the drawing. Selection only opens its reading and never writes the design.',
  'freeboard.select.edit': 'Reveal the endpoint field',
  'freeboard.select.editHint': 'This reveals and focuses the saved source field; it does not change its value.',
  'freeboard.panel.title': 'Selected endpoint',
  'freeboard.panel.height': 'Saved height',
  'freeboard.lock': 'Pinned by the depth lock: the four FD/AD endpoints come from the saved depth snapshot, so this reading offers no edit there.',
  'freeboard.pinned': 'Pinned by the depth lock; the saved depth snapshot owns this endpoint.',
  'freeboard.changed': 'differs from the saved revision',
  'freeboard.unknown': '—',

  'freeboard.context': 'Context',
  'freeboard.run': 'Run',
  'freeboard.basis': 'Basis',

  'freeboard.export.svg': 'Download SVG',
  'freeboard.export.png': 'Download PNG',
  'freeboard.export.svgError': 'The SVG could not be downloaded in this browser; the reading is unchanged.',
  'freeboard.export.pngError': 'The PNG could not be produced in this browser; the SVG download is still complete.',
  'freeboard.export.file': 'freeboard-profile',
  'freeboard.profile.aria': 'Freeboard endpoint profile',
} as const;

/** Every string the hull and freeboard readers can print. */
export type HullFreeboardKey = keyof typeof EN;

/** The shape both dictionaries must have. */
export type HullFreeboardDictionary = Readonly<Record<HullFreeboardKey, string>>;

const ZH: HullFreeboardDictionary = {
  'hull.kicker': '联动船体结果',
  'hull.title': '船体与主尺度',
  'hull.intro': '原生方法保存的联动船体尺度、设计自身的长度与排水量驱动、深度锁定声明，以及统一台账平衡。此处不做任何重算。',

  'hull.state.pending': '仍有一处船体修改在确认中；确认完成前不显示联动事实。',
  'hull.state.failed': '未能确认船体读数；不显示联动事实。',
  'hull.state.absent': '该读数没有保存原生设计结果。',
  'hull.state.schema': '该结果未声明受支持的原生结果形态，故不读取船体事实。',
  'hull.state.method': '该结果未声明受支持的原生设计方法，故不读取船体事实。',
  'hull.state.unavailable': '该结果不含可读取的船体或干舷分节。',
  'hull.state.frozen': '冻结已保存结果的只读船体读数。',

  'hull.facts.title': '联动尺度',
  'hull.fact.length': '水线长度',
  'hull.fact.lengthOA': '总长',
  'hull.fact.beam': '型宽',
  'hull.fact.beamBulges': '防雷突出部宽',
  'hull.fact.draught': '吃水（正常）',
  'hull.fact.block': '方形系数',
  'hull.fact.displacement': '来源排水量',
  'hull.fact.units': '长度均为结果中的归一化英尺，并按读者所选长度单位显示。来源排水量保持长吨，与下方以吨计的统一台账平衡彼此独立。',

  'hull.driver.title': '已声明驱动与锁定',
  'hull.driver.length': '长度驱动',
  'hull.driver.displacement': '排水量驱动',
  'hull.driver.depth': '深度锁定',
  'hull.driver.waterline': '水线',
  'hull.driver.overall': '总长',
  'hull.driver.block': '方形系数',
  'hull.driver.displacementChoice': '排水量',
  'hull.depth.locked': '锁定为已保存深度快照',
  'hull.depth.unlocked': '未锁定',
  'hull.depth.undeclared': '未声明深度锁定',
  'hull.driver.targetOverall': '总长目标',
  'hull.driver.targetDisplacement': '排水量目标',
  'hull.driver.targetNote': '总长目标按船体页保存的数值原样显示，此处不换算为英尺。排水量目标为来源长吨数值。',

  'hull.balance.title': '统一台账平衡',
  'hull.balance.selected': '选取质量',
  'hull.balance.estimate': '估算质量',
  'hull.balance.target': '目标排水量',
  'hull.balance.difference': '平衡差额',
  'hull.balance.note': '四项平衡数字均为受管台账的吨值，不是从主尺度另行推导的第二套排水量。',

  'hull.reveal': '揭示字段',
  'hull.changed': '有变化',
  'hull.unknown': '—',

  'freeboard.kicker': '已声明端点',
  'freeboard.title': '已声明端点剖面',
  'freeboard.intro': '八个已保存干舷端点高度与四段已声明甲板比例。轮廓只连接已声明站位，不表示实际型线、真实船艏外形或防护面积。',

  'freeboard.state.pending': '仍有一处干舷修改在确认中；确认完成前不显示剖面或事实。',
  'freeboard.state.failed': '未能确认干舷读数；不显示剖面或事实。',
  'freeboard.state.absent': '该读数没有保存原生设计结果。',
  'freeboard.state.schema': '该结果未声明受支持的原生结果形态，故不读取干舷事实。',
  'freeboard.state.method': '该结果未声明受支持的原生设计方法，故不读取干舷事实。',
  'freeboard.state.unavailable': '该结果不含可读取的船体或干舷分节。',
  'freeboard.state.frozen': '冻结已保存结果的只读干舷读数。',

  'freeboard.endpoints.title': '八个已声明端点',
  'freeboard.endpoints.note': '每个端点单独列出，因此两个重合站位仍可分别选择与揭示。已保存的零或负高度均为已知来源值；缺失高度保持未知。',
  'freeboard.height': '干舷',
  'freeboard.point.freeQDAft': '艉楼后',
  'freeboard.point.freeQDFor': '艉楼前',
  'freeboard.point.freeADAft': '后甲板后',
  'freeboard.point.freeADFor': '后甲板前',
  'freeboard.point.freeFDAft': '平甲板后',
  'freeboard.point.freeFDFor': '平甲板前',
  'freeboard.point.freeFCAft': '艏楼后',
  'freeboard.point.freeFCFor': '艏楼前',

  'freeboard.fraction.title': '已声明甲板比例',
  'freeboard.fraction.fcLength': '艏楼长度',
  'freeboard.fraction.fdLength': '平甲板长度',
  'freeboard.fraction.adLength': '后甲板长度',
  'freeboard.fraction.qdLength': '艉楼长度',

  'freeboard.geometry.title': '已声明站位轮廓',
  'freeboard.problem.length': '已保存水线长度缺失或不为正，故不绘制轮廓。',
  'freeboard.problem.heights': '有端点高度缺失或非有限，故不绘制轮廓；已知端点仍会列出。',
  'freeboard.problem.bow': '艏角缺失或非有限，故不绘制轮廓；已知端点仍会列出。',
  'freeboard.problem.stern': '艉延伸缺失、为负或非有限，故不绘制轮廓；已知端点仍会列出。',
  'freeboard.problem.fraction': '已声明甲板比例超出 0–1 范围，或合计超出船体长度，故不绘制轮廓；已保存比例仍按原样陈述。',
  'freeboard.unitNote': '端点高度为结果中的归一化英尺，并按读者所选长度单位显示。比例是来源的 0–1 声明，以百分比显示。',

  'freeboard.select.list': '端点清单',
  'freeboard.select.hint': '在此清单或图中选择端点。选择只打开其读数，绝不写入设计。',
  'freeboard.select.edit': '揭示端点字段',
  'freeboard.select.editHint': '此处只揭示并聚焦已保存的来源字段，不更改其数值。',
  'freeboard.panel.title': '已选端点',
  'freeboard.panel.height': '已保存高度',
  'freeboard.lock': '深度锁定已固定：FD／AD 四个端点来自已保存深度快照，因此此处不为它们提供编辑。',
  'freeboard.pinned': '由深度锁定固定；该端点归已保存深度快照所有。',
  'freeboard.changed': '与已保存修订不同',
  'freeboard.unknown': '—',

  'freeboard.context': '上下文',
  'freeboard.run': '运行',
  'freeboard.basis': '基准',

  'freeboard.export.svg': '下载 SVG',
  'freeboard.export.png': '下载 PNG',
  'freeboard.export.svgError': '此浏览器无法下载 SVG；读数未改变。',
  'freeboard.export.pngError': '此浏览器无法生成 PNG；SVG 下载仍然完整。',
  'freeboard.export.file': '干舷剖面',
  'freeboard.profile.aria': '干舷端点剖面',
};

/** The whole hull/freeboard dictionary for one language. */
export function hullFreeboardDictionary(language: SiteLanguage): HullFreeboardDictionary {
  return language === 'zh-CN' ? ZH : EN;
}

/** One message, with its `{slot}`s filled; an unknown key returns the key. */
export function hullFreeboardCopy(language: SiteLanguage, key: HullFreeboardKey, params?: CopyParams): string {
  const text: string = (hullFreeboardDictionary(language) as Record<string, string>)[key] ?? key;
  return interpolate(text, params);
}

/** The lookup, bound to the shell's one language state. */
export function useHullFreeboardCopy(): (key: HullFreeboardKey, params?: CopyParams) => string {
  const { language } = useLanguage();
  return useCallback((key: HullFreeboardKey, params?: CopyParams) => hullFreeboardCopy(language, key, params), [language]);
}
