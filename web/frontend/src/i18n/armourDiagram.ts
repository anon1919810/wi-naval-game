import { useCallback } from 'react';
import { useLanguage } from '../portfolio/LanguageProvider';
import { interpolate } from './terms';
import type { CopyParams, SiteLanguage } from '../portfolio/LanguageProvider';

/**
 * The armour diagram dictionary.
 *
 * The diagram prints its own words: the schematic conventions it may not guess
 * (where a belt sits along the hull, where a tower stands, where the machinery
 * and magazine boxes are), the seven deck-coverage names the source selector
 * chooses between, the two bulkhead types, and the state of a reading that is
 * pending, failed, or not the supported shape. English is the source and Chinese
 * is shape-checked against it, the arrangement every other dictionary here uses.
 */

const EN = {
  'armour.kicker': 'ARMOUR ARRANGEMENT',
  'armour.title': 'Armour diagram',
  'armour.intro': 'A schematic of the armour reading. It draws only the stated facts and says where placement is not declared.',

  'armour.state.pending': 'An armour edit is still being confirmed; no diagram or numbers are shown until it settles.',
  'armour.state.failed': 'The armour reading could not be confirmed; no diagram or numbers are shown.',
  'armour.state.absent': 'No native armour result is saved for this reading.',
  'armour.state.schema': 'This result does not declare the supported native result shape, so no diagram is drawn.',
  'armour.state.method': 'This result does not declare the supported native design method, so no diagram is drawn.',
  'armour.state.unavailable': 'This result carries no armour section, so there is nothing to draw.',
  'armour.state.frozen': 'Read-only diagram of the frozen saved result.',

  'armour.context.title': 'Reading context',
  'armour.context.draft': 'Confirmed draft · saved revision {revision}',
  'armour.context.hullLength': 'Waterline length',
  'armour.context.beam': 'Beam',
  'armour.context.basis': 'Basis condition',
  'armour.context.source': 'Source',
  'armour.context.bulkheadType': 'Bulkhead type',
  'armour.warn': 'The core flagged this armour reading; treat the drawn bands as declared values only.',

  'armour.bands.title': 'Length-proportion bands',
  'armour.bands.note': 'Schematic convention: each band is drawn centred at its declared length as a fraction of the waterline length. Starting station and vertical placement are not declared and are not shown.',
  'armour.bands.track': 'Waterline length',
  'armour.bands.zero': 'declared zero length',
  'armour.bands.unknown': 'length unknown',

  'armour.problem.missing': 'Length is missing or not a finite number; the band is not drawn.',
  'armour.problem.negative': 'Length is negative; the band is not drawn.',
  'armour.problem.overlong': 'Length is longer than the waterline length; the band is not drawn to proportion.',
  'armour.problem.nohull': 'The waterline length is unknown, so this length cannot be drawn to proportion.',

  'armour.deck.title': 'Deck partition (plan)',
  'armour.deck.note': 'Schematic convention: the declared deck fractions are shown end to end. The hull outline and the protected area are not declared and are not drawn.',
  'armour.deck.boxes': 'The machinery and magazine box positions are not declared; no box is placed.',
  'armour.deck.coverage': 'Deck coverage',
  'armour.deck.coverageSelected': 'selected',
  'armour.deck.coverageOptions': 'All seven coverage options the source offers',
  'armour.deck.thickness': 'Main deck',
  'armour.deck.forecastle': 'Forecastle deck',
  'armour.deck.quarterdeck': 'Quarterdeck',
  'armour.deck.fraction': 'Fraction',
  'armour.deck.total': 'Declared total',
  'armour.deck.fractionOverlong': 'The declared deck fractions total more than the hull; they are shown as declared and are never trimmed.',
  'armour.deck.fractionIncomplete': 'One or more declared deck fractions are unknown; the later segments cannot be placed.',
  'armour.deck.fractionInvalid': 'A declared deck fraction is not a valid fraction of the hull (0–1).',
  'armour.segment.quarterdeck': 'Quarterdeck',
  'armour.segment.afterdeck': 'Afterdeck',
  'armour.segment.flatDeck': 'Central deck (flat deck)',
  'armour.segment.forecastle': 'Forecastle',

  'armour.towers.title': 'Conning towers',
  'armour.towers.note': 'Thicknesses only. The tower positions are not declared and are not drawn.',
  'armour.tower.forward': 'Forward conning tower',
  'armour.tower.aft': 'Aft conning tower',

  'armour.bulkhead.title': 'Bulkheads',
  'armour.bulkhead.note': 'The source declares a bulkhead type, not a known torpedo or transverse arrangement.',

  'armour.freeboard.title': 'Freeboard endpoints (context)',
  'armour.freeboard.note': 'The eight saved endpoints, read through the same geometry the freeboard profile uses. Underwater hull and belt placement are not declared and are not drawn.',
  'armour.freeboard.missing': 'The saved freeboard endpoints are missing or cannot be plotted; the context strip is omitted.',
  'armour.freeboard.stern': 'Stern',
  'armour.freeboard.bow': 'Bow',

  'armour.ledger.title': 'Ledger masses',
  'armour.ledger.note': 'Every shown mass is the managed ledger\'s own reading for that role. The armour block\'s weights are long tons and are not used as masses.',
  'armour.policy.estimated': 'estimated',
  'armour.policy.declared': 'declared (manual)',
  'armour.policy.other': 'other policy',
  'armour.policy.unset': 'not set',

  'armour.mass.selected': 'Selected mass',
  'armour.mass.estimate': 'Source estimate',
  'armour.mass.target': 'Target displacement',
  'armour.mass.difference': 'Balance gap',

  'armour.bulkhead.beam': 'Beam',
  'armour.bulkhead.type': 'Type',
  'armour.deck.unknownRest': 'The remaining segments are not placed because an earlier declared fraction is unknown.',

  'armour.fact.length': 'Length',
  'armour.fact.height': 'Height',
  'armour.fact.thickness': 'Thickness',
  'armour.fact.inclination': 'Inclination',
  'armour.fact.weight': 'Source weight',
  'armour.fact.ledger': 'Ledger',
  'armour.fact.mode': 'Policy',
  'armour.fact.selected': 'Selected mass',
  'armour.fact.estimate': 'Source estimate',
  'armour.fact.unknown': 'not declared',

  'armour.legend.title': 'Legend',
  'armour.legend.known': 'Known dimensions (as declared)',
  'armour.legend.unknown': 'Placement not declared (schematic only)',
  'armour.legend.changed': 'Differs from the saved revision',
  'armour.legend.units': 'Lengths and heights in {length}; thicknesses in {thickness}; masses in {mass}.',

  'armour.mass.title': 'Mass and balance',
  'armour.mass.total': 'Armour weight',
  'armour.mass.belts': 'Belts weight',
  'armour.mass.beltCover': 'Belt coverage',
  'armour.mass.maxBeltHeight': 'Maximum belt height',
  'armour.mass.context': 'Shown mass belongs to',
  'armour.mass.run': 'Run',

  'armour.region.belt_main': 'Main belt',
  'armour.region.belt_ends': 'End belts',
  'armour.region.belt_upper': 'Upper belt',
  'armour.region.bulkhead': 'Bulkheads',
  'armour.region.bulge': 'Bulges',
  'armour.region.deck': 'Deck',
  'armour.region.conning': 'Conning towers',

  'armour.select.title': 'Region',
  'armour.select.hint': 'Select a region in the diagram or the list to read its dimensions and masses.',
  'armour.select.list': 'Armour regions',
  'armour.select.edit': 'Edit this region',
  'armour.select.editHint': 'Opens the matching field group and focuses its first field.',

  'armour.export.svg': 'Download SVG',
  'armour.export.png': 'Download PNG',
  'armour.export.error': 'The picture could not be produced.',
  'armour.export.svgError': 'The SVG could not be downloaded in this browser. Please try again.',
  'armour.export.pngError': 'The PNG could not be produced in this browser; the SVG is still complete.',

  'armour.unit.ft': 'ft',
  'armour.unit.m': 'm',
  'armour.unit.t': 't',
  'armour.unit.kg': 'kg',
  'armour.unit.long_ton': 'long ton',
  'armour.unit.deg': '°',
  'armour.unit.rad': 'rad',
  'armour.unit.in': 'in',
  'armour.unit.mm': 'mm',

  'armour.changed': 'changed',
  'armour.continuous': 'Continuous facts',
} as const;

