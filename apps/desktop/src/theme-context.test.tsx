// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { ThemeProvider, useTheme } from "./theme-context";

function ThemeProbe() {
  const { mode, toggle } = useTheme();
  return (
    <button type="button" onClick={toggle}>
      {mode}
    </button>
  );
}

afterEach(() => {
  cleanup();
  window.localStorage.clear();
  document.documentElement.removeAttribute("data-theme");
});

describe("theme preference", () => {
  it("starts in dark mode and switches the root to light mode", () => {
    render(
      <ThemeProvider>
        <ThemeProbe />
      </ThemeProvider>,
    );

    expect(screen.getByRole("button").textContent).toBe("dark");
    fireEvent.click(screen.getByRole("button"));

    expect(screen.getByRole("button").textContent).toBe("light");
    expect(document.documentElement.dataset.theme).toBe("light");
    expect(window.localStorage.getItem("atlas-flow.theme")).toBe("light");
  });

  it("restores a stored preference on the next mount", () => {
    window.localStorage.setItem("atlas-flow.theme", "light");

    render(
      <ThemeProvider>
        <ThemeProbe />
      </ThemeProvider>,
    );

    expect(screen.getByRole("button").textContent).toBe("light");
  });
});
