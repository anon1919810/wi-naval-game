import { useCallback } from 'react';
import { useLanguage } from '../portfolio/LanguageProvider';
import { interpolate } from './terms';
import type { CopyParams, SiteLanguage } from '../portfolio/LanguageProvider';

/**
 * The propulsion and performance dictionary.
 *
 * Two ordinary chapters share one reading: the engine chapter states the
 * declared fuel → engine → drive → shaft chain, the source speed, power, range,
 * coal share and bunker weights and the two whole-ship machinery and fuel ledger
 * roles; the performance chapter states the source empirical stability, hull
 * strength and seakeeping readings with the source's own warning and rating
 * flags. The vocabulary keeps three things separate that must never be merged:
 *
 * - Source horsepower, nautical miles and long tons are the source's own units
 *   and are never relabelled. Only the ledger masses are tonnes.
 * - A source flag that is false says that one flag only and is never a general
 *   pass; an unknown flag is never printed as a "no", and no threshold is
 *   restated here — the source owns it.
 * - The empirical stability height and the roll period keep the units the source
 *   saved; they are screens, never a modern metacentric height or a safety
 *   certificate.
 *
 * English is the source and the Chinese side is shape-checked against it, the
 * same arrangement every other dictionary here uses.
 */
const EN = {
  'propulsion.kicker': 'PROPULSION & ENDURANCE',
  'propulsion.title': 'Propulsion and endurance',
  'propulsion.intro': 'The declared fuel, engine, drive and shaft chain, the source speed, power, range, coal share and bunker facts, the declared power lock and the two whole-ship machinery and fuel ledger roles. Nothing here is recomputed.',

  'propulsion.state.pending': 'A propulsion edit is still being confirmed; no facts are shown until it settles.',
  'propulsion.state.failed': 'The propulsion reading could not be confirmed; no facts are shown.',
  'propulsion.state.absent': 'No native design result is saved for this reading.',
  'propulsion.state.schema': 'This result does not declare the supported native result shape, so no propulsion facts are read.',
  'propulsion.state.method': 'This result does not declare the supported native design method, so no propulsion facts are read.',
  'propulsion.state.unavailable': 'This result carries no readable engine or performance section.',
  'propulsion.state.frozen': 'Read-only propulsion reading of the frozen saved result.',

  'propulsion.declaration.title': 'Declared chain',
  'propulsion.declaration.fuel': 'Fuel',
  'propulsion.declaration.engine': 'Engines',
  'propulsion.declaration.drive': 'Drive',
  'propulsion.declaration.screws': 'Shafts',
  'propulsion.declaration.note': 'Fuel, engine and drive are the saved selector declarations; a row that is not declared stays unknown and is never guessed. The shaft count is the declared whole number of shafts.',

  'propulsion.fact.speedMax': 'Maximum speed',
  'propulsion.fact.speedCruise': 'Cruise speed',
  'propulsion.fact.hpMax': 'Maximum power',
  'propulsion.fact.hpCruise': 'Cruise power',
  'propulsion.fact.range': 'Endurance range',
  'propulsion.fact.screws': 'Shafts',
  'propulsion.fact.pctCoal': 'Coal share',
  'propulsion.fact.bunker': 'Bunker at normal load',
  'propulsion.fact.bunkerMax': 'Bunker at maximum load',
  'propulsion.fact.engineWeight': 'Machinery mass (source)',
  'propulsion.fact.units': 'Speed follows the reader\'s chosen unit. Power is the source horsepower, range the source nautical miles and the source machinery mass and bunker weights the source long tons; each is shown as saved and never relabelled. The source machinery mass is the engine page\'s own figure, separate from the whole-ship ledger masses in tonnes below.',

  'propulsion.lock.title': 'Declared power lock',
  'propulsion.lock.locked': 'Power is locked to a declared value.',
  'propulsion.lock.unlocked': 'Power is not locked; the source solver derives it.',
  'propulsion.lock.undeclared': 'The lock declaration is not saved for this result, so it stays unknown.',
  'propulsion.lock.powerHp': 'Locked power',
  'propulsion.lock.bunkerLt': 'Locked bunker',
  'propulsion.lock.note': 'The existing recalculate-power-and-speed button calls the source solver; a saved lock is a declaration and not a promise that this screen re-solves live. An undeclared locked value is never shown as zero.',

  'propulsion.ledger.title': 'Whole-ship machinery and fuel',
  'propulsion.ledger.note': 'The two whole-ship roles as the managed ledger holds them, in tonnes. They are global: no per-engine or per-fuel-type split exists, and a manual policy change appears here even when the declared chain is unchanged.',
  'propulsion.ledger.role.machinery': 'Machinery',
  'propulsion.ledger.role.fuel': 'Fuel',
  'propulsion.ledger.mass': '{selected} selected · {estimate} estimate · policy {policy}',
  'propulsion.ledger.unbound': 'This role has no binding yet; its masses stay as the ledger reports them.',

  'propulsion.edit.speed': 'Reveal the speed fields',
  'propulsion.edit.range': 'Reveal the range field',
  'propulsion.edit.screws': 'Reveal the shaft-count field',
  'propulsion.edit.coal': 'Reveal the coal-share field',

  'performance.kicker': 'PERFORMANCE SCREENS',
  'performance.title': 'Stability, strength and seakeeping',
  'performance.intro': 'The source empirical stability, hull strength and seakeeping readings, by group and in the units the source saved. These are the method\'s own screens, not a modern metacentric height and not a safety certificate.',

  'performance.state.pending': 'A performance edit is still being confirmed; no readings are shown until it settles.',
  'performance.state.failed': 'The performance reading could not be confirmed; no readings are shown.',
  'performance.state.absent': 'No native design result is saved for this reading.',
  'performance.state.schema': 'This result does not declare the supported native result shape, so no performance facts are read.',
  'performance.state.method': 'This result does not declare the supported native design method, so no performance facts are read.',
  'performance.state.unavailable': 'This result carries no readable performance section.',
  'performance.state.frozen': 'Read-only performance reading of the frozen saved result.',

  'performance.group.stability': 'Stability',
  'performance.group.strength': 'Hull strength',
  'performance.group.seakeeping': 'Seakeeping',

  'performance.fact.stability': 'Stability',
  'performance.fact.stabilityAdj': 'Adjusted stability',
  'performance.fact.metacentre': 'Metacentric height (source estimate)',
  'performance.fact.rollPeriod': 'Roll period',
  'performance.fact.strengthCross': 'Transverse strength',
  'performance.fact.strengthLong': 'Longitudinal strength',
  'performance.fact.strengthComp': 'Overall strength (composite)',
  'performance.fact.seaboat': 'Seaboat',
  'performance.fact.seakeeping': 'Seakeeping',
  'performance.fact.steadiness': 'Steadiness',
  'performance.fact.steadinessAdj': 'Adjusted steadiness',
  'performance.fact.units': 'Strength and the stability, seaboat, steadiness and seakeeping terms are the source\'s empirical scores. The metacentric height is the source\'s own empirically derived height in feet and the roll period is in seconds; neither is converted.',

  'performance.flags.title': 'Source verdicts',
  'performance.flags.intro': 'The source\'s own warning and rating flags, exactly as saved. A false flag is that one flag only and never a general pass; an unknown flag is not a "no". These thresholds live in the source and are never redefined here.',
  'performance.flags.tenderWarn': 'Tender warning',
  'performance.flags.capsizeWarn': 'Capsize warning',
  'performance.flags.steady': 'Steady gun platform',
  'performance.flags.unsteady': 'Unsteady',
  'performance.flags.badSea': 'Bad seaboat',
  'performance.flags.poorSea': 'Poor seaboat',
  'performance.flags.goodSea': 'Good seaboat',
  'performance.flags.fineSea': 'Excellent seaboat',
  'performance.flag.true': 'triggered',
  'performance.flag.false': 'not triggered',

  'performance.note': 'Performance is affected by the declared hull, freeboard, armour, armament, weight and trim; these readings point at related inputs and never promise that raising one value fixes a result.',
  'performance.related.title': 'Related inputs',
  'performance.related.note': 'Orientation only: open a chapter to see an input that bears on these readings, or reveal the trim field. Nothing here changes a declaration.',
  'performance.related.trim': 'Reveal the trim field',
  'performance.related.open': 'Open {chapter}',
} as const;

