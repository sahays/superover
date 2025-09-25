import { setupWorker } from 'msw/browser';
import { handlers } from './handlers';

// Set up the service worker with our request handlers
export const worker = setupWorker(...handlers);

// Start the worker in development mode
if (typeof window !== 'undefined' && process.env.NODE_ENV === 'development') {
  worker.start({
    onUnhandledRequest: 'warn',
  });
}