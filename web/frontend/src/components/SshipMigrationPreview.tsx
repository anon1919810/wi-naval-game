import type {
  ProjectDiagnostic, SshipMigration, SshipMigrationField, SshipProjectImportPreview,
} from '../types';
import type { WorkspaceKey } from '../i18n/workspace';

/**
 * What one SpringSharp 3.0 source file contains, before anything is saved.
 *
 * The reader of a `.sship` file is deciding whether to trust a conversion, so
 * this is a description of the file rather than a claim about a ship: the
 * version and header the server actually accepted, the digest of the bytes that
 * will be sent, how the 280 positional fields were disposed of, the geometry the
 * new project does and does not have, and the limits the migration itself
 * reported.
 *
 * Two rules are load-bearing. Every value is rendered as React text — a field
 * name or a diagnostic message is somebody else's file content and is never
 * interpreted as markup. And the disclosures are disclosures: 280 field records
 * and the canonical validator's own warnings are evidence a reader may want,
 * but they are not what most readers need before confirming.
 */

const DISPOSITION_LABEL: Record<string, WorkspaceKey> = {
  mapped: 'sship.field.disposition.mapped',
  preserved: 'sship.field.disposition.preserved',
  duplicate: 'sship.field.disposition.duplicate',
  reserved: 'sship.field.disposition.reserved',
};

/** Counts in the order a reader asks about them: what is used, what is kept. */
const COUNT_ROWS: ReadonlyArray<{ key: string; label: WorkspaceKey }> = [
  { key: 'mapped', label: 'sship.count.mapped' },
  { key: 'preserved', label: 'sship.count.preserved' },
  { key: 'duplicate', label: 'sship.count.duplicate' },
  { key: 'reserved', label: 'sship.count.reserved' },
];

type Copy = (key: WorkspaceKey, params?: Record<string, string | number>) => string;

/** A migration limit, whether the core sent it as a sentence or as a finding. */
function limitationText(limitation: SshipMigration['limitations'][number]): string | null {
  if (typeof limitation === 'string') return limitation;
  if (!limitation || typeof limitation !== 'object') return null;
  return limitation.message ?? null;
}

function MigrationFinding({ diagnostic, w }: { diagnostic: ProjectDiagnostic; w: Copy }) {
  return <li className="project-import-finding">
    <span className="project-import-finding-severity" data-severity={diagnostic.severity}>
      {diagnostic.severity === 'error' ? w('import.severity.error') : w('import.severity.notice')}
    </span>
    {diagnostic.path && <code className="project-import-finding-path">{diagnostic.path}</code>}
    <span className="project-import-finding-message">{diagnostic.message}</span>
    {diagnostic.code && <code className="project-import-finding-code">{diagnostic.code}</code>}
  </li>;
}

function MigrationField({ field, w }: { field: SshipMigrationField; w: Copy }) {
  const disposition = DISPOSITION_LABEL[field.disposition];
  return <li className="project-import-finding" data-disposition={field.disposition}>
    <code className="project-import-finding-path">#{field.index} · {w('sship.field.line', { line: field.line })}</code>
    <span className="project-import-finding-message">{field.name}</span>
    <code className="project-import-finding-code">{field.raw === '' ? w('sship.field.unknown') : field.raw}</code>
    <span className="project-import-finding-severity">
      {disposition ? w(disposition) : field.disposition}
      {field.destinations.length > 0 && ` · ${w('sship.field.destinations')} ${field.destinations.join(', ')}`}
      {field.reason && ` · ${field.reason}`}
    </span>
  </li>;
}

export function SshipMigrationPreview({ preview, w }: { preview: SshipProjectImportPreview; w: Copy }) {
  const migration = preview.migration;
  if (!migration) return null;

  const findings = migration.diagnostics ?? [];
  // What the canonical validator still warns about about the *draft*: a draft
  // with no loading conditions and unknown inputs is exactly what a migration
  // produces, so these are the reader's own warnings about the project they are
  // about to save, kept apart from what the migration itself reported.
  const canonical = preview.diagnostics ?? [];
  const limitations = (migration.limitations ?? [])
    .map(limitationText)
    .filter((text): text is string => Boolean(text));

  return <>
    <dl className="project-import-identity">
      <div><dt>{w('sship.identity.version')}</dt><dd>{migration.source.version}</dd></div>
      <div><dt>{w('sship.identity.header')}</dt><dd><code>{migration.source.header}</code></dd></div>
      <div><dt>{w('sship.identity.file')}</dt><dd>{migration.source.filename}</dd></div>
      <div><dt>{w('sship.identity.hash')}</dt><dd><code>{migration.source.sha256}</code></dd></div>
      <div><dt>{w('sship.identity.size')}</dt><dd>{(migration.source.byte_length / 1024).toFixed(0)} KiB</dd></div>
      <div><dt>{w('sship.identity.method')}</dt><dd><code>{migration.method_version}</code></dd></div>
    </dl>

    <dl className="project-import-counts">
      {COUNT_ROWS.filter(row => typeof migration.counts[row.key] === 'number')
        .map(row => <div key={row.key}><dt>{w(row.label)}</dt><dd>{migration.counts[row.key]}</dd></div>)}
      <div><dt>{w('sship.count.total')}</dt><dd>{migration.fields.length}</dd></div>
    </dl>

    <p className="project-import-note">{w('sship.note')}</p>

    {limitations.length > 0 && <div className="project-import-findings">
      <h3 className="project-import-findings-title">{w('sship.limitations.title')}</h3>
      <ul className="project-import-finding-list">
        {limitations.map((limitation, index) =>
          <li className="project-import-finding" key={`${index}-${limitation}`}>
            <span className="project-import-finding-message">{limitation}</span>
          </li>)}
      </ul>
    </div>}

    {findings.length > 0 && <div className="project-import-findings">
      <h3 className="project-import-findings-title">{w('sship.findings.title', { count: findings.length })}</h3>
      <ul className="project-import-finding-list">
        {findings.map((diagnostic, index) =>
          <MigrationFinding diagnostic={diagnostic} w={w} key={`${diagnostic.path ?? ''}-${index}`} />)}
      </ul>
    </div>}

    {canonical.length > 0 && <details className="project-import-findings-more">
      <summary>{w('sship.canonical.title', { count: canonical.length })}</summary>
      <ul className="project-import-finding-list">
        {canonical.map((diagnostic, index) =>
          <MigrationFinding diagnostic={diagnostic} w={w} key={`canonical-${diagnostic.path ?? ''}-${index}`} />)}
      </ul>
    </details>}

    <details className="project-import-findings-more">
      <summary>{w('sship.fields.title', { count: migration.fields.length })}</summary>
      <p className="project-import-note">{w('sship.fields.note')}</p>
      <ul className="project-import-finding-list">
        {migration.fields.map(field =>
          <MigrationField field={field} w={w} key={field.index} />)}
      </ul>
    </details>
  </>;
}