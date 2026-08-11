/**
 * What the chat understands.
 *
 * Commands are parsed here, in the client, and never sent to a model. An
 * orchestrator whose control surface guesses is one you cannot trust: "cancel"
 * has to cancel, every time, with nothing inferring in between. Anything not
 * recognised is treated as a message, never as a guessed action.
 */

export type Command =
  | { kind: "run"; goalId: string }
  | { kind: "cancel"; runId: string | null }
  | { kind: "evidence"; goalId: string | null }
  | { kind: "show"; goalId: string }
  | { kind: "help" }
  | { kind: "message"; content: string };

/** A Goal id as the Goal system writes them: P08-G01, L01-G02. */
const GOAL_ID = /\b([A-Z]\d{1,2}-G\d{1,2})\b/i;
const RUN_ID = /\b(run-[0-9a-f]{6,})\b/i;

export interface CommandSpec {
  /** What to type. */
  usage: string;
  /** What it does, in one line. */
  summary: string;
}

/** Listed in the order they are most likely to be wanted. */
export const COMMANDS: CommandSpec[] = [
  { usage: "run P08-G01", summary: "Plan the Goal and start executing it" },
  { usage: "cancel", summary: "Stop the run in flight" },
  { usage: "show P08-G01", summary: "Select a Goal and open its plan" },
  { usage: "evidence P08-G01", summary: "What each gate has, and what it lacks" },
  { usage: "help", summary: "This list" },
];

/**
 * Parse one line of input.
 *
 * The verb has to come first. Accepting "please cancel the run" would mean
 * guessing where the command ends and the sentence begins, and a sentence that
 * happens to contain "cancel" must not stop a run.
 */
export function parseCommand(input: string): Command {
  const trimmed = input.trim();
  if (trimmed === "") return { kind: "message", content: "" };

  const [verb, ...rest] = trimmed.split(/\s+/);
  const tail = rest.join(" ");
  const goal = GOAL_ID.exec(tail)?.[1]?.toUpperCase() ?? null;

  switch (verb.toLowerCase()) {
    case "run":
    case "/run":
      return goal ? { kind: "run", goalId: goal } : { kind: "message", content: trimmed };
    case "cancel":
    case "/cancel":
      return { kind: "cancel", runId: RUN_ID.exec(tail)?.[1] ?? null };
    case "evidence":
    case "/evidence":
      return { kind: "evidence", goalId: goal };
    case "show":
    case "/show":
      return goal ? { kind: "show", goalId: goal } : { kind: "message", content: trimmed };
    case "help":
    case "/help":
    case "?":
      return { kind: "help" };
    default:
      return { kind: "message", content: trimmed };
  }
}

/** The list the chat prints for `help`, and when a verb is used wrongly. */
export function helpText(): string {
  return COMMANDS.map((command) => `${command.usage} — ${command.summary}`).join("\n");
}
