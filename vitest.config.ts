import { defineConfig } from "vitest/config";

/**
 * `NODE_ENV` is pinned here rather than in the npm script.
 *
 * React resolves a different build per NODE_ENV, and the production build does
 * not export `act` — so a machine with `NODE_ENV=production` in its environment
 * fails every rendering test with `React.act is not a function`, which says
 * nothing about the cause. Vitest defaults NODE_ENV to "test" only when it is
 * unset, so an ambient value silently wins.
 *
 * Setting it in a `VAR=value` shell prefix would fix that on POSIX and break
 * Windows, where cmd.exe has no such syntax and CI runs the same script.
 */
export default defineConfig({
  test: {
    env: { NODE_ENV: "test" },
  },
});