/** Every string the armour diagram can print. */
export type ArmourDiagramKey = keyof typeof EN;

/** The shape both dictionaries must have. */
export type ArmourDiagramDictionary = Readonly<Record<ArmourDiagramKey, string>>;

const ZH: ArmourDiagramDictionary = {
  'armour.kicker': '装甲布置',
  'armour.title': '装甲示意图',
  'armour.intro': '依据装甲读数绘制的示意图。只绘制已声明的事实，并说明哪些位置未被声明。',

  'armour.state.pending': '仍有一处装甲修改在确认中；确认完成前不显示示意图或数字。',
  'armour.state.failed': '未能确认装甲读数；不显示示意图或数字。',
  'armour.state.absent': '该读数没有保存原生装甲结果。',
  'armour.state.schema': '该结果未声明受支持的原生结果形态，故不绘制示意图。',
  'armour.state.method': '该结果未声明受支持的原生设计方法，故不绘制示意图。',
  'armour.state.unavailable': '该结果不含装甲部分，故没有可绘制的内容。',
  'armour.state.frozen': '冻结已保存结果的只读示意图。',

  'armour.context.title': '读数背景',
  'armour.context.draft': '已确认草稿 · 已保存修订 {revision}',
  'armour.context.hullLength': '水线长度',
  'armour.context.beam': '型宽',
  'armour.context.basis': '基准工况',
  'armour.context.source': '来源',
  'armour.context.bulkheadType': '舱壁类型',
  'armour.warn': '核心对该装甲读数给出告警；所绘条带仅表示已声明数值。',

  'armour.bands.title': '按长度比例的条带',
  'armour.bands.note': '示意约定：每条带以水线长度的比例、按各自声明的长度居中绘制。起始站与垂向位置并未声明，因此不作标示。',
  'armour.bands.track': '水线长度',
  'armour.bands.zero': '声明长度为零',
  'armour.bands.unknown': '长度未知',

  'armour.problem.missing': '长度缺失或非有限数；不绘制该条带。',
  'armour.problem.negative': '长度为负；不绘制该条带。',
  'armour.problem.overlong': '长度大于水线长度；不按比例绘制该条带。',
  'armour.problem.nohull': '水线长度未知，故无法按比例绘制该长度。',

  'armour.deck.title': '甲板划分（平面）',
  'armour.deck.note': '示意约定：声明的甲板分段依次相接展示。船体外轮廓与防护面积并未声明，因此不作绘制。',
  'armour.deck.boxes': '机械舱与弹药库盒体的位置并未声明；因此不放置任何盒体。',
  'armour.deck.coverage': '甲板覆盖',
  'armour.deck.coverageSelected': '已选',
  'armour.deck.coverageOptions': '来源提供的全部七种覆盖方式',
  'armour.deck.thickness': '主甲板',
  'armour.deck.forecastle': '艏楼甲板',
  'armour.deck.quarterdeck': '后甲板',
  'armour.deck.fraction': '占比',
  'armour.deck.total': '声明合计',
  'armour.deck.fractionOverlong': '声明的甲板占比合计超过船体；按声明展示，绝不裁剪。',
  'armour.deck.fractionIncomplete': '一处或多处声明的甲板占比未知；其后的分段无法定位。',
  'armour.deck.fractionInvalid': '某处声明的甲板占比不是船体的有效占比（0–1）。',
  'armour.segment.quarterdeck': '后甲板',
  'armour.segment.afterdeck': '尾甲板',
  'armour.segment.flatDeck': '中部甲板（平甲板）',
  'armour.segment.forecastle': '艏楼',

  'armour.towers.title': '司令塔',
  'armour.towers.note': '仅给出厚度。塔的位置并未声明，因此不作绘制。',
  'armour.tower.forward': '前司令塔',
  'armour.tower.aft': '后司令塔',

  'armour.bulkhead.title': '舱壁',
  'armour.bulkhead.note': '来源声明的是舱壁类型，而非已知的鱼雷或横向布置。',

  'armour.freeboard.title': '干舷端点（背景）',
  'armour.freeboard.note': '按干舷剖面所用的同一几何读取的八个已保存端点。水下船体与装甲带位置并未声明，因此不作绘制。',
  'armour.freeboard.missing': '已保存的干舷端点缺失或无法绘制；故省略背景条。',
  'armour.freeboard.stern': '艉',
  'armour.freeboard.bow': '艏',

  'armour.ledger.title': '台账质量',
  'armour.ledger.note': '所示每项质量均为该角色在受管台账中的读数。装甲部分的质量为长吨，不作为质量使用。',
  'armour.policy.estimated': '估算',
  'armour.policy.declared': '声明（手动）',
  'armour.policy.other': '其他策略',
  'armour.policy.unset': '未设置',

  'armour.mass.selected': '选取质量',
  'armour.mass.estimate': '来源估算',
  'armour.mass.target': '目标排水量',
  'armour.mass.difference': '平衡差额',

  'armour.bulkhead.beam': '型宽',
  'armour.bulkhead.type': '类型',
  'armour.deck.unknownRest': '由于靠前的一处声明占比未知，其余分段不作定位。',

  'armour.fact.length': '长度',
  'armour.fact.height': '高度',
  'armour.fact.thickness': '厚度',
  'armour.fact.inclination': '倾角',
  'armour.fact.weight': '来源质量',
  'armour.fact.ledger': '台账',
  'armour.fact.mode': '策略',
  'armour.fact.selected': '选取质量',
  'armour.fact.estimate': '来源估算',
  'armour.fact.unknown': '未声明',

  'armour.legend.title': '图例',
  'armour.legend.known': '已知尺寸（按声明）',
  'armour.legend.unknown': '位置未声明（仅为示意）',
  'armour.legend.changed': '与已保存修订不同',
  'armour.legend.units': '长度与高度以 {length} 计；厚度以 {thickness} 计；质量以 {mass} 计。',

  'armour.mass.title': '质量与平衡',
  'armour.mass.total': '装甲质量',
  'armour.mass.belts': '装甲带质量',
  'armour.mass.beltCover': '装甲带覆盖',
  'armour.mass.maxBeltHeight': '最大装甲带高度',
  'armour.mass.context': '所示质量属于',
  'armour.mass.run': '运行',

  'armour.region.belt_main': '主装甲带',
  'armour.region.belt_ends': '端部装甲带',
  'armour.region.belt_upper': '上部装甲带',
  'armour.region.bulkhead': '舱壁',
  'armour.region.bulge': '防雷鼓包',
  'armour.region.deck': '甲板',
  'armour.region.conning': '司令塔',

  'armour.select.title': '区域',
  'armour.select.hint': '在示意图或列表中选择一个区域，即可读取其尺寸与质量。',
  'armour.select.list': '装甲区域',
  'armour.select.edit': '编辑此区域',
  'armour.select.editHint': '打开对应的字段分组并聚焦其第一个字段。',

  'armour.export.svg': '下载 SVG',
  'armour.export.png': '下载 PNG',
  'armour.export.error': '未能生成图片。',
  'armour.export.svgError': '此浏览器未能下载 SVG，请重试。',
  'armour.export.pngError': '此浏览器未能生成 PNG；SVG 内容仍然完整。',

  'armour.unit.ft': '英尺',
  'armour.unit.m': '米',
  'armour.unit.t': '吨',
  'armour.unit.kg': '千克',
  'armour.unit.long_ton': '长吨',
  'armour.unit.deg': '°',
  'armour.unit.rad': '弧度',
  'armour.unit.in': '英寸',
  'armour.unit.mm': '毫米',

  'armour.changed': '已变更',
  'armour.continuous': '连续事实',
};

