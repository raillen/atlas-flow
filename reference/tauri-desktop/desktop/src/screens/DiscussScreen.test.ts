import { describe, expect, it } from "vitest";
import type { DecisionCandidate, ProjectDraft } from "../api";
import { DRAFT_DOMAINS, describeDraft, isPending } from "./DiscussScreen";

function draft(overrides: Partial<ProjectDraft> = {}): ProjectDraft {
  const base = Object.fromEntries(
    DRAFT_DOMAINS.map((domain) => [domain, "unknown"]),
  ) as ProjectDraft;
  return { ...base, ...overrides };
}

function decision(status: string): DecisionCandidate {
  return {
    id: "dec-1",
    title: "Use SQLite",
    statement: "Operational state goes in SQLite",
    rationale: "",
    status,
    affectedDomains: [],
    requiresAdr: false,
    timestamp: "2026-08-11T00:00:00Z",
  };
}

describe("describeDraft", () => {
  it("names the domains that still need work", () => {
    // Finalization is refused while any domain is short; a button that fails
    // without saying which one looks broken.
    const text = describeDraft(draft({ product: "sufficient" }));

    expect(text).toContain("8 of 9");
    expect(text).toContain("architecture");
    expect(text).not.toContain("product,");
  });

  it("says so when the draft is finalizable", () => {
    const complete = Object.fromEntries(
      DRAFT_DOMAINS.map((domain) => [domain, "sufficient"]),
    ) as ProjectDraft;

    expect(describeDraft(complete)).toContain("can be finalized");
  });

  it("handles a session with no draft at all", () => {
    expect(describeDraft(undefined)).toBe("No draft yet.");
  });

  it("covers the nine domains the Goal system tracks", () => {
    expect(DRAFT_DOMAINS).toHaveLength(9);
    expect(DRAFT_DOMAINS).toContain("aiOrchestration");
  });
});

describe("isPending", () => {
  it("offers acceptance only for a proposal", () => {
    expect(isPending(decision("PROPOSED"))).toBe(true);
    expect(isPending(decision("proposed"))).toBe(true);
  });

  it("does not offer to accept what already has an answer", () => {
    for (const status of ["ACCEPTED", "REJECTED", "SUPERSEDED"]) {
      expect(isPending(decision(status)), status).toBe(false);
    }
  });
});
