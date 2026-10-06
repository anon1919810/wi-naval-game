import { useMemo } from 'react';

import { estimateLabel, provenanceGroups } from './sourceAudit';
import type { AnalysisResult } from '../types';

/**
 * The audit trail at the end of the report.
 *
 * It sits inside the report body rather than in a third rail: at 1440 and 1024
 * a permanent side column would cost the reading column more than it gives. The
 * applicability flags stay in view because they decide how the numbers above may
 * be read; the long material — fingerprints, the saved sources, the method
 * versions and the provenance of every declared field — folds, and printing
 * opens it.
 *
 * The provenance appendix is walked from the saved payload rather than described,
 * and only when it is needed: a result can carry a very large payload, so it is
 * mounted when the reader opens it or when the report is printed. It says what
 * the payload declares and nothing more; it is not a claim of historical
 * confirmation.
 */
function triState(value: boolean | null | undefined): string {
  return value === true ? '是 · 已声明' : value === false ? '否' : '未知 · 无结论';
}

export function SourceInspector({ result, deferred = false, onOpen }: {
  result: AnalysisResult; deferred?: boolean; onOpen?: () => void;
}) {
  const groups = useMemo(() => (deferred ? provenanceGroups(result) : []), [deferred, result]);
  const paths = groups.reduce((total, group) => total + group.paths.length, 0);
  const requested = Object.values(result.stages ?? {}).filter(stage => stage?.requested === true).length;
  return <section className="report-sources report-audit" aria-label="报告来源与适用性">
    <div className="section-heading"><h2>审计信息</h2><span>适用性 · 指纹 · 来源声明</span></div>
    <dl className="report-audit-facts">
      <dt>计算完整性</dt><dd>{result.validity.complete ? '所请求阶段已完成' : '存在未完成阶段'}</dd>
      <dt>收敛</dt><dd>{triState(result.validity.converged)}</dd>
      <dt>模型适用性</dt><dd>{triState(result.validity.model_applicable)}</dd>
      <dt>史实验证</dt><dd>{triState(result.validity.historical_validated)}</dd>
      <dt>所请求阶段</dt><dd>{requested} 个</dd>
      {/* The request fingerprint identifies this report and stays in view; the
          two long input fingerprints fold. */}
      <dt>请求指纹</dt><dd><code>{result.request_fingerprint}</code></dd>
    </dl>
    <details className="report-audit-fold"><summary>完整指纹与请求身份</summary>
      <dl className="report-audit-facts">
        <dt>项目输入指纹</dt><dd><code>{result.project_fingerprint}</code></dd>
        <dt>所选工况指纹</dt><dd><code>{result.input_fingerprint}</code></dd>
        <dt>项目</dt><dd><code>{result.project_id}</code></dd>
        <dt>工况</dt><dd><code>{result.condition_id}</code></dd>
      </dl>
    </details>
    <details className="report-audit-fold"><summary>保存的来源声明与限制</summary>
      <pre>{JSON.stringify(result.sources, null, 2)}</pre>
    </details>
    <details className="report-audit-fold"><summary>方法版本</summary>
      <pre>{JSON.stringify(result.method_versions, null, 2)}</pre>
    </details>
    {/* The walk is deferred on purpose: it reads the saved payload, which is
        large. The summary is always there so a reader can ask for it, and the
        content is mounted when they open it or when the report is printed. */}
    <details className="report-audit-fold report-provenance"
      onToggle={event => { if (event.currentTarget.open) onOpen?.(); }}>
      <summary>{deferred ? `来源声明附录 · ${groups.length} 组 / ${paths} 处声明` : '来源声明附录 · 按需生成'}</summary>
      {deferred && (groups.length === 0
        ? <p className="report-audit-empty">本次保存结果没有声明任何来源字段。</p>
        : groups.map(group => <details className="report-audit-group" key={group.key}>
          <summary><span className="report-audit-declaration">{group.text}</span>
            <span className="report-audit-estimate">{estimateLabel(group.estimate)}</span>
            <span className="report-audit-count">{group.paths.length} 处</span></summary>
          <ul className="report-audit-paths">{group.paths.map(path => <li key={path}><code>{path}</code></li>)}</ul>
        </details>))}
    </details>
    <p className="source-footnote">计算状态只表示模型执行情况；不代表史实、设计或适航认证。来源声明说明数字来自哪里，不等于已经过史实验证。</p>
  </section>;
}