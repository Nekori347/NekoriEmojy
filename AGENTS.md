# AGENTS.md

These instructions apply to all Codex work in this repository.

## 1. Core Priorities

When priorities conflict, use this order:

1. User data safety
2. Correctness and root-cause resolution
3. Compatibility with the existing project
4. Maintainability
5. Simplicity
6. Performance and application footprint
7. Development speed

Do not sacrifice the higher priorities merely to finish faster.

---

## 2. Think Before Coding

Do not silently make consequential assumptions.

Before implementation:

- Understand the existing behavior and the relevant code path first.
- Distinguish clearly between:
  - confirmed facts;
  - hypotheses / unverified assumptions;
  - ruled-out possibilities.
- Do not treat a plausible explanation as a confirmed root cause.
- If multiple interpretations would lead to materially different behavior, architecture, compatibility, or data-safety outcomes, surface them.
- If the existing code, tests, documentation, and project context clearly support one interpretation, use it rather than asking unnecessary questions.
- Ask the user only when ambiguity materially affects:
  - requirements;
  - architecture;
  - data safety;
  - irreversible operations;
  - major UX behavior;
  - or a significant long-term tradeoff.

For ordinary implementation details, infer from existing code and conventions and continue independently.

---

## 3. Simplicity First

Use the minimum complexity necessary to solve the actual requirement.

Do not:

- implement features that were not requested;
- add speculative flexibility or configuration;
- create abstractions for one-off logic without a clear benefit;
- introduce unnecessary layers;
- add redundant listeners, polling, timers, or fallback chains;
- over-generalize code for hypothetical future requirements;
- turn a small application into a collection of unnecessary frameworks or dependencies.

If a clear 50-line implementation can safely replace a 200-line design, prefer the simpler implementation.

However, simplicity must not remove necessary validation or error handling at real external boundaries such as:

- filesystem operations;
- databases and schema migrations;
- backup and restore;
- software updates;
- network operations;
- user input;
- external tools or services.

---

## 4. Surgical Changes

Make the smallest logically complete change required.

When editing existing code:

- do not refactor unrelated code;
- do not reformat adjacent code merely for style;
- do not rewrite working code only because another style is preferred;
- follow the existing project conventions where they remain reasonable;
- mention unrelated problems instead of automatically fixing them;
- remove imports, variables, functions, or files only when your own change makes them obsolete.

Do not rewrite work that has already been completed and verified solely to conform to these rules.

Every meaningful change should be traceable to at least one of:

- the current requirement;
- a necessary bug fix;
- a required compatibility adjustment;
- a migration requirement;
- or required testing / verification.

---

## 5. Root Cause Before Patch

Prefer fixing the actual trigger, lifecycle, data flow, persistence logic, or ownership problem.

Do not solve bugs by default through:

- route or page enumeration;
- special-case accumulation;
- repeated fallback branches;
- duplicated listeners;
- arbitrary delays;
- repeated polling;
- masking an error without understanding its source;
- stacking patches on top of earlier patches.

Before modifying a problematic subsystem, identify the relevant:

- trigger;
- data source;
- call chain;
- lifecycle;
- ownership boundary;
- persistence path;
- and failure point.

A workaround is acceptable only when the underlying limitation cannot reasonably be fixed and the reason is documented.

---

## 6. Goal-Driven Execution

Convert work into verifiable outcomes.

Examples:

Bug fix:
- reproduce the bug;
- identify the failing layer;
- fix it;
- verify that the original reproduction no longer fails.

New feature:
- define observable acceptance criteria;
- implement the minimum required behavior;
- verify the criteria.

Database migration:
- prepare representative old data;
- run the migration;
- verify that user data survives correctly;
- verify the new version can read it.

Refactor:
- establish current behavior;
- perform the refactor;
- verify equivalent behavior afterward.

For multi-step work, use a brief execution plan:

1. [step] -> verify: [check]
2. [step] -> verify: [check]
3. [step] -> verify: [check]

Do not create a long speculative plan when the task is simple.

After each logical unit, run the smallest relevant verification first.

Do not accumulate many unrelated unverified changes and leave all debugging until the end.

---

## 7. Preserve User Data

User data safety has priority over implementation convenience.

Treat the following as persistent user data when applicable:

- imported assets;
- library metadata;
- categories;
- category relationships;
- custom ordering;
- tags;
- OCR tags and manually corrected OCR data;
- favorites and other resource metadata;
- user settings;
- indexes;
- library databases;
- backup metadata.

Never solve compatibility problems by:

- deleting the database;
- clearing user data;
- resetting the library;
- silently dropping unsupported records;
- requiring the user to rebuild categories or sorting;
- forcing all resources to be re-imported.

Schema changes should use explicit migrations where appropriate.

Migration, update, or recovery failures should preserve recoverable user data whenever reasonably possible.

When modifying persistence logic, consider backward compatibility before writing the migration.

---

## 8. Program / User Data Separation

The project architecture should preserve the separation between:

- replaceable program files;
- persistent user libraries and databases.

Program updates must not depend on deleting or overwriting persistent user data.

Where relevant, preserve the project's intended lightweight portable architecture:

- replaceable ZIP application body;
- independently located user library;
- persistent database and metadata associated with the library;
- imported assets copied into the managed library rather than moving the user's original files.

Do not casually reintroduce dependencies between the executable directory and persistent library data.

---

## 9. Existing Solutions and Dependencies

For common infrastructure problems, investigate existing solutions before inventing a complex custom implementation.

