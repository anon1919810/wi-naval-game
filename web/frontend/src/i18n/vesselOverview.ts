import { useCallback } from 'react';
import { useLanguage } from '../portfolio/LanguageProvider';
import { interpolate } from './terms';
import { designFeedbackCopy } from './designFeedback';
import { deckCoverageLabel } from './armourDiagram';
import type { CopyParams, SiteLanguage } from '../portfolio/LanguageProvider';

/**
 * The vessel-overview and armament-composition dictionary.
 *
 * The overview states independent known facts and names every unknown as
 * unknown; it makes no aggregate completeness claim. The composition reader
 * prints the five declared banks, their two groups and the source estimates in
 * the units the native source returned. Both surfaces are frozen-report safe:
 * every enum label lives here as a static bilingual table, so a saved reading is
 * readable offline with no catalogue fetch.
 *
 * English is the source and Chinese is shape-checked against it, the arrangement
 * every other dictionary here uses.
 */

const EN = {
  'vessel.kicker': 'VESSEL DESIGN',
  'vessel.title': 'Vessel design overview',
  'vessel.intro': 'The confirmed draft as one design. Each section states independent known facts; a value that is not declared stays unknown, and no section claims the design is complete.',

  'vessel.state.pending': 'An edit is still being confirmed; no overview facts are shown until it settles.',
  'vessel.state.failed': 'The design reading could not be confirmed; no overview facts are shown.',
  'vessel.state.absent': 'No native design result is saved for this reading.',
  'vessel.state.schema': 'This result does not declare the supported native result shape, so no overview is drawn.',
  'vessel.state.method': 'This result does not declare the supported native design method, so no overview is drawn.',
  'vessel.state.unavailable': 'This result carries no readable native sections.',
  'vessel.state.frozen': 'Read-only overview of the frozen saved result.',
  'vessel.context.draft': 'Confirmed draft · saved revision {revision}',

  'vessel.section.hull': 'Hull and main dimensions',
  'vessel.section.freeboard': 'Freeboard',
  'vessel.section.armament': 'Armament',
  'vessel.section.armour': 'Armour',
  'vessel.section.propulsion': 'Propulsion',
  'vessel.section.weight': 'Weight and balance',
  'vessel.open': 'Open {chapter}',
  'vessel.unknown': '—',

  'vessel.fact.length': 'Waterline length',
  'vessel.fact.beam': 'Beam',
  'vessel.fact.draught': 'Draught (normal)',
  'vessel.fact.freeboard': 'Freeboard',
  'vessel.fact.freeboardNote': 'The saved freeboard reading. Deck-partition fractions and the endpoint profile are shown in their own chapters and in the frozen report.',
  'vessel.fact.batteryLine': '{calibre} · {barrels} barrels · {mounts} mounts',
  'vessel.fact.batteryNone': 'No battery is declared.',
  'vessel.fact.batteryUnavailable': 'Battery {bank} is not declared.',
  'vessel.fact.armamentNote': 'The five declared batteries, each read on its own. The guns chapter holds the full two-group composition and its source estimates.',
  'vessel.fact.beltMain': 'Main belt thickness',
  'vessel.fact.deck': 'Armour deck thickness',
  'vessel.fact.deckCoverage': 'Deck coverage',
  'vessel.fact.speedMax': 'Maximum speed',
  'vessel.fact.speedCruise': 'Cruise speed',
  'vessel.fact.hpMax': 'Maximum power',
  'vessel.fact.range': 'Range',
  'vessel.fact.fuel': 'Fuel',
  'vessel.fact.engine': 'Engines',
  'vessel.fact.drive': 'Drive',
  'vessel.fact.screws': 'Shafts',
  'vessel.fact.powerLock': 'Power lock',
  'vessel.fact.lockTarget': 'Locked power and bunker',
  'vessel.fact.propulsionNote': 'Power is the source horsepower, shown as saved and never relabelled. Fuel, engine and drive are the declared selections, never guessed.',
  'vessel.fact.balanceSelected': 'Selected mass',
  'vessel.fact.balanceEstimate': 'Estimated mass',
  'vessel.fact.balanceTarget': 'Target displacement',
  'vessel.fact.balanceDifference': 'Balance difference',
  'vessel.fact.ledgerGuns': 'Guns',
  'vessel.fact.ledgerMounts': 'Mounts',
  'vessel.fact.ledgerAmmunition': 'Ammunition',
  'vessel.fact.ledgerGunArmour': 'Gun armour',
  'vessel.fact.ledgerNote': 'The ledger\'s own global role masses, stored in tonnes and shown in the chosen mass unit. They are never split across the batteries and never added to the source estimates.',
  'vessel.fact.selected': 'selected',
  'vessel.fact.estimate': 'estimate',
  'vessel.fact.mode': 'policy',
  'vessel.fact.noneSelected': 'none selected',

  'armament.kicker': 'ARMAMENT COMPOSITION',
  'armament.title': 'Armament composition',
  'armament.intro': 'Every declared battery, its two mount groups and its source estimates. Selection reveals one battery; it never changes the saved declaration.',

  'armament.state.pending': 'An armament edit is still being confirmed; no composition or numbers are shown until it settles.',
  'armament.state.failed': 'The armament reading could not be confirmed; no composition or numbers are shown.',
  'armament.state.absent': 'No native armament result is saved for this reading.',
  'armament.state.schema': 'This result does not declare the supported native result shape, so no composition is drawn.',
  'armament.state.method': 'This result does not declare the supported native design method, so no composition is drawn.',
  'armament.state.unavailable': 'This result carries no readable armament section.',
  'armament.state.frozen': 'Read-only composition of the frozen saved result.',

  'armament.banks.title': 'Five batteries',
  'armament.banks.note': 'Each battery carries its own declared number; the list order is never its identity. A battery that is missing or declared ambiguously is unavailable and is never reassigned.',
  'armament.banks.list': 'Armament batteries',
  'armament.bank.label': 'Battery {bank}',
  'armament.bank.zero': 'Declared zero armament.',
  'armament.bank.missing': 'Not declared.',
  'armament.bank.ambiguous': 'The declaration is ambiguous, so no configuration is read for this battery.',
  'armament.group.G1': 'Group 1',
  'armament.group.G2': 'Group 2',
  'armament.group.none': 'This group is not declared.',
  'armament.group.mounts': '{count} mounts',
  'armament.group.mountsUnknown': 'mounts not declared',

  'armament.fact.barrels': 'Barrels',
  'armament.fact.mounts': 'Total mounts',
  'armament.fact.calibre': 'Calibre',
  'armament.fact.gunType': 'Gun type',
  'armament.fact.mountType': 'Mount type',
  'armament.fact.year': 'Year',
  'armament.fact.calLength': 'Calibre length',
  'armament.fact.magazine': 'Rounds per gun',
  'armament.fact.selector': 'Mount selector',
  'armament.fact.layout': 'Arrangement',
  'armament.fact.perMount': 'Barrels per mount',
  'armament.fact.groupMounts': 'Mounts in group',
  'armament.fact.elevated': 'Elevated mounts',
  'armament.fact.deck': 'Deck mounts',
  'armament.fact.depressed': 'Depressed mounts',
  'armament.fact.face': 'Face armour',
  'armament.fact.side': 'Side / roof armour',
  'armament.fact.barbette': 'Barbette armour',
  'armament.fact.shellDeclared': 'Declared shell weight',
  'armament.fact.shellEffective': 'Effective shell weight',
  'armament.fact.shellRecovered': 'Adjusted shell weight',
  'armament.fact.broadside': 'Broadside weight',
  'armament.fact.gunWeight': 'Gun mass (source)',
  'armament.fact.mountWeight': 'Mount mass (source)',
  'armament.fact.magazineWeight': 'Magazine mass (source)',
  'armament.fact.armWeight': 'Mount armour mass (source)',
  'armament.fact.totalWeight': 'Total mass (source)',
  'armament.fact.estimateNote': 'The five mass figures are the source\'s own returned estimates, stored in long tons and shown in the chosen mass unit. They are never recomputed and never added to the ledger.',
  'armament.fact.weightUnits': 'Declared and effective shell weights and the broadside weight are pounds; the five mass estimates are stored in long tons and shown in the chosen mass unit.',
  'armament.fact.flagElevation': 'Double elevation declared',
  'armament.fact.flagDepression': 'Double depression declared',
  'armament.fact.calibreLength': '{value} cal',
  'armament.count.invalid': '{value} — not a whole count',
  'armament.flags.unknown': 'not declared',
  'armament.flags.none': 'none declared',

  'armament.ledger.title': 'Global ledger masses',
  'armament.ledger.note': 'The four armament roles as the managed ledger holds them, stored in tonnes and shown in the chosen mass unit. They are global: no per-battery split exists, and a manual policy change appears here even when the battery configuration is unchanged.',
  'armament.ledger.role.guns': 'Guns',
  'armament.ledger.role.mounts': 'Mounts',
  'armament.ledger.role.ammunition': 'Ammunition',
  'armament.ledger.role.gun_armour': 'Gun armour',
  'armament.ledger.mass': '{selected} selected · {estimate} estimate · policy {policy}',

  'armament.select.list': 'Select a battery',
  'armament.select.hint': 'Select a battery in the list to read its configuration and source estimates. Selection keeps keyboard focus and never changes the declaration.',
  'armament.select.edit': 'Edit this battery calibre',
  'armament.select.editHint': 'Opens the guns field group and focuses this battery\'s calibre field.',
  'armament.changed': 'changed',

  'armament.export.svg': 'Download SVG',
  'armament.export.png': 'Download PNG',
  'armament.export.svgError': 'The SVG could not be downloaded in this browser. Please try again.',
  'armament.export.pngError': 'The PNG could not be produced in this browser; the SVG is still complete.',

  'armament.legend.title': 'Legend',
  'armament.legend.battery': 'One declared battery, by its own number rather than its position',
  'armament.legend.group': 'One mount group; the glyphs are a bounded schematic, never a placement',
  'armament.legend.unknown': 'Not declared (schematic only)',
  'armament.legend.changed': 'Differs from the saved revision',
  'armament.legend.units': 'Calibre and thicknesses in inches and millimetres; shell and broadside weights in pounds; source mass estimates stored in long tons; ledger masses stored in tonnes. Masses follow the chosen mass unit.',

  'vessel.config.title': 'Configuration changes',
  'vessel.config.intro': 'Five battery configurations and the key hull, armour and propulsion facts. The direction is comparison − current, the same as the reading table beside it.',
  'vessel.config.current': 'Current',
  'vessel.config.comparison': 'Comparison',
  'vessel.config.metric': 'Fact',
  'vessel.config.difference': 'Difference',
  'vessel.config.group.battery': 'Battery configuration',
  'vessel.config.group.hull': 'Hull',
  'vessel.config.group.armour': 'Armour',
  'vessel.config.group.propulsion': 'Propulsion',
  'vessel.config.battery': 'Battery {bank}',
  'vessel.config.unavailable': 'not declared',
  'vessel.config.unchanged': 'unchanged',
  'vessel.config.categorical': 'labels only, no numeric difference',
  'vessel.config.lock.locked': 'locked to a declared value',
  'vessel.config.lock.unlocked': 'not locked',
  'vessel.config.lock.undeclared': 'lock not declared',
  'vessel.config.note': 'Categorical rows are printed as before / after labels; only a physical quantity carries a numeric difference.',
} as const;

