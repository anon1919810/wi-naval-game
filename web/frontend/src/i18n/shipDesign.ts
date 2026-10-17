import { useCallback } from 'react';

import { useLanguage, type CopyParams, type SiteLanguage } from '../portfolio/LanguageProvider';
import { interpolate } from './terms';

/**
 * The native ship-design dictionary.
 *
 * The ordinary workbench hosts the native fields on its own chapters, so the
 * words here are the ones the native host adds — the design's own notes and
 * source, its basis condition, the managed ledger and the explicit bindings —
 * and the words the native report readings add, because those readings are the
 * same declaration's frozen result. The recovered source-field labels still come
 * from `./sps3b3`, because they are the same fields under the same names.
 *
 * English is the source; Chinese is shape-checked against it by the type system,
 * keys are dotted and flat, and interpolation is the shell's `{slot}` rule.
 */

const EN = {
  'shipDesign.title': 'Ship design',
  'shipDesign.projectName': 'Project name',
  'shipDesign.kicker': 'SHIP DESIGN',
  'shipDesign.intro': 'Edit hull, armament and machinery in one design. Weight estimates and balance update with each confirmed change.',
  'shipDesign.empiricalNote': 'Performance is estimated from the design parameters. Declared mass differences appear in the balance; detailed physical checks require positions and hull geometry.',
  'shipDesign.formatHint': 'Original-format exports contain the original parameters and their empirical report. Use the project JSON backup to retain the full ledger, bindings and loading conditions.',

  'shipDesign.setup.title': 'Ship design setup',
  'shipDesign.setup.hint': 'This project declares no ship design yet. Starting one adds the design to the draft; the physical project is untouched until you save.',
  'shipDesign.setup.fresh': 'Start a fresh ship design',
  'shipDesign.setup.import': 'Import an original source (.sship / .dat / 2.0 or 3.0)',
  'shipDesign.setup.fromMigration': 'Build from this project’s migration archive',
  'shipDesign.setup.noMigration': 'This project holds no migration archive.',
  'shipDesign.setup.replace': 'Replace the design from a source file…',
  'shipDesign.setup.importHint': 'The file is loaded as a draft. Saving creates a new revision; an existing original-file archive stays unchanged.',
  'shipDesign.setup.pending': 'Reading the design…',
  'shipDesign.setup.enabled': 'Ship design declared',

  'shipDesign.source': 'Design source',
  'shipDesign.sourcePlaceholder': 'Where this declaration comes from — your own words',
  'shipDesign.notes': 'Appended report notes',
  'shipDesign.notesHint': 'Added to the ship-design report only; the migration original is not changed.',
  'shipDesign.condition': 'Design basis condition',
  'shipDesign.conditionHint': 'This balance uses the named design condition. Other loading conditions remain separate.',
  'shipDesign.conditionUnset': 'No basis condition declared',

  'shipDesign.pending': '{count} ship-design edit(s) are still being confirmed. Saving and running stay blocked until they settle.',
  'shipDesign.blocked': 'Save and run are blocked while ship-design edits are still being confirmed.',
  'shipDesign.failed': 'A ship-design edit failed to confirm: {message}',

  'shipDesign.ledger.title': 'Weight and design balance',
  'shipDesign.ledger.positions': 'Item positions and sources',
  'shipDesign.ledger.positionsHint': 'Supplement the same ledger with positions and source records for detailed physical checks.',
  'shipDesign.ledger.intro': 'Weights are counted once. Use binding settings to keep a declared mass or adopt an estimate.',
  'shipDesign.ledger.optional': 'Not configured (optional)',
  'shipDesign.ledger.role': 'Role',
  'shipDesign.ledger.estimate': 'Estimate',
  'shipDesign.ledger.selected': 'Selected',
  'shipDesign.ledger.target': 'Target',
  'shipDesign.ledger.difference': 'Difference',
  'shipDesign.ledger.mode': 'Mode',
  'shipDesign.ledger.mode.estimated': 'Estimated',
  'shipDesign.ledger.mode.declared': 'Declared',
  'shipDesign.ledger.items': 'Owned items',
  'shipDesign.ledger.none': 'No ledger yet. Preview or run the design to read it.',
  'shipDesign.ledger.needsBinding': 'Needs binding',
  'shipDesign.ledger.complete': 'Every role is bound.',
  'shipDesign.ledger.incomplete': 'Some roles are still unbound.',
  'shipDesign.ledger.unboundItems': 'Unbound ledger items: {items}',
  'shipDesign.ledger.unresolved': '{count} role(s) still need a binding.',
  'shipDesign.ledger.roleTable': 'Every design role at a glance; the binding forms below are collapsed.',
  'shipDesign.ledger.tonnes': 't',

  'shipDesign.balance.title': 'Unified balance',
  'shipDesign.balance.basis': 'Basis condition {condition}',

  'shipDesign.bind.title': 'Bind',
  'shipDesign.bind.summary': 'Bindings and declared masses ({count} roles)',
  'shipDesign.bind.intro': 'Choose which ledger items belong to each role and whether to use an estimate or a declared mass. Each item is counted once.',
  'shipDesign.bind.items': 'Ledger items',
  'shipDesign.bind.mass': 'Declared mass (t, optional)',
  'shipDesign.bind.massHint': 'Only for an additional existing payload whose role differs from the estimated one.',
  'shipDesign.bind.apply': 'Bind role',
  'shipDesign.bind.problem.empty': 'Choose at least one ledger item.',
  'shipDesign.bind.problem.estimated_multiple': 'An estimated role owns exactly one item. Choose one, or switch the mode to declared.',
  'shipDesign.bind.problem.already_bound': 'An item already belongs to another role. Change that role’s selection first.',

  'shipDesign.declared.title': 'Declared mass',
  'shipDesign.declared.hint': 'Only a role bound in declared mode may carry an explicit mass. Switch the binding to declared first.',
  'shipDesign.declared.disabled': 'Estimated mass is the product’s own; switch the binding to declared to edit it.',
  'shipDesign.declared.set': 'Set',

  'shipDesign.reading.selectedMass': 'Design selected mass',
  'shipDesign.reading.estimatedMass': 'Design estimated mass',
  'shipDesign.reading.targetDisplacement': 'Design target displacement',
  'shipDesign.reading.difference': 'Design mass difference',
  'shipDesign.reading.speedMax': 'Maximum design speed',
  'shipDesign.reading.powerMax': 'Maximum source power',
  'shipDesign.reading.range': 'Design range',
  'shipDesign.reading.stability': 'Design stability score',
  'shipDesign.reading.basisNote': 'design basis {condition}',
  'shipDesign.reading.reason.notNative': 'This saved design stage carries no native method result this reading can be taken from',
  'shipDesign.reading.reason.identity': 'The saved design method version does not match the version this reading declares',
} as const;

