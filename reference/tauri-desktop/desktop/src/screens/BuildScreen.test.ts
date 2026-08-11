import { describe, expect, it } from "vitest";
import { cancelState } from "./BuildScreen";

describe("cancelState", () => {
  it("offers cancellation while a run is moving", () => {
    for (const state of ["CREATED", "PLANNING", "READY", "RUNNING"]) {
      expect(cancelState(state), state).toEqual({ enabled: true, label: "Cancel" });
    }
  });

  it("refuses a run that has already stopped", () => {
    // The backend answers 409 for these; offering a button that cannot work
    // teaches people the app is unreliable.
    for (const state of ["VERIFYING", "REVIEWING", "COMPLETED", "FAILED"]) {
      expect(cancelState(state).enabled, state).toBe(false);
    }
  });

  it("says a cancelled run is cancelled rather than offering to cancel it again", () => {
    expect(cancelState("CANCELLED")).toEqual({ enabled: false, label: "Cancelled" });
  });

  it("is disabled before anything has loaded", () => {
    expect(cancelState(undefined).enabled).toBe(false);
  });
});