/** Every string the overview and composition can print. */
export type VesselOverviewKey = keyof typeof EN;

/** The shape both dictionaries must have. */
export type VesselOverviewDictionary = Readonly<Record<VesselOverviewKey, string>>;

const ZH: VesselOverviewDictionary = {
  'vessel.kicker': '舰船设计',
  'vessel.title': '舰船设计总览',
  'vessel.intro': '以一件设计呈现已确认草稿。每一节只陈述各自独立的事实；未声明的数值保持未知，任何一节都不声称设计已完整。',

  'vessel.state.pending': '仍有一处修改在确认中；确认完成前不显示总览事实。',
  'vessel.state.failed': '未能确认设计读数；不显示总览事实。',
  'vessel.state.absent': '该读数没有保存原生设计结果。',
  'vessel.state.schema': '该结果未声明受支持的原生结果形态，故不绘制总览。',
  'vessel.state.method': '该结果未声明受支持的原生设计方法，故不绘制总览。',
  'vessel.state.unavailable': '该结果不含可读取的原生分节。',
  'vessel.state.frozen': '冻结已保存结果的只读总览。',
  'vessel.context.draft': '已确认草稿 · 已保存修订 {revision}',

  'vessel.section.hull': '船体与主尺度',
  'vessel.section.freeboard': '干舷',
  'vessel.section.armament': '武备',
  'vessel.section.armour': '装甲',
  'vessel.section.propulsion': '动力',
  'vessel.section.weight': '重量与平衡',
  'vessel.open': '打开{chapter}',
  'vessel.unknown': '—',

  'vessel.fact.length': '水线长度',
  'vessel.fact.beam': '型宽',
  'vessel.fact.draught': '吃水（正常）',
  'vessel.fact.freeboard': '干舷',
  'vessel.fact.freeboardNote': '已保存的干舷读数。甲板分段占比与端点剖面在各自章节和冻结报告中展示。',
  'vessel.fact.batteryLine': '{calibre} · {barrels} 门炮 · {mounts} 座炮架',
  'vessel.fact.batteryNone': '未声明任何炮组。',
  'vessel.fact.batteryUnavailable': '炮组 {bank} 未声明。',
  'vessel.fact.armamentNote': '已声明的五个炮组，各自独立读取。炮组章节给出完整的两组构成及其来源估算。',
  'vessel.fact.beltMain': '主装甲带厚度',
  'vessel.fact.deck': '装甲甲板厚度',
  'vessel.fact.deckCoverage': '甲板覆盖',
  'vessel.fact.speedMax': '最大航速',
  'vessel.fact.speedCruise': '巡航航速',
  'vessel.fact.hpMax': '最大功率',
  'vessel.fact.range': '续航',
  'vessel.fact.fuel': '燃料',
  'vessel.fact.engine': '主机',
  'vessel.fact.drive': '传动',
  'vessel.fact.screws': '轴数',
  'vessel.fact.powerLock': '功率锁定',
  'vessel.fact.lockTarget': '锁定功率与载煤燃油',
  'vessel.fact.propulsionNote': '功率为来源马力，按原样显示，绝不改称。燃料、主机与传动均为已声明的选择，绝不臆测。',
  'vessel.fact.balanceSelected': '选取质量',
  'vessel.fact.balanceEstimate': '估算质量',
  'vessel.fact.balanceTarget': '目标排水量',
  'vessel.fact.balanceDifference': '平衡差额',
  'vessel.fact.ledgerGuns': '火炮',
  'vessel.fact.ledgerMounts': '炮座',
  'vessel.fact.ledgerAmmunition': '弹药',
  'vessel.fact.ledgerGunArmour': '火炮装甲',
  'vessel.fact.ledgerNote': '台账自身的全局角色质量，以吨存储，按所选质量单位显示。绝不按炮组拆分，也绝不计入来源估算。',
  'vessel.fact.selected': '选取',
  'vessel.fact.estimate': '估算',
  'vessel.fact.mode': '策略',
  'vessel.fact.noneSelected': '未选择',

  'armament.kicker': '武备构成',
  'armament.title': '武备构成',
  'armament.intro': '每个已声明炮组、其两个炮座组以及来源估算。选取只揭示一个炮组，绝不改变已保存声明。',

  'armament.state.pending': '仍有一处武备修改在确认中；确认完成前不显示构成或数字。',
  'armament.state.failed': '未能确认武备读数；不显示构成或数字。',
  'armament.state.absent': '该读数没有保存原生武备结果。',
  'armament.state.schema': '该结果未声明受支持的原生结果形态，故不绘制构成。',
  'armament.state.method': '该结果未声明受支持的原生设计方法，故不绘制构成。',
  'armament.state.unavailable': '该结果不含可读取的武备分节。',
  'armament.state.frozen': '冻结已保存结果的只读构成。',

  'armament.banks.title': '五个炮组',
  'armament.banks.note': '每个炮组各有其声明的编号；列表顺序绝不是其标识。缺失或声明含混的炮组视为不可用，绝不改派。',
  'armament.banks.list': '武备炮组',
  'armament.bank.label': '炮组 {bank}',
  'armament.bank.zero': '声明武备为零。',
  'armament.bank.missing': '未声明。',
  'armament.bank.ambiguous': '声明含混，因此本炮组不读取任何配置。',
  'armament.group.G1': '第 1 组',
  'armament.group.G2': '第 2 组',
  'armament.group.none': '未声明该组。',
  'armament.group.mounts': '{count} 座',
  'armament.group.mountsUnknown': '未声明炮座数',

  'armament.fact.barrels': '炮管',
  'armament.fact.mounts': '炮座总数',
  'armament.fact.calibre': '口径',
  'armament.fact.gunType': '火炮类型',
  'armament.fact.mountType': '炮座类型',
  'armament.fact.year': '年份',
  'armament.fact.calLength': '倍径',
  'armament.fact.magazine': '每炮备弹',
  'armament.fact.selector': '炮座选择器',
  'armament.fact.layout': '布置',
  'armament.fact.perMount': '每座炮管数',
  'armament.fact.groupMounts': '组内炮座',
  'armament.fact.elevated': '高置炮座',
  'armament.fact.deck': '甲板炮座',
  'armament.fact.depressed': '低置炮座',
  'armament.fact.face': '正面装甲',
  'armament.fact.side': '侧面 / 顶部装甲',
  'armament.fact.barbette': '炮座圈装甲',
  'armament.fact.shellDeclared': '声明弹重',
  'armament.fact.shellEffective': '有效弹重',
  'armament.fact.shellRecovered': '修正弹重',
  'armament.fact.broadside': '舷侧齐射重量',
  'armament.fact.gunWeight': '火炮质量（来源）',
  'armament.fact.mountWeight': '炮座质量（来源）',
  'armament.fact.magazineWeight': '弹药库质量（来源）',
  'armament.fact.armWeight': '炮座装甲质量（来源）',
  'armament.fact.totalWeight': '总质量（来源）',
  'armament.fact.estimateNote': '五项质量为来源自身返回的估算，以长吨存储，按所选质量单位显示。绝不重算，也绝不计入台账。',
  'armament.fact.weightUnits': '声明与有效弹重及舷侧齐射重量以磅计；五项质量估算以长吨存储，按所选质量单位显示。',
  'armament.fact.flagElevation': '已声明双层高置',
  'armament.fact.flagDepression': '已声明双层低置',
  'armament.fact.calibreLength': '{value} 倍径',
  'armament.count.invalid': '{value} —— 非整数计数',
  'armament.flags.unknown': '未声明',
  'armament.flags.none': '未声明任何一项',

  'armament.ledger.title': '全局台账质量',
  'armament.ledger.note': '受管台账所持的四个武备角色，以吨存储，按所选质量单位显示。它们属于全局：不存在按炮组的拆分，手动策略改动即使炮组配置未变也会在此呈现。',
  'armament.ledger.role.guns': '火炮',
  'armament.ledger.role.mounts': '炮座',
  'armament.ledger.role.ammunition': '弹药',
  'armament.ledger.role.gun_armour': '火炮装甲',
  'armament.ledger.mass': '选取 {selected} · 估算 {estimate} · 策略 {policy}',

  'armament.select.list': '选择炮组',
  'armament.select.hint': '在列表中选择一个炮组即可读取其配置与来源估算。选取保持键盘焦点，绝不改变声明。',
  'armament.select.edit': '编辑本炮组口径',
  'armament.select.editHint': '打开火炮字段组并聚焦本炮组的口径字段。',
  'armament.changed': '已变更',

  'armament.export.svg': '下载 SVG',
  'armament.export.png': '下载 PNG',
  'armament.export.svgError': '此浏览器未能下载 SVG，请重试。',
  'armament.export.pngError': '此浏览器未能生成 PNG；SVG 内容仍然完整。',

  'armament.legend.title': '图例',
  'armament.legend.battery': '一个已声明炮组，按其自身编号而非位置',
  'armament.legend.group': '一个炮座组；图形为有界示意，绝不表示布置位置',
  'armament.legend.unknown': '未声明（仅为示意）',
  'armament.legend.changed': '与已保存修订不同',
  'armament.legend.units': '口径与厚度以英寸和毫米计；弹重与舷侧齐射重量以磅计；来源质量估算以长吨存储；台账质量以吨存储。质量按所选质量单位显示。',

  'vessel.config.title': '配置变更',
  'vessel.config.intro': '五个炮组配置以及关键的船体、装甲与动力事实。方向为对比 − 当前，与旁边的读数表一致。',
  'vessel.config.current': '当前',
  'vessel.config.comparison': '对比',
  'vessel.config.metric': '事实',
  'vessel.config.difference': '差值',
  'vessel.config.group.battery': '炮组配置',
  'vessel.config.group.hull': '船体',
  'vessel.config.group.armour': '装甲',
  'vessel.config.group.propulsion': '动力',
  'vessel.config.battery': '炮组 {bank}',
  'vessel.config.unavailable': '未声明',
  'vessel.config.unchanged': '无变化',
  'vessel.config.categorical': '仅为标签，无数值差值',
  'vessel.config.lock.locked': '锁定为声明值',
  'vessel.config.lock.unlocked': '未锁定',
  'vessel.config.lock.undeclared': '未声明锁定',
  'vessel.config.note': '分类行以“前 / 后”标签呈现；只有物理量才带数值差值。',
};