/** Every string the native ship-design host can print. */
export type ShipDesignKey = keyof typeof EN;

/** The shape the Chinese dictionary must have. */
export type ShipDesignDictionary = Readonly<Record<ShipDesignKey, string>>;

const ZH: ShipDesignDictionary = {
  'shipDesign.title': '舰船设计',
  'shipDesign.projectName': '项目名称',
  'shipDesign.kicker': '舰船设计',
  'shipDesign.intro': '在同一份设计中编辑船体、武备与动力。每次确认修改后，估重与设计平衡一起更新。',
  'shipDesign.empiricalNote': '性能按设计参数估算。人工质量差额在平衡中列出；详细物理检查需补齐位置与型线。',
  'shipDesign.formatHint': '原版格式导出保存原参数及其经验报告；完整台账、绑定和载荷工况请使用项目 JSON 备份。',

  'shipDesign.setup.title': '舰船设计初始化',
  'shipDesign.setup.hint': '本工程尚未声明舰船设计。开始即把设计加入草稿；在保存之前，物理工程不受影响。',
  'shipDesign.setup.fresh': '新建一份舰船设计',
  'shipDesign.setup.import': '导入原始文件（.sship / .dat / 2.0 或 3.0）',
  'shipDesign.setup.fromMigration': '从本工程的迁移归档构建',
  'shipDesign.setup.noMigration': '本工程没有迁移归档。',
  'shipDesign.setup.replace': '用源文件替换设计…',
  'shipDesign.setup.importHint': '文件先作为草稿载入，保存后形成新修订；已有原文件归档不变。',
  'shipDesign.setup.pending': '正在读取设计…',
  'shipDesign.setup.enabled': '已声明舰船设计',

  'shipDesign.source': '设计来源',
  'shipDesign.sourcePlaceholder': '这份声明来自哪里——用你自己的话',
  'shipDesign.notes': '追加报告注释',
  'shipDesign.notesHint': '仅加入舰船设计报告；迁移原文不变。',
  'shipDesign.condition': '设计基准工况',
  'shipDesign.conditionHint': '此处平衡按所标注的设计工况计算，其他载荷工况分别保留。',
  'shipDesign.conditionUnset': '未声明基准工况',

  'shipDesign.pending': '还有 {count} 项舰船设计修改正在确认；在它们全部落定前，保存与运行保持禁用。',
  'shipDesign.blocked': '舰船设计修改仍在确认期间，保存与运行被禁用。',
  'shipDesign.failed': '一项舰船设计修改未能确认：{message}',

  'shipDesign.ledger.title': '重量与设计平衡',
  'shipDesign.ledger.positions': '条目位置与来源',
  'shipDesign.ledger.positionsHint': '为同一份台账补充位置与来源记录，用于详细物理检查。',
  'shipDesign.ledger.intro': '各项重量只计一次。可在绑定设置中保留人工质量，或采用估重。',
  'shipDesign.ledger.optional': '未配置（可选）',
  'shipDesign.ledger.role': '角色',
  'shipDesign.ledger.estimate': '估算',
  'shipDesign.ledger.selected': '已选',
  'shipDesign.ledger.target': '目标',
  'shipDesign.ledger.difference': '差额',
  'shipDesign.ledger.mode': '模式',
  'shipDesign.ledger.mode.estimated': '估算',
  'shipDesign.ledger.mode.declared': '声明',
  'shipDesign.ledger.items': '归属条目',
  'shipDesign.ledger.none': '暂无台账。预览或运行该设计后读取。',
  'shipDesign.ledger.needsBinding': '待绑定',
  'shipDesign.ledger.complete': '全部角色均已绑定。',
  'shipDesign.ledger.incomplete': '仍有角色未绑定。',
  'shipDesign.ledger.unboundItems': '未绑定的台账条目：{items}',
  'shipDesign.ledger.unresolved': '仍有 {count} 个角色待绑定。',
  'shipDesign.ledger.roleTable': '一眼看尽每个设计角色；下方的绑定表单默认折叠。',
  'shipDesign.ledger.tonnes': '吨',

  'shipDesign.balance.title': '统一平衡',
  'shipDesign.balance.basis': '基准工况 {condition}',

  'shipDesign.bind.title': '绑定',
  'shipDesign.bind.summary': '绑定与声明质量（{count} 个角色）',
  'shipDesign.bind.intro': '选择各角色对应的台账条目，并决定采用估算值还是人工质量。每项重量只计入一次。',
  'shipDesign.bind.items': '台账条目',
  'shipDesign.bind.mass': '声明质量（吨，可选）',
  'shipDesign.bind.massHint': '仅用于角色与估算不同的一项额外既有载荷。',
  'shipDesign.bind.apply': '绑定角色',
  'shipDesign.bind.problem.empty': '请至少选择一个台账条目。',
  'shipDesign.bind.problem.estimated_multiple': '估算角色只拥有一个条目。请只选一个，或把模式切换为声明。',
  'shipDesign.bind.problem.already_bound': '该条目已归属另一角色，请先修改该角色的条目选择。',

  'shipDesign.declared.title': '声明质量',
  'shipDesign.declared.hint': '只有以声明模式绑定的角色才能携带显式质量；请先把绑定切换为声明。',
  'shipDesign.declared.disabled': '估算质量由产品自己拥有；把绑定切换为声明后方可编辑。',
  'shipDesign.declared.set': '设定',

  'shipDesign.reading.selectedMass': '设计已选质量',
  'shipDesign.reading.estimatedMass': '设计估算质量',
  'shipDesign.reading.targetDisplacement': '设计目标排水量',
  'shipDesign.reading.difference': '设计质量差额',
  'shipDesign.reading.speedMax': '设计最大航速',
  'shipDesign.reading.powerMax': '最大源功率',
  'shipDesign.reading.range': '设计续航',
  'shipDesign.reading.stability': '设计稳性评分',
  'shipDesign.reading.basisNote': '设计基准 {condition}',
  'shipDesign.reading.reason.notNative': '本次保存的设计阶段未给出可用于该读数的原生方法结果',
  'shipDesign.reading.reason.identity': '保存的设计方法版本与本次读数声明的版本不一致',
};

