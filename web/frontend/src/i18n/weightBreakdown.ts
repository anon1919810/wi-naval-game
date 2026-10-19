import { useCallback } from 'react';

import { useLanguage } from '../portfolio/LanguageProvider';
import { interpolate } from './terms';
import type { CopyParams, SiteLanguage } from '../portfolio/LanguageProvider';

/**
 * The managed weight breakdown dictionary.
 *
 * The weight reader explains what the saved ledger already contains: each role's
 * own source estimate and adopted mass, how the six presentation groups add up,
 * and where the authoritative balance comes from. Four distinctions are kept in
 * the words themselves:
 *
 * - A group whose roles are not all known has an unknown total, never a partial
 *   subtotal dressed up as the group's own sum.
 * - A saved zero or a negative mass is a fact; a missing one is unknown.
 * - A repeated role identity is one conflict, not two readings and not a sum.
 * - The balance figures are read from the ledger's own four totals, never rebuilt
 *   from the group sums.
 *
 * The same dictionary carries the report's local print-scope words, so the two
 * report scopes are named once and read the same way on screen and on paper.
 */
const EN = {
  'weight.kicker': 'MANAGED WEIGHT LEDGER',
  'weight.title': 'Weight and role breakdown',
  'weight.intro': 'Every managed role\'s own source estimate and adopted mass, read from the saved ledger. The six groups below are the reading\'s own presentation; the authoritative balance above them is read, never rebuilt from these sums.',

  'weight.state.pending': 'A weight edit is still being confirmed; no breakdown is shown until it settles.',
  'weight.state.failed': 'The weight reading could not be confirmed; no breakdown is shown.',
  'weight.state.absent': 'No native design result is saved for this reading.',
  'weight.state.schema': 'This result does not declare the supported native result shape, so no ledger is read.',
  'weight.state.method': 'This result does not declare the supported native design method, so no ledger is read.',
  'weight.state.unavailable': 'This result carries no readable ledger, so no residual weight is shown.',
  'weight.state.frozen': 'Read-only weight breakdown of the frozen saved result.',

  'weight.unknown': '—',
  'weight.changed': 'changed',

  'weight.mode.estimated': 'estimated',
  'weight.mode.declared': 'declared',
  'weight.mode.none': 'no policy',
  'weight.estimate': 'Source estimate',
  'weight.selected': 'Adopted mass',
  'weight.adoption': 'Adopted − estimate',
  'weight.items': 'Items',

  'weight.group.structure': 'Structure',
  'weight.group.armament': 'Armament',
  'weight.group.armour': 'Fixed armour',
  'weight.group.machinery': 'Machinery',
  'weight.group.fuel': 'Fuel',
  'weight.group.other': 'Stores and other',

  'weight.groups.title': 'Role groups',
  'weight.groups.note': 'Each group is the sum of its own roles, dimension by dimension: a known adopted sum stands even when an estimate is unknown, and the other way round. An empty group is not a zero. A group that is missing an expected role is incomplete even when every role it carries is known.',
  'weight.groups.empty': 'No role of this group is in the saved ledger.',
  'weight.groups.incomplete': 'This group is not complete: a role is unknown, conflicting, or missing, so at least one group dimension stays unknown.',
  'weight.group.missing': 'Missing expected roles: {roles}',
  'weight.group.estimate': 'Group estimate',
  'weight.group.selected': 'Group adopted',

  'weight.roles.title': 'Roles in this group',
  'weight.role.items': 'Items',
  'weight.role.none': 'No item',
  'weight.role.optional': 'Optional, no binding required',
  'weight.role.conflict.title': 'Role conflict',
  'weight.role.conflict.note': 'This source identity is saved more than once. Its estimate, adopted mass, policy, binding and difference cannot be determined, and its group total stays unknown. The saved ledger is still auditable below.',
  'weight.role.absent': 'Not in the saved ledger',

  'weight.chart.title': 'Estimate and adopted mass',
  'weight.chart.legend.estimate': 'Source estimate',
  'weight.chart.legend.selected': 'Adopted mass',
  'weight.chart.note': 'Both bars start at the zero line, so a saved negative reads to the left and a saved zero is a real zero. A value the ledger does not declare is shown as unknown and draws no bar.',
  'weight.chart.unknown': 'unknown',

  'weight.select.list': 'Weight groups',
  'weight.select.hint': 'Select a group to open its role readings. Selection only reads the saved result and never writes the design.',
  'weight.reveal': 'Reveal the binding',
  'weight.reveal.hint': 'This opens the existing binding form and focuses its control; it does not change any value.',
  'weight.noReveal': 'This role has no binding control to open.',

  'weight.balance.title': 'Authoritative balance',
  'weight.balance.selected': 'Selected mass',
  'weight.balance.estimate': 'Estimated mass',
  'weight.balance.target': 'Target displacement',
  'weight.balance.difference': 'Balance difference',
  'weight.balance.adoption': 'Selected − estimated',
  'weight.balance.estimateVsTarget': 'Estimated − target',
  'weight.balance.note': 'The four totals are the saved ledger\'s own figures. The two contrasts are explanation only; the balance difference stays exactly the value the ledger saved.',
  'weight.reconcile.sum': 'Determinate role sums',
  'weight.reconcile.balance': 'Ledger balance',
  'weight.reconcile.estimate': 'Estimate',
  'weight.reconcile.selected': 'Adopted',
  'weight.reconcile.match': 'The determinate role sums agree with the ledger balance.',
  'weight.reconcile.mismatch': 'The determinate role sums do not agree with the ledger balance; the ledger balance is authoritative and stands.',
  'weight.reconcile.partial': 'At least one role is unknown or conflicting, so the role sums cannot be checked against the ledger balance.',
  'weight.complete': 'Every role is bound',
  'weight.complete.unknown': 'The saved result does not declare whether every role is bound.',
  'weight.incomplete': 'Some roles still need binding',
  'weight.unresolved': '{count} role(s) still need binding',
  'weight.other.note': 'The optional other classification carries no source estimate and needs no binding; it is not a missing role.',
  'weight.units.note': 'All masses are the ledger\'s own tonnes and follow the reader\'s mass display preference. Source long tons are not mixed into this ledger.',

  'weight.context': 'Context',
  'weight.run': 'Run',
  'weight.basis': 'Basis',

  'weight.comparison.title': 'Frozen role comparison',
  'weight.comparison.intro': 'Every role of both frozen runs, in one ordered union: each side\'s own estimate, adopted mass, policy and binding, with the difference stated as comparison − current. A policy or binding change is a categorical change, never a mass difference.',
  'weight.comparison.metric': 'Role',
  'weight.comparison.current': 'Current',
  'weight.comparison.comparison': 'Comparison',
  'weight.comparison.delta': 'Difference',
  'weight.comparison.estimate': 'Estimate',
  'weight.comparison.selected': 'Adopted',
  'weight.comparison.mode': 'Policy',
  'weight.comparison.binding': 'Binding',
  'weight.comparison.roleAbsent': 'Not in this run\'s ledger',
  'weight.comparison.conflict': 'role conflict',
  'weight.comparison.changed': 'changed',
  'weight.comparison.direction': 'Difference is comparison − current',
  'weight.comparison.incompatible': 'Both results are readable, but they do not share one known basis, so no role difference is stated.',
  'weight.comparison.note': 'A difference is shown only when both sides declare the role and both values are known. A known value that became unknown is a change with an unknown difference; two unknowns are not a change.',

  'print.scope.kicker': 'PRINT SCOPE',
  'print.scope.design': 'Design report',
  'print.scope.full': 'Full report',
  'print.scope.designHint': 'The readable native design, its diagnostics and the requested physical results. The duplicate original text, native key audit and source appendix are left off the paper.',
  'print.scope.fullHint': 'The whole report, including the saved source and method appendix and the original report text.',
  'print.scope.note': 'The scope affects paper only. The screen, the stored snapshot and the downloads stay complete, and no project is changed.',
  'print.scope.pdf': 'Print / Save as PDF',

  'print.identity.kicker': 'REPORT IDENTITY',
  'print.identity.method': 'Method {value}',
  'print.identity.designMethod': 'Design method {value}',
  'print.identity.request': 'Request {value}',
  'print.identity.run': 'Run {value}',
  'print.identity.revision': 'Revision {value}',
  'print.identity.basis': 'Basis {value}',
  'print.identity.unset': '—',
} as const;

