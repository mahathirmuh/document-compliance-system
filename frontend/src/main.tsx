import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import { AppProviders } from './providers/AppProviders';
import { AppRoutes } from './routes/AppRoutes';
import './styles/index.css';

const rootElement = document.getElementById('root');

if (!rootElement) {
  throw new Error('Unable to start the application: root element was not found.');
}

createRoot(rootElement).render(
  <StrictMode>
    <AppProviders>
      <AppRoutes />
    </AppProviders>
  </StrictMode>,
);