/** The whole armour diagram dictionary for one language. */
export function armourDiagramDictionary(language: SiteLanguage): ArmourDiagramDictionary {
  return language === 'zh-CN' ? ZH : EN;
}

/** One diagram message, with its `{slot}`s filled; an unknown key returns the key. */
export function armourDiagramCopy(language: SiteLanguage, key: ArmourDiagramKey, params?: CopyParams): string {
  const text: string = (armourDiagramDictionary(language) as Record<string, string>)[key] ?? key;
  return interpolate(text, params);
}

/** The diagram lookup, bound to the shell's one language state. */
export function useArmourDiagramCopy(): (key: ArmourDiagramKey, params?: CopyParams) => string {
  const { language } = useLanguage();
  return useCallback((key: ArmourDiagramKey, params?: CopyParams) => armourDiagramCopy(language, key, params), [language]);
}

/** The seven deck-coverage names, in the source selector's own order. */
export const DECK_COVERAGE_LABELS: Readonly<Record<SiteLanguage, readonly string[]>> = {
  en: [
    'Armoured deck — multiple decks',
    'Armoured deck — single deck',
    'Protected deck — multiple decks',
    'Protected deck — single deck',
    'Box over machinery',
    'Box over magazines',
    'Box over machinery & magazines',
  ],
  'zh-CN': [
    '装甲甲板 —— 多层',
    '装甲甲板 —— 单层',
    '防护甲板 —— 多层',
    '防护甲板 —— 单层',
    '机械舱盒式防护',
    '弹药库盒式防护',
    '机械舱与弹药库盒式防护',
  ],
};