/** Every string the weight reader and the report scope control can print. */
export type WeightBreakdownKey = keyof typeof EN;

/** The shape both dictionaries must have. */
export type WeightBreakdownDictionary = Readonly<Record<WeightBreakdownKey, string>>;

const ZH: WeightBreakdownDictionary = {
  'weight.kicker': '受管重量台账',
  'weight.title': '重量与角色构成',
  'weight.intro': '每个受管角色的来源估重与实际采用质量，均读自已保存台账。下方六个分组是本读数自身的呈现方式；其上的权威平衡是读来的，绝不从这些合计重建。',

  'weight.state.pending': '仍有一处重量修改在确认中；确认完成前不显示构成。',
  'weight.state.failed': '未能确认重量读数；不显示构成。',
  'weight.state.absent': '该读数没有保存原生设计结果。',
  'weight.state.schema': '该结果未声明受支持的原生结果形态，故不读取台账。',
  'weight.state.method': '该结果未声明受支持的原生设计方法，故不读取台账。',
  'weight.state.unavailable': '该结果不含可读取台账，故不显示任何残留重量。',
  'weight.state.frozen': '冻结已保存结果的只读重量构成。',

  'weight.unknown': '—',
  'weight.changed': '有变化',

  'weight.mode.estimated': '估算',
  'weight.mode.declared': '声明',
  'weight.mode.none': '无策略',
  'weight.estimate': '来源估重',
  'weight.selected': '采用质量',
  'weight.adoption': '采用−估重',
  'weight.items': '项目',

  'weight.group.structure': '结构',
  'weight.group.armament': '武备',
  'weight.group.armour': '固定装甲',
  'weight.group.machinery': '机械',
  'weight.group.fuel': '燃料',
  'weight.group.other': '储备与其他',

  'weight.groups.title': '角色分组',
  'weight.groups.note': '每个分组按各自维度求和：估重未知时已知采用合计仍成立，反之亦然。空组不等于零。缺少应有角色的分组即使所载角色全部已知也属不完整。',
  'weight.groups.empty': '该分组没有已保存台账角色。',
  'weight.groups.incomplete': '该分组不完整：有角色未知、冲突或缺失，故至少一个分组维度保持未知。',
  'weight.group.missing': '缺少应有角色：{roles}',
  'weight.group.estimate': '分组估重',
  'weight.group.selected': '分组采用',

  'weight.roles.title': '本组角色',
  'weight.role.items': '项目',
  'weight.role.none': '无项目',
  'weight.role.optional': '可选，无需绑定',
  'weight.role.conflict.title': '角色冲突',
  'weight.role.conflict.note': '该来源身份被保存了不止一次。其估重、采用质量、策略、绑定与差值均不可确定，所属组合计保持未知。完整原始台账仍可在下方审计。',
  'weight.role.absent': '不在已保存台账中',

  'weight.chart.title': '估重与采用质量',
  'weight.chart.legend.estimate': '来源估重',
  'weight.chart.legend.selected': '采用质量',
  'weight.chart.note': '两条条带均从零线起算：已保存的负值向左延伸，已保存的零是真正的零。台账未声明的取值显示为未知，不绘制条带。',
  'weight.chart.unknown': '未知',

  'weight.select.list': '重量分组',
  'weight.select.hint': '选择分组以打开其角色读数。选择只读取已保存结果，绝不写入设计。',
  'weight.reveal': '揭示原绑定',
  'weight.reveal.hint': '此处只打开已有绑定表单并聚焦其控件，不更改任何数值。',
  'weight.noReveal': '该角色没有可打开的绑定控件。',

  'weight.balance.title': '权威平衡',
  'weight.balance.selected': '选取质量',
  'weight.balance.estimate': '估算质量',
  'weight.balance.target': '目标排水量',
  'weight.balance.difference': '平衡差额',
  'weight.balance.adoption': '选取−估算',
  'weight.balance.estimateVsTarget': '估算−目标',
  'weight.balance.note': '四项总额均来自已保存台账自身。两处对照仅用于解释；平衡差额始终显示台账保存的原值。',
  'weight.reconcile.sum': '可确定的角色合计',
  'weight.reconcile.balance': '台账平衡',
  'weight.reconcile.estimate': '估重',
  'weight.reconcile.selected': '采用',
  'weight.reconcile.match': '可确定的角色合计与台账平衡一致。',
  'weight.reconcile.mismatch': '可确定的角色合计与台账平衡不一致；台账平衡为权威，保持不变。',
  'weight.reconcile.partial': '至少有一个角色未知或冲突，故无法用台账平衡核对角色合计。',
  'weight.complete': '所有角色均已绑定',
  'weight.complete.unknown': '已保存结果未声明是否所有角色均已绑定。',
  'weight.incomplete': '仍有角色需要绑定',
  'weight.unresolved': '仍有 {count} 个角色需要绑定',
  'weight.other.note': '可选的其它载荷没有来源估重，也无需绑定；它不是缺失角色。',
  'weight.units.note': '所有质量均为台账自身的吨值，并随读者所选质量显示偏好呈现。来源长吨不混入本台账。',

  'weight.context': '上下文',
  'weight.run': '运行',
  'weight.basis': '基准',

  'weight.comparison.title': '冻结角色对照',
  'weight.comparison.intro': '两次冻结运行的全部角色，按一个有序并集列出：各自的估重、采用质量、策略与绑定，差值表述为对照−当前。策略或绑定变化是类别变化，绝不伪装成质量差。',
  'weight.comparison.metric': '角色',
  'weight.comparison.current': '当前',
  'weight.comparison.comparison': '对照',
  'weight.comparison.delta': '差值',
  'weight.comparison.estimate': '估重',
  'weight.comparison.selected': '采用',
  'weight.comparison.mode': '策略',
  'weight.comparison.binding': '绑定',
  'weight.comparison.roleAbsent': '不在该运行的台账中',
  'weight.comparison.conflict': '角色冲突',
  'weight.comparison.changed': '有变化',
  'weight.comparison.direction': '差值为对照−当前',
  'weight.comparison.incompatible': '两份结果均可读取，但不共享同一已知基准，故不陈述角色差值。',
  'weight.comparison.note': '仅当两侧都声明该角色且两侧取值均已知时才显示差值。已知转未知计为变化但差值未知；两个未知不算变化。',

  'print.scope.kicker': '打印范围',
  'print.scope.design': '设计报告',
  'print.scope.full': '完整报告',
  'print.scope.designHint': '可读原生设计、其诊断与被请求的物理结果。重复的原格式文本、原生键值审计与来源附录不上纸。',
  'print.scope.fullHint': '整份报告，包括已保存的来源与方法附录以及原报告文本。',
  'print.scope.note': '范围只影响纸面。屏幕、已存快照与下载保持完整，且不更改任何项目。',
  'print.scope.pdf': '打印／保存为 PDF',

  'print.identity.kicker': '报告身份',
  'print.identity.method': '方法 {value}',
  'print.identity.designMethod': '设计方法 {value}',
  'print.identity.request': '请求 {value}',
  'print.identity.run': '运行号 {value}',
  'print.identity.revision': '修订 {value}',
  'print.identity.basis': '基准 {value}',
  'print.identity.unset': '—',
};

/** The whole weight-breakdown dictionary for one language. */
export function weightBreakdownDictionary(language: SiteLanguage): WeightBreakdownDictionary {
  return language === 'zh-CN' ? ZH : EN;
}

/** One message, with its `{slot}`s filled; an unknown key returns the key. */
export function weightBreakdownCopy(language: SiteLanguage, key: WeightBreakdownKey, params?: CopyParams): string {
  const text: string = (weightBreakdownDictionary(language) as Record<string, string>)[key] ?? key;
  return interpolate(text, params);
}

/** The lookup, bound to the shell's one language state. */
export function useWeightBreakdownCopy(): (key: WeightBreakdownKey, params?: CopyParams) => string {
  const { language } = useLanguage();
  return useCallback((key: WeightBreakdownKey, params?: CopyParams) => weightBreakdownCopy(language, key, params), [language]);
}
