// metro.config.js
const { getDefaultConfig } = require("expo/metro-config");
const path = require('path');
const { FileStore } = require('metro-cache');

const config = getDefaultConfig(__dirname);

// ── Metro on-disk cache (July 2026) ───────────────────────────────────
// Cache directory namespaced by CACHE_VERSION below. Bump CACHE_VERSION
// whenever a released build must invalidate Cloudflare Pages' cached
// transform artifacts (their build worker retains the previous run's
// `.metro-cache` unless the path itself changes).
//
// Alternatively set METRO_CACHE_ROOT in your env to override.
const CACHE_VERSION = 'v10-2026-07-26-008-julyfix';
const root = process.env.METRO_CACHE_ROOT
  || path.join(__dirname, `.metro-cache-${CACHE_VERSION}`);
config.cacheStores = [
  new FileStore({ root: path.join(root, 'cache') }),
];


// // Exclude unnecessary directories from file watching
// config.watchFolders = [__dirname];
// config.resolver.blacklistRE = /(.*)\/(__tests__|android|ios|build|dist|.git|node_modules\/.*\/android|node_modules\/.*\/ios|node_modules\/.*\/windows|node_modules\/.*\/macos)(\/.*)?$/;

// // Alternative: use a more aggressive exclusion pattern
// config.resolver.blacklistRE = /node_modules\/.*\/(android|ios|windows|macos|__tests__|\.git|.*\.android\.js|.*\.ios\.js)$/;

// Reduce the number of workers to decrease resource usage
config.maxWorkers = 2;

module.exports = config;
