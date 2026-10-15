import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import Portfolio from './portfolio/Portfolio';
import './styles/tokens.css';
import './styles/layout.css';
// The workspace material is loaded eagerly, not with the workspace chunk. The
// workspace chunk can fail to arrive, and the surfaces that have to cope with
// that — the reading placeholder, the failed-chunk panel and the Suspense
// fallback — are rendered by this document before the chunk exists, so their
// styles cannot depend on it. Every rule here is already scoped to
// `.app-shell` / `.ff-tool-shell`, so the public pages are unaffected.
import './styles/workspace.css';
// Shared glass loads eagerly; scoped adapters outrank the workspace's square
// control reset without relying on lazy stylesheet insertion order.
import './styles/liquid-glass.css';

createRoot(document.getElementById('root')!).render(<StrictMode><Portfolio /></StrictMode>);