/** The whole overview dictionary for one language. */
export function vesselOverviewDictionary(language: SiteLanguage): VesselOverviewDictionary {
  return language === 'zh-CN' ? ZH : EN;
}

/** One overview message, with its `{slot}`s filled; an unknown key returns the key. */
export function vesselOverviewCopy(language: SiteLanguage, key: VesselOverviewKey, params?: CopyParams): string {
  const text: string = (vesselOverviewDictionary(language) as Record<string, string>)[key] ?? key;
  return interpolate(text, params);
}

/** The overview lookup, bound to the shell's one language state. */
export function useVesselOverviewCopy(): (key: VesselOverviewKey, params?: CopyParams) => string {
  const { language } = useLanguage();
  return useCallback((key: VesselOverviewKey, params?: CopyParams) => vesselOverviewCopy(language, key, params), [language]);
}

/**
 * The localized ledger policy word, from the reading table's own policy labels.
 *
 * An absent or unrecognized policy stays "not set" rather than being read as an
 * estimate, and a policy that is neither estimated nor declared is named as
 * another policy. A policy-only change therefore stays visible even when the two
 * masses beside it are equal.
 */
export function ledgerPolicyLabel(language: SiteLanguage, mode: string | null | undefined): string {
  return mode === 'estimated' ? designFeedbackCopy(language, 'feedback.policy.estimated')
    : mode === 'declared' ? designFeedbackCopy(language, 'feedback.policy.declared')
      : mode ? designFeedbackCopy(language, 'feedback.policy.other')
        : designFeedbackCopy(language, 'feedback.policy.unknown');
}

/**
 * The static enum tables, from the source authority.
 *
 * The gun and mount types are `sship_fields.GUN_TYPES` and `MOUNT_TYPES`; the
 * nineteen arrangements are `sship_fields.LAYOUT_LABELS`, whose index 18 is the
 * explicit `None`; the fifteen selectors are `sps_gun_review.MOUNT_LABELS`; and
 * the fuel, engine and drive arrays follow the native boolean selectors. Every
 * table is a declaration list, so the reader never infers an option.
 */
export const GUN_TYPE_LABELS: Readonly<Record<SiteLanguage, readonly string[]>> = {
  en: ['Muzzle loading gun', 'Breech loading gun', 'Quick firing gun', 'Anti-air gun', 'Dual purpose gun', 'Auto rapid fire gun', 'Machine gun'],
  'zh-CN': ['前装炮', '后装炮', '速射炮', '高射炮', '两用炮', '自动速射炮', '机枪'],
};

export const MOUNT_TYPE_LABELS: Readonly<Record<SiteLanguage, readonly string[]>> = {
  en: ['in broadside mount', 'in Coles/Ericsson turret mount', 'in open barbette mount', 'in turret on barbette mount', 'in deck and hoist mount', 'in deck mount', 'in casemate mount'],
  'zh-CN': ['舷侧炮座', '科尔斯/埃里克森炮塔', '露天炮座', '炮塔-炮座', '甲板与扬弹机炮座', '甲板炮座', '炮廓炮座'],
};

