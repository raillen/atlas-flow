import { Workspace } from "./workspace/Workspace";

/**
 * The application is a workspace, not a set of pages.
 *
 * Everything the shell needs lives in Workspace; this file exists so the entry
 * point has one obvious thing to render. See ADR-013 for why the five tabs
 * became one shell with stages.
 */
export function App() {
  return <Workspace />;
}

export { STAGES, STAGE_LABELS, nextStageIndex } from "./workspace/Workspace";
