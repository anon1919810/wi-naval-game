import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import Portfolio from './portfolio/Portfolio';
import './styles/tokens.css';
import './styles/layout.css';

createRoot(document.getElementById('root')!).render(<StrictMode><Portfolio /></StrictMode>);