export const LAYOUT_LABELS: Readonly<Record<SiteLanguage, readonly string[]>> = {
  en: [
    'Centreline - distributed', 'Centreline - ends (fore >= aft)', 'Centreline - ends (aft >= fore)',
    'Centreline - fore deck forward', 'Centreline - fore deck', 'Centreline - fore deck aft',
    'Centreline - aft deck forward', 'Centreline - aft deck', 'Centreline - aft deck aft',
    'Sides - distributed', 'Sides - ends (fore >= aft)', 'Sides - ends (aft >= fore)',
    'Sides - fore deck forward', 'Sides - fore deck', 'Sides - fore deck aft',
    'Sides - aft deck forward', 'Sides - aft deck', 'Sides - aft deck aft', 'None',
  ],
  'zh-CN': [
    '中线——分布', '中线——两端（前 ≥ 后）', '中线——两端（后 ≥ 前）',
    '中线——前甲板前部', '中线——前甲板', '中线——前甲板后部',
    '中线——后甲板前部', '中线——后甲板', '中线——后甲板后部',
    '两舷——分布', '两舷——两端（前 ≥ 后）', '两舷——两端（后 ≥ 前）',
    '两舷——前甲板前部', '两舷——前甲板', '两舷——前甲板后部',
    '两舷——后甲板前部', '两舷——后甲板', '两舷——后甲板后部', '无（未设置）',
  ],
};

export const SELECTOR_LABELS: Readonly<Record<SiteLanguage, readonly string[]>> = {
  en: ['Single mount', '2 row twin mount', '4 row quad mount', 'Twin mount', '2-gun mount', '2 row quad mount', 'Triple mount', '3-gun mount', '2 row sextuple mount', 'Quad mount', '4-gun mount', '2 row octuple mount', 'Quintuple mount', '5-gun mount', '2 row decuple mount'],
  'zh-CN': ['单装', '双联装（2 排）', '四联装（4 排）', '双联装', '双炮装', '四联装（2 排）', '三联装', '三炮装', '六联装（2 排）', '四联装', '四炮装', '八联装（2 排）', '五联装', '五炮装', '十联装（2 排）'],
};

export const FUEL_LABELS: Readonly<Record<SiteLanguage, readonly string[]>> = {
  en: ['Coal fired boilers', 'Oil fired boilers', 'Diesel motors', 'Petrol motors', 'Batteries'],
  'zh-CN': ['燃煤锅炉', '燃油锅炉', '柴油机', '汽油机', '蓄电池'],
};

export const ENGINE_LABELS: Readonly<Record<SiteLanguage, readonly string[]>> = {
  en: ['Simple reciprocating', 'Compound reciprocating', 'Steam turbine'],
  'zh-CN': ['往复式（单级）', '往复式（复式）', '蒸汽轮机'],
};

