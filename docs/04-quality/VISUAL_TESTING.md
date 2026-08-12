# Visual Testing

Current preferred roster is text-oriented; visual correctness must not depend
on an LLM.

The App Shell currently has a deterministic Skia/headless render smoke test at
1440 × 900. It verifies that the frame is produced at or above the supported
minimum geometry, the selected stage is represented in the control tree and
every button has an automation name. The Run surface is composed through the
same XAML tree and its state transitions are covered at ViewModel level.
Palette tests cover both themes.

Baseline for the next components: golden images where stable, overflow and
minimum-window geometry checks, keyboard interaction, accessibility-tree
checks and human polish review. Golden updates require an explicit visual
review; a failing image is not accepted by blindly replacing the baseline.

Optional vision models can be added by policy later without changing gates.
