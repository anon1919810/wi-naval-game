import { useCallback } from 'react';
import { useLanguage } from '../portfolio/LanguageProvider';
import { interpolate } from './terms';
import type { CopyParams, SiteLanguage } from '../portfolio/LanguageProvider';

/**
 * The draft feedback dictionary: the words the comparison panel needs, and only
 * those.
 *
 * The panel is one surface with two readings of the same nine paragraphs — the
 * workbench compares the draft against the saved revision, the report compares
 * a frozen comparison run against the frozen current run. Both directions are
 * named in words rather than only in a column heading, because the two signs
 * must never be read as each other.
 *
 * English is the source and the Chinese side is shape-checked against it, the
 * same arrangement the workspace and laboratory dictionaries use. The stability
 * paragraph states its own name: the source method's empirical screen, never a
 * metacentric height.
 */
const EN = {
  'feedback.kicker': 'DESIGN FEEDBACK',
  'feedback.title': 'Draft against the saved revision',
  'feedback.intro': 'What the draft changed and how the readings moved. Observed changes only: this is not a sensitivity analysis and not evidence of cause.',

  'feedback.frozen.title': 'Native design summary',
  'feedback.frozen.intro': 'The frozen native readings of both runs, compared exactly as saved. No live preview is read and nothing is recomputed.',
  'feedback.frozen.current': 'Current run',
  'feedback.frozen.comparison': 'Comparison run',
  'feedback.frozen.revision': 'revision {revision}',

  'feedback.direction.draft': 'Difference: draft − saved',
  'feedback.direction.frozen': 'Difference: comparison − current',

  'feedback.reading.metric': 'Reading',
  'feedback.reading.before': 'Saved',
  'feedback.reading.after': 'Draft',
  'feedback.reading.beforeFrozen': 'Current',
  'feedback.reading.afterFrozen': 'Comparison',
  'feedback.reading.delta': 'Difference',

  'feedback.baseline.loading': 'Reading the saved revision…',
  'feedback.baseline.failed': 'The saved revision could not be read.',
  'feedback.baseline.absent': 'This saved revision declares no ship design yet, so the draft has no saved baseline to differ from.',
  'feedback.baseline.empty': 'The saved revision returned no native preview to compare against.',
  'feedback.baseline.retry': 'Read the saved revision again',

  'feedback.current.pending': 'An edit is still being confirmed; the current readings are withheld until it settles.',
  'feedback.current.failed': 'A ship-design edit did not confirm; the current readings are withheld.',
  'feedback.current.empty': 'The draft has no confirmed native preview yet.',

  'feedback.incompatible.schema': 'The two results are not the same native result shape; numeric differences are withheld.',
  'feedback.incompatible.method': 'The two results do not both declare the supported native design method; numeric differences are withheld.',
  'feedback.incompatible.status': 'A result does not declare a readable status (available or partial), so its residual numbers are withheld.',
  'feedback.incompatible.basis': 'The two results do not both declare the same known basis condition; numeric differences are withheld.',
  'feedback.incompatible.project': 'The two sides do not belong to the same project; numeric differences are withheld.',

  'feedback.frozen.currentUnreadable': 'The current run has no readable native design stage; numeric differences are withheld.',
  'feedback.frozen.comparisonUnreadable': 'The comparison run has no readable native design stage; numeric differences are withheld.',
  'feedback.frozen.schema': "A run's native stage does not declare the supported result shape; numeric differences are withheld.",
  'feedback.frozen.method': "A run's native stage does not declare the supported design method, or its declared kernel identity disagrees with its payload; numeric differences are withheld.",
  'feedback.frozen.status': "A run's native result does not declare a readable status (available or partial); its residual numbers are withheld.",
  'feedback.frozen.snapshot': "A run's saved input snapshot does not belong to that run's project; numeric differences are withheld.",
  'feedback.frozen.identity': "A run's saved envelope does not agree with its own result; numeric differences are withheld.",
  'feedback.frozen.optionalScope': 'The two runs requested different optional physical stages; the native readings are still compared, but those physical results differ in scope.',

  'feedback.reading.selectedMass': 'Selected mass',
  'feedback.reading.estimatedMass': 'Source estimated mass',
  'feedback.reading.targetDisplacement': 'Target displacement',
  'feedback.reading.difference': 'Balance gap',
  'feedback.reading.speedMax': 'Maximum speed',
  'feedback.reading.speedCruise': 'Cruise speed',
  'feedback.reading.powerMax': 'Source horsepower',
  'feedback.reading.powerCruise': 'Source cruise horsepower',
  'feedback.reading.range': 'Endurance range',
  'feedback.reading.stability': 'Source empirical stability (not a metacentric height)',
  'feedback.reading.metacentre': 'Source metacentric height (empirical, not a GM)',
  'feedback.reading.rollPeriod': 'Roll period',
  'feedback.reading.hullStrength': 'Source hull strength (composite, relative)',
  'feedback.reading.hullStrengthCross': 'Source transverse strength (relative)',
  'feedback.reading.hullStrengthLong': 'Source longitudinal strength (relative)',
  'feedback.reading.seakeeping': 'Source seakeeping (empirical)',

  'feedback.reason.beforeUnknown': 'The saved reading is missing or not a finite number.',
  'feedback.reason.afterUnknown': 'The draft reading is missing or not a finite number.',
  'feedback.reason.bothUnknown': 'Both readings are missing or not finite.',

  'feedback.zeroBaseline': 'the baseline is zero — absolute change only',
  'feedback.percentOf': '{value}% of the baseline',

  'feedback.inputs.title': 'Changed design inputs',
  'feedback.inputs.none': 'No declared input changed.',
  'feedback.inputs.count': '{count} declared inputs changed',
  'feedback.inputs.more': 'Show {count} more',
  'feedback.inputs.less': 'Show fewer',
  'feedback.inputs.unit': 'unit {unit}',
  'feedback.inputs.unitChanged': 'unit changed: {before} → {after}',
  'feedback.inputs.open': 'Open {chapter}',

  'feedback.roles.title': 'Changed ledger roles',
  'feedback.roles.none': 'No ledger role or policy changed.',
  'feedback.roles.count': '{count} ledger roles changed',
  'feedback.roles.selected': 'Selected mass',
  'feedback.roles.estimate': 'Source estimate',
  'feedback.policy.estimated': 'estimated',
  'feedback.policy.declared': 'declared (manual)',
  'feedback.policy.other': 'other policy',
  'feedback.policy.unknown': 'not set',
  'feedback.roles.more': 'Show {count} more roles',
  'feedback.roles.less': 'Show fewer roles',
  'feedback.roles.observed': 'Observed ledger changes, including manual (declared) mass. Not a sensitivity analysis and not proof of causation.',
} as const;