export const DRIVE_LABELS: Readonly<Record<SiteLanguage, readonly string[]>> = {
  en: ['Direct', 'Geared', 'Electric', 'Hydraulic'],
  'zh-CN': ['直接驱动', '齿轮传动', '电力传动', '液压传动'],
};

/** The four armament ledger roles, in the source's own order. */
export const ARMAMENT_LEDGER_KEYS = ['guns', 'mounts', 'ammunition', 'gun_armour'] as const;
export type ArmamentLedgerKey = typeof ARMAMENT_LEDGER_KEYS[number];

/** The label table a labelled enum index reads from. */
export type VesselLabelTable = 'gunType' | 'mountType' | 'layout' | 'selector' | 'fuel' | 'engine' | 'drive' | 'deckCoverage';

/** One label by table name and index, or `null` when the index is not one of the table's. */
export function vesselLabel(language: SiteLanguage, table: VesselLabelTable, index: number | null): string | null {
  if (index === null || !Number.isInteger(index) || index < 0) return null;
  if (table === 'deckCoverage') return deckCoverageLabel(language, index);
  const lists: Record<Exclude<VesselLabelTable, 'deckCoverage'>, readonly string[]> = {
    gunType: GUN_TYPE_LABELS[language], mountType: MOUNT_TYPE_LABELS[language],
    layout: LAYOUT_LABELS[language], selector: SELECTOR_LABELS[language],
    fuel: FUEL_LABELS[language], engine: ENGINE_LABELS[language], drive: DRIVE_LABELS[language],
  };
  const list = lists[table];
  return index < list.length ? list[index] : null;
}