/** The two declared bulkhead types, in the source selector's own order. */
export const BULKHEAD_TYPE_LABELS: Readonly<Record<SiteLanguage, readonly string[]>> = {
  en: ['Additional bulkheads', 'Strengthened bulkheads'],
  'zh-CN': ['附加舱壁', '加强舱壁'],
};

/** One deck-coverage name by selector index, or `null` when the index is not one of the seven. */
export function deckCoverageLabel(language: SiteLanguage, index: number | null): string | null {
  if (index === null || !Number.isInteger(index) || index < 0 || index >= DECK_COVERAGE_LABELS[language].length) return null;
  return DECK_COVERAGE_LABELS[language][index];
}

/** One bulkhead-type name by selector index, or `null` when the index is not one of the two. */
export function bulkheadTypeLabel(language: SiteLanguage, index: number | null): string | null {
  if (index === null || !Number.isInteger(index) || index < 0 || index >= BULKHEAD_TYPE_LABELS[language].length) return null;
  return BULKHEAD_TYPE_LABELS[language][index];
}

/** The reader's word for one ledger policy, in the reader's own language. */
export function policyLabel(language: SiteLanguage, mode: string | null): string {
  if (mode === 'estimated') return armourDiagramCopy(language, 'armour.policy.estimated');
  if (mode === 'declared') return armourDiagramCopy(language, 'armour.policy.declared');
  if (mode === null || mode === '') return armourDiagramCopy(language, 'armour.policy.unset');
  return armourDiagramCopy(language, 'armour.policy.other');
}