/** Every string the two propulsion and performance readers can print. */
export type PropulsionPerformanceKey = keyof typeof EN;

/** The shape both dictionaries must have. */
export type PropulsionPerformanceDictionary = Readonly<Record<PropulsionPerformanceKey, string>>;

const ZH: PropulsionPerformanceDictionary = {
  'propulsion.kicker': '动力与续航',
  'propulsion.title': '动力与续航',
  'propulsion.intro': '已声明的燃料、主机、传动与轴数链，来源航速、功率、航程、煤比例与载煤燃油事实，已声明的功率锁定，以及两条全舰机械与燃料台账角色。此处不做任何重算。',

  'propulsion.state.pending': '仍有一处动力修改在确认中；确认完成前不显示任何事实。',
  'propulsion.state.failed': '未能确认动力读数；不显示任何事实。',
  'propulsion.state.absent': '该读数没有保存原生设计结果。',
  'propulsion.state.schema': '该结果未声明受支持的原生结果形态，故不读取动力事实。',
  'propulsion.state.method': '该结果未声明受支持的原生设计方法，故不读取动力事实。',
  'propulsion.state.unavailable': '该结果不含可读取的发动机或性能分节。',
  'propulsion.state.frozen': '冻结已保存结果的只读动力读数。',

  'propulsion.declaration.title': '已声明链条',
  'propulsion.declaration.fuel': '燃料',
  'propulsion.declaration.engine': '主机',
  'propulsion.declaration.drive': '传动',
  'propulsion.declaration.screws': '轴数',
  'propulsion.declaration.note': '燃料、主机与传动为已保存的选择器声明；未声明的行保持未知，绝不臆测。轴数为已声明的整数轴数。',

  'propulsion.fact.speedMax': '最大航速',
  'propulsion.fact.speedCruise': '巡航航速',
  'propulsion.fact.hpMax': '最大功率',
  'propulsion.fact.hpCruise': '巡航功率',
  'propulsion.fact.range': '续航里程',
  'propulsion.fact.screws': '轴数',
  'propulsion.fact.pctCoal': '煤比例',
  'propulsion.fact.bunker': '正常载煤燃油',
  'propulsion.fact.bunkerMax': '最大载煤燃油',
  'propulsion.fact.engineWeight': '机械质量（来源）',
  'propulsion.fact.units': '航速按读者所选单位显示。功率为来源马力，航程为来源海里，来源机械质量与载煤燃油均为来源长吨；各自按原样显示，绝不改称。来源机械质量为发动机页面自身数值，与下方以吨计的全舰台账质量彼此独立。',

  'propulsion.lock.title': '已声明的功率锁定',
  'propulsion.lock.locked': '功率已锁定为一个声明的值。',
  'propulsion.lock.unlocked': '功率未锁定；由来源求解器推导。',
  'propulsion.lock.undeclared': '该结果未保存锁定声明，故保持未知。',
  'propulsion.lock.powerHp': '锁定功率',
  'propulsion.lock.bunkerLt': '锁定载煤燃油',
  'propulsion.lock.note': '现有“重算功率与航速”按钮调用来源求解器；已保存的锁定是一项声明，并不承诺本界面实时求解。未声明的锁定值绝不显示为零。',

  'propulsion.ledger.title': '全舰机械与燃料',
  'propulsion.ledger.note': '受管台账所持的两条全舰角色，以吨计。它们属于全局：不存在按主机或燃料类型的拆分，手动策略改动即使已声明链条未变也会在此呈现。',
  'propulsion.ledger.role.machinery': '机械',
  'propulsion.ledger.role.fuel': '燃料',
  'propulsion.ledger.mass': '选取 {selected} · 估算 {estimate} · 策略 {policy}',
  'propulsion.ledger.unbound': '该角色尚未绑定；其质量照台账所报显示。',

  'propulsion.edit.speed': '揭示航速字段',
  'propulsion.edit.range': '揭示航程字段',
  'propulsion.edit.screws': '揭示轴数字段',
  'propulsion.edit.coal': '揭示煤比例字段',

  'performance.kicker': '性能筛查',
  'performance.title': '稳性、强度与适航性',
  'performance.intro': '来源经验稳性、船体强度与适航性读数，按组展示，并保留来源自身单位。它们是方法自身的筛查，不是现代初稳性高，也不是安全认证。',

  'performance.state.pending': '仍有一处性能修改在确认中；确认完成前不显示任何读数。',
  'performance.state.failed': '未能确认性能读数；不显示任何读数。',
  'performance.state.absent': '该读数没有保存原生设计结果。',
  'performance.state.schema': '该结果未声明受支持的原生结果形态，故不读取性能事实。',
  'performance.state.method': '该结果未声明受支持的原生设计方法，故不读取性能事实。',
  'performance.state.unavailable': '该结果不含可读取的性能分节。',
  'performance.state.frozen': '冻结已保存结果的只读性能读数。',

  'performance.group.stability': '稳性',
  'performance.group.strength': '船体强度',
  'performance.group.seakeeping': '适航性',

  'performance.fact.stability': '稳性',
  'performance.fact.stabilityAdj': '修正稳性',
  'performance.fact.metacentre': '初稳性高（来源推算）',
  'performance.fact.rollPeriod': '横摇周期',
  'performance.fact.strengthCross': '横向强度',
  'performance.fact.strengthLong': '纵向强度',
  'performance.fact.strengthComp': '总体强度（复合值）',
  'performance.fact.seaboat': '耐波性',
  'performance.fact.seakeeping': '适航性',
  'performance.fact.steadiness': '平稳度',
  'performance.fact.steadinessAdj': '修正平稳度',
  'performance.fact.units': '强度与稳性、耐波性、平稳度、适航性各项均为来源经验得分。初稳性高为来源自身经验推算的高度，以英尺计；横摇周期以秒计；两者均不换算。',

  'performance.flags.title': '来源判词',
  'performance.flags.intro': '来源自身的警告与评级标记，按保存原样呈现。false 仅表示该一项，绝不构成总体通过；未知同样不是“否”。这些阈值属于来源，此处绝不重新定义。',
  'performance.flags.tenderWarn': '易倾警告',
  'performance.flags.capsizeWarn': '倾覆警告',
  'performance.flags.steady': '稳定炮台',
  'performance.flags.unsteady': '不稳定',
  'performance.flags.badSea': '耐波性差',
  'performance.flags.poorSea': '耐波性欠佳',
  'performance.flags.goodSea': '耐波性良好',
  'performance.flags.fineSea': '耐波性极佳',
  'performance.flag.true': '已触发',
  'performance.flag.false': '未触发',

  'performance.note': '性能受已声明的船体、干舷、装甲、武备、重量与 trim 影响；这些读数指向相关输入，绝不承诺调大某一数值即可解决。',
  'performance.related.title': '相关输入',
  'performance.related.note': '仅为定位：打开某一章节查看与这些读数相关的输入，或揭示 trim 字段。此处不更改任何声明。',
  'performance.related.trim': '揭示 trim 字段',
  'performance.related.open': '打开{chapter}',
};

/** The whole propulsion/performance dictionary for one language. */
export function propulsionPerformanceDictionary(language: SiteLanguage): PropulsionPerformanceDictionary {
  return language === 'zh-CN' ? ZH : EN;
}

/** One message, with its `{slot}`s filled; an unknown key returns the key. */
export function propulsionPerformanceCopy(language: SiteLanguage, key: PropulsionPerformanceKey, params?: CopyParams): string {
  const text: string = (propulsionPerformanceDictionary(language) as Record<string, string>)[key] ?? key;
  return interpolate(text, params);
}

/** The lookup, bound to the shell's one language state. */
export function usePropulsionPerformanceCopy(): (key: PropulsionPerformanceKey, params?: CopyParams) => string {
  const { language } = useLanguage();
  return useCallback((key: PropulsionPerformanceKey, params?: CopyParams) => propulsionPerformanceCopy(language, key, params), [language]);
}
