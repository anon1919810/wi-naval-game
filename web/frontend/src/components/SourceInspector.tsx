import type { AnalysisResult } from '../types';

export function SourceInspector({ result }: { result: AnalysisResult }) {
  return <aside className="report-sources" aria-label="报告来源与适用性">
    <span className="section-kicker">TRACE / 审计信息</span>
    <h2>从哪里来</h2>
    <dl><dt>项目输入指纹</dt><dd><code>{result.project_fingerprint}</code></dd>
      <dt>所选工况指纹</dt><dd><code>{result.input_fingerprint}</code></dd>
      <dt>请求指纹</dt><dd><code>{result.request_fingerprint}</code></dd>
      <dt>计算完整性</dt><dd>{result.validity.complete ? '所请求阶段已完成' : '存在未完成阶段'}</dd>
      <dt>史实验证</dt><dd>{result.validity.historical_validated === true ? '已声明验证' : '未验证 / 无结论'}</dd></dl>
    <details><summary>来源声明</summary><pre>{JSON.stringify(result.sources, null, 2)}</pre></details>
    <details><summary>方法版本</summary><pre>{JSON.stringify(result.method_versions, null, 2)}</pre></details>
    <p className="source-footnote">计算状态只表示模型执行情况；不代表史实、设计或适航认证。</p>
  </aside>;
}
