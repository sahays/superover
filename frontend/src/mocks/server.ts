import { setupServer } from 'msw/node';
import { handlers } from './handlers';

// Set up the mock server for Node.js (used in tests)
export const server = setupServer(...handlers);