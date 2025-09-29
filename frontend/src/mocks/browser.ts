import { setupWorker } from 'msw/browser';
import { handlers } from './handlers';

// Set up the service worker with our request handlers
export const worker = setupWorker(...handlers);

// Start the worker in development mode
if (typeof window !== 'undefined' && process.env.NODE_ENV === 'development') {
  worker.start({
    onUnhandledRequest: (request) => {
      // Ignore WebSocket requests and Next.js internal requests
      if (
        request.url.includes('_next/webpack-hmr') ||
        request.url.includes('_next/static') ||
        request.url.includes('favicon.ico') ||
        request.url.startsWith('ws://') ||
        request.url.startsWith('wss://')
      ) {
        return;
      }

      console.warn(`[MSW] Unhandled ${request.method} request to ${request.url}`);
    },
  });
}