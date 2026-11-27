// Page context & Guide-mode command bridge.
// Delegates to the Unified Semantic DOM Engine (dom-engine.js) in Chrome's isolated world.
import { domEngine } from './dom-engine.js';

export const pageCommand = domEngine;
