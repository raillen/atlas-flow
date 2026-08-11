import { describe, expect, it } from "vitest";
import { COMMANDS, helpText, parseCommand } from "./commands";

describe("parseCommand", () => {
  it("runs a Goal named after the verb", () => {
    expect(parseCommand("run P08-G01")).toEqual({ kind: "run", goalId: "P08-G01" });
    expect(parseCommand("/run p08-g01")).toEqual({ kind: "run", goalId: "P08-G01" });
  });

  it("cancels with or without a run id", () => {
    expect(parseCommand("cancel")).toEqual({ kind: "cancel", runId: null });
    expect(parseCommand("cancel run-4f2a91")).toEqual({
      kind: "cancel",
      runId: "run-4f2a91",
    });
  });

  it("treats a sentence containing a verb as a message, not an action", () => {
    // The whole point of parsing here rather than asking a model: a sentence
    // that mentions cancelling must never stop a run.
    expect(parseCommand("I think we should cancel the retry policy")).toEqual({
      kind: "message",
      content: "I think we should cancel the retry policy",
    });
    expect(parseCommand("we could run this later").kind).toBe("message");
  });

  it("keeps a verb without its argument as a message rather than guessing", () => {
    expect(parseCommand("run").kind).toBe("message");
    expect(parseCommand("show").kind).toBe("message");
  });

  it("reads evidence with and without a Goal", () => {
    expect(parseCommand("evidence P07-G01")).toEqual({
      kind: "evidence",
      goalId: "P07-G01",
    });
    expect(parseCommand("evidence")).toEqual({ kind: "evidence", goalId: null });
  });

  it("answers help however it is asked", () => {
    for (const input of ["help", "/help", "?", "  HELP  "]) {
      expect(parseCommand(input).kind, input).toBe("help");
    }
  });

  it("treats empty input as an empty message rather than a command", () => {
    expect(parseCommand("   ")).toEqual({ kind: "message", content: "" });
  });

  it("recognises Goal ids from projects that are not this one", () => {
    expect(parseCommand("run L01-G02")).toEqual({ kind: "run", goalId: "L01-G02" });
  });
});

describe("helpText", () => {
  it("lists every command it can accept", () => {
    // An interface whose commands are undiscoverable is a command line with no
    // manual page.
    const text = helpText();
    for (const command of COMMANDS) {
      expect(text).toContain(command.usage);
      expect(text).toContain(command.summary);
    }
  });

  it("names a verb for every parseable command kind", () => {
    const kinds = COMMANDS.map((command) => parseCommand(command.usage).kind);
    expect(new Set(kinds)).toEqual(new Set(["run", "cancel", "show", "evidence", "help"]));
  });
});