/** Every string the draft feedback panel can print. */
export type DesignFeedbackKey = keyof typeof EN;

/** The shape both dictionaries must have. */
export type DesignFeedbackDictionary = Readonly<Record<DesignFeedbackKey, string>>;

const ZH: DesignFeedbackDictionary = {
  'feedback.kicker': '设计反馈',
  'feedback.title': '草稿与已保存修订的对比',
  'feedback.intro': '草稿改动了什么，读数又移动了多少。这里只陈述观察到的变化：它不是敏感性分析，也不构成因果证据。',

  'feedback.frozen.title': '原生设计摘要',
  'feedback.frozen.intro': '按保存原样对比两次运行的冻结原生读数。不读取任何实时预览，也不重新计算。',
  'feedback.frozen.current': '当前运行',
  'feedback.frozen.comparison': '对照运行',
  'feedback.frozen.revision': '修订 {revision}',

  'feedback.direction.draft': '差值：草稿 − 已保存',
  'feedback.direction.frozen': '差值：对照 − 当前',

  'feedback.reading.metric': '读数',
  'feedback.reading.before': '已保存',
  'feedback.reading.after': '草稿',
  'feedback.reading.beforeFrozen': '当前',
  'feedback.reading.afterFrozen': '对照',
  'feedback.reading.delta': '差值',

  'feedback.baseline.loading': '正在读取已保存修订…',
  'feedback.baseline.failed': '未能读取已保存修订。',
  'feedback.baseline.absent': '该已保存修订尚未声明舰船设计，因此草稿没有可对比的已保存基线。',
  'feedback.baseline.empty': '已保存修订未返回可用于对比的原生预览。',
  'feedback.baseline.retry': '重新读取已保存修订',

  'feedback.current.pending': '仍有一处修改在确认中；确认完成前不显示当前读数。',
  'feedback.current.failed': '有一处舰船设计修改未确认；因此不显示当前读数。',
  'feedback.current.empty': '草稿尚无已确认的原生预览。',

  'feedback.incompatible.schema': '两项结果的原生结果形态不同，故不给出数值差值。',
  'feedback.incompatible.method': '两项结果并非都声明受支持的原生设计方法，故不给出数值差值。',
  'feedback.incompatible.status': '有一项结果未声明可读取的状态（available 或 partial），故不给出其残留数值。',
  'feedback.incompatible.basis': '两项结果并非都声明同一个已知基准工况，故不给出数值差值。',
  'feedback.incompatible.project': '两侧不属于同一个项目，故不给出数值差值。',

  'feedback.frozen.currentUnreadable': '当前运行没有可读取的原生设计阶段，故不给出数值差值。',
  'feedback.frozen.comparisonUnreadable': '对照运行没有可读取的原生设计阶段，故不给出数值差值。',
  'feedback.frozen.schema': '某次运行的原生阶段未声明受支持的结果形态，故不给出数值差值。',
  'feedback.frozen.method': '某次运行的原生阶段未声明受支持的设计方法，或其声明的内核身份与载荷不一致，故不给出数值差值。',
  'feedback.frozen.status': '某次运行的原生结果未声明可读取的状态（available 或 partial），故不给出其残留数值。',
  'feedback.frozen.snapshot': '某次运行保存的输入快照不属于该运行的项目，故不给出数值差值。',
  'feedback.frozen.identity': '某次运行保存的信封与其自身结果不一致，故不给出数值差值。',
  'feedback.frozen.optionalScope': '两次运行请求的可选物理阶段不同；原生读数仍照常对比，但这些物理结果的范围不同。',

  'feedback.reading.selectedMass': '选取质量',
  'feedback.reading.estimatedMass': '来源估算质量',
  'feedback.reading.targetDisplacement': '目标排水量',
  'feedback.reading.difference': '平衡差额',
  'feedback.reading.speedMax': '最大航速',
  'feedback.reading.speedCruise': '巡航航速',
  'feedback.reading.powerMax': '来源马力',
  'feedback.reading.powerCruise': '来源巡航马力',
  'feedback.reading.range': '续航里程',
  'feedback.reading.stability': '来源经验稳性（非初稳性高）',
  'feedback.reading.metacentre': '来源初稳性高（经验推算，非 GM）',
  'feedback.reading.rollPeriod': '横摇周期',
  'feedback.reading.hullStrength': '来源船体强度（复合值，相对）',
  'feedback.reading.hullStrengthCross': '来源横向强度（相对）',
  'feedback.reading.hullStrengthLong': '来源纵向强度（相对）',
  'feedback.reading.seakeeping': '来源适航性（经验）',

  'feedback.reason.beforeUnknown': '已保存读数为缺失或非有限数。',
  'feedback.reason.afterUnknown': '草稿读数为缺失或非有限数。',
  'feedback.reason.bothUnknown': '两侧读数均为缺失或非有限数。',

  'feedback.zeroBaseline': '左列基准值为零，仅显示绝对变化',
  'feedback.percentOf': '为左列基准值的 {value}%',

  'feedback.inputs.title': '改动的设计输入',
  'feedback.inputs.none': '没有声明的输入发生变化。',
  'feedback.inputs.count': '{count} 项声明输入发生变化',
  'feedback.inputs.more': '再显示 {count} 项',
  'feedback.inputs.less': '收起',
  'feedback.inputs.unit': '单位 {unit}',
  'feedback.inputs.unitChanged': '单位已变更：{before} → {after}',
  'feedback.inputs.open': '打开{chapter}',

  'feedback.roles.title': '改动的台账角色',
  'feedback.roles.none': '没有台账角色或策略发生变化。',
  'feedback.roles.count': '{count} 个台账角色发生变化',
  'feedback.roles.selected': '选取质量',
  'feedback.roles.estimate': '来源估算',
  'feedback.policy.estimated': '估算',
  'feedback.policy.declared': '声明（手动）',
  'feedback.policy.other': '其他策略',
  'feedback.policy.unknown': '未设置',
  'feedback.roles.more': '再显示 {count} 个角色',
  'feedback.roles.less': '收起',
  'feedback.roles.observed': '台账中观察到的变化，含手动（声明）质量。它不是敏感性分析，也不构成因果证据。',
};

/** The whole feedback dictionary for one language. */
export function designFeedbackDictionary(language: SiteLanguage): DesignFeedbackDictionary {
  return language === 'zh-CN' ? ZH : EN;
}

/**
 * One feedback message, with its `{slot}`s filled.
 *
 * An unknown key returns the key itself, as in every other dictionary here.
 */
export function designFeedbackCopy(language: SiteLanguage, key: DesignFeedbackKey, params?: CopyParams): string {
  const text: string = (designFeedbackDictionary(language) as Record<string, string>)[key] ?? key;
  return interpolate(text, params);
}

/** The feedback lookup, bound to the shell's one language state. */
export function useDesignFeedbackCopy(): (key: DesignFeedbackKey, params?: CopyParams) => string {
  const { language } = useLanguage();
  return useCallback((key: DesignFeedbackKey, params?: CopyParams) => designFeedbackCopy(language, key, params), [language]);
}