Check, in order where appropriate:

- platform / framework official APIs;
- existing implementation already present in this repository;
- mature and actively maintained libraries;
- established open-source implementations and architectural patterns.

This especially applies to areas such as:

- database migrations;
- ZIP / archive handling;
- software update mechanisms;
- OCR;
- clipboard and drag-and-drop import;
- filesystem operations;
- logging;
- configuration management;
- thumbnails and caching;
- backup and restore;
- Windows-native window behavior.

Before introducing a significant dependency, consider:

- compatibility with the current language and framework;
- current maintenance activity;
- adoption and real-world use;
- known stability or security issues;
- license compatibility;
- dependency-tree size;
- installation-size impact;
- startup and runtime cost;
- additional runtimes or background services;
- Windows reliability;
- long-term coupling and replacement cost.

Third-party software is a tool, not an architectural goal.

Do not assemble the application from unnecessary, overlapping, or heavyweight dependencies merely to reduce implementation effort.

If only a small part of an existing solution is useful, prefer its API, concept, or isolated component rather than importing an entire framework unnecessarily.

---

## 10. Efficient Repository Work

Minimize redundant repository investigation.

- Prefer targeted search for relevant functions, fields, symbols, configurations, and call sites.
- Do not repeatedly rescan the entire repository without a specific reason.
- Reuse existing investigation notes and confirmed conclusions.
- Do not re-investigate a confirmed conclusion unless new evidence contradicts it.
- Do not repeatedly reread large files after their relevant structure is already understood.
- When a failure occurs, inspect the actual error, logs, stack trace, runtime state, and failing layer before trying another solution.

Do not optimize for fewer tool calls at the expense of correctness, but avoid pointless repetition.

---

## 11. Testing and Verification

Every meaningful change must have an appropriate verification path.

Prefer:

1. smallest relevant test;
2. affected subsystem tests;
3. broader build / lint / typecheck / regression checks when appropriate.

Before considering a task complete:

- verify the requested behavior;
- run relevant tests;
- run applicable build / lint / typecheck commands;
- inspect relevant logs where appropriate;
- inspect `git diff`;
- inspect `git status`;
- ensure no unrelated files were accidentally changed.

If a test cannot be run:

- state that clearly;
- explain why;
- do not claim the behavior has been verified.

Do not repeatedly run expensive full-project validation when a smaller targeted check is sufficient during intermediate iterations.

---

## 12. Logging and Diagnostics

Diagnostics should help locate real failures without noticeably degrading normal performance.

When adding diagnostic logging:

- prefer structured and meaningful events;
- avoid high-frequency spam;
- avoid repeatedly logging unchanged state;
- do not log sensitive user content unnecessarily;
- keep expensive diagnostic behavior disabled or lightweight during normal use where appropriate.

Logs should help answer:

- what happened;
- when;
- in which subsystem;
- with what relevant state;
- and why the operation failed.

Do not use logging as a substitute for fixing a known bug.

---

## 13. Git Safety

Keep changes scoped to the current task.

When practical:

- keep logically separate work in separate commits;
- avoid mixing unrelated refactors into feature or bug-fix commits;
- use clear commit messages.

Do not perform destructive Git operations without explicit approval, including:

- `git reset --hard`;
- `git clean`;
- force push;
- history rewriting;
- deleting large groups of existing files.

Do not rewrite existing commit history unless explicitly requested.

---

## 14. Mid-Project Rule

This repository may already contain substantial completed work.

Therefore:

- preserve existing verified implementations;
- do not restart completed investigation;
- do not perform a project-wide cleanup just because these instructions were introduced later;
- apply these rules primarily to new work and to existing code that must actually change.

If an already-completed implementation materially conflicts with these rules:

1. identify the exact conflict;
2. explain the practical impact;
3. determine whether it causes a real maintenance, correctness, performance, or data-safety problem;
4. only then decide whether modification is necessary.

Do not refactor merely for theoretical purity.

---

## 15. User Interaction

Do not interrupt the user for routine engineering decisions.

Proceed independently when a decision:

- follows existing project conventions;
- is easy to reverse;
- has no meaningful product impact;
- has no material data-safety risk.

Ask the user when:

- requirements genuinely conflict;
- different options create materially different UX;
- a decision substantially affects architecture;
- a heavy dependency is being considered;
- data could be lost;
- an operation is irreversible;
- or the choice creates a significant long-term tradeoff.

When asking, explain the actual decision and tradeoff concisely.

---

## 16. Communication Language

Respond in Chinese by default unless the user explicitly requests another language.

Use Chinese for:

- explanations;
- plans;
- analysis;
- questions;
- summaries;
- completion reports.

Keep the following in their original form where accuracy benefits:

- code;
- identifiers;
- filenames;
- paths;
- CLI commands;
- API names;
- error messages;
- log output;
- stack traces.

Do not translate technical literals merely for consistency.

---

## 17. Completion Reports

At the end of each logical stage, report only information useful for continuing the project:

- what changed;
- why it changed;
- how it was verified;
- remaining known issues;
- the next logical step.

Do not repeatedly restate the full project background, requirements, or already-confirmed investigation history.

Keep progress reports concise unless detailed analysis is specifically useful.

---

## Final Principle

Be rigorous without becoming bureaucratic.

For simple tasks, act simply.

For risky or complex tasks, investigate enough to make the change safely.

Prefer:

correct root cause
> preserved user data
> compatible implementation
> maintainable solution
> simple implementation
> minimal diff
> fast completion