/**
 * The curated label of each native design role, as the core names it.
 *
 * These are the core's own role identifiers, mapped to words a reader uses —
 * never the identifiers themselves, and never a second vocabulary invented here.
 * A role the core reports that is not listed falls back to its own id.
 */
const ROLE_LABELS: Readonly<Record<string, readonly [string, string]>> = {
  structure: ['Hull structure', '船体结构'],
  guns: ['Guns', '火炮'],
  mounts: ['Mounts', '炮架'],
  gun_armour: ['Gun armour', '炮座装甲'],
  ammunition: ['Ammunition', '弹药'],
  machinery: ['Machinery', '动力机械'],
  fuel: ['Fuel', '燃料'],
  stores: ['Stores', '储备'],
  auxiliary: ['Auxiliary', '辅助载荷'],
  belt_main: ['Main belt armour', '主装甲带'],
  belt_ends: ['Belt ends', '装甲带端部'],
  belt_upper: ['Upper belt armour', '上装甲带'],
  bulkhead: ['Bulkheads', '舱壁'],
  bulge: ['Bulges', '防雷隔舱'],
  deck: ['Deck armour', '甲板装甲'],
  conning: ['Conning tower', '指挥塔'],
  misc_vital: ['Misc. vital', '杂项关键'],
  misc_hull: ['Misc. hull', '杂项船体'],
  misc_deck: ['Misc. deck', '杂项甲板'],
  misc_above: ['Misc. above water', '杂项水上'],
  misc_void: ['Misc. void', '杂项空舱'],
  other: ['Other payload', '其它载荷'],
};

/** The reader-facing label of one core role, in one language. */
export function shipDesignRoleLabel(language: SiteLanguage, role: string): string {
  const pair = ROLE_LABELS[role];
  if (!pair) return role;
  return language === 'zh-CN' ? pair[1] : pair[0];
}

/** The role-label lookup bound to the shell's one language state. */
export function useShipDesignRoleLabel(): (role: string) => string {
  const { language } = useLanguage();
  return useCallback((role: string) => shipDesignRoleLabel(language, role), [language]);
}

/** One native ship-design message in one language, with its `{slot}`s filled. */
export function shipDesignCopy(language: SiteLanguage, key: ShipDesignKey, params?: CopyParams): string {
  const dictionary: ShipDesignDictionary = language === 'zh-CN' ? ZH : EN;
  return interpolate((dictionary as Record<string, string>)[key] ?? key, params);
}

/** The native ship-design lookup bound to the shell's one language state. */
export function useShipDesignCopy(): (key: ShipDesignKey, params?: CopyParams) => string {
  const { language } = useLanguage();
  return useCallback((key: ShipDesignKey, params?: CopyParams) => shipDesignCopy(language, key, params),
    [language]);
}
