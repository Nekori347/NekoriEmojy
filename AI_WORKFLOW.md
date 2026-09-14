# AI_WORKFLOW.md

## Purpose

This repository uses two AI roles:

- **OpenAI Codex**: primary implementation agent
- **DeepSeek**: secondary reviewer and analysis agent

The goal is to preserve OpenAI Codex usage for work that requires direct repository access, implementation, execution, and verification, while using DeepSeek for lower-risk review and analysis work.

These rules are intended to improve engineering quality while reducing unnecessary Codex usage. They do not override the repository's `AGENTS.md`; they complement it.

---

## Activation Status

Updated by explicit user instruction on 2026-09-14. This section defines when the workflow below applies and takes precedence over its general stage-review and handoff guidance.

### Current NekoriEmojy version (the P0–P6 release now in development)

- OpenAI Codex is the sole development and review executor throughout the remaining implementation stages.
- The regular Codex / DeepSeek dual-model stage workflow is **not yet active** for this version.
- Do not pause P3, P4, or any other intermediate stage to wait for DeepSeek Review.
- Do not proactively generate intermediate DeepSeek review or stage-handoff packages. Ordinary development records, test evidence, commits, and pull requests remain appropriate.
- DeepSeek is planned for **one Final Review only**: after all major features, testing, and fixes are complete, and before final acceptance / merge / release, prepare one complete Final Review handoff for a second-engineer pre-release review.
- Preserve the already completed and verified P1–P3 work. This activation change does not require redoing, re-reviewing, or rolling it back. Continue the current P4 work.
- Any earlier P3 review materials are historical artifacts; they do not create an active intermediate review gate.

### Starting with the next version

The regular dual-model stage collaboration and review workflow defined below becomes active starting with the **next NekoriEmojy version**, not partway through the current version.

### Effective immediately

**Reasoning Level Guidance remains active now**, including the Medium / High / Highest recommendations at meaningful stage boundaries in sections 11–15. The user continues to control the reasoning level manually.

---

## 1. OpenAI Codex Responsibilities

Use OpenAI Codex as the primary implementation agent for:

- reading and modifying the actual repository;
- tracing real call chains and runtime behavior;
- implementing features;
- fixing bugs;
- database and schema migrations;
- filesystem and persistence changes;
- build and compilation;
- running tests;
- runtime verification;
- Git operations;
- commits;
- pull requests;
- final validation of external review findings.

OpenAI Codex remains the source of truth for the actual repository state.

Do not delegate final verification of repository behavior to another model.

---

## 2. DeepSeek Responsibilities

Prefer DeepSeek for tasks that do not require directly changing the authoritative repository, including:

- reviewing a completed diff or commit;
- searching for possible regressions;
- identifying missing edge cases;
- proposing test cases;
- reviewing database migration risks;
- checking for unnecessary complexity;
- checking whether an implementation looks like a workaround rather than a root-cause fix;
- comparing implementation approaches;
- reviewing dependency choices;
- analyzing logs already supplied to it;
- challenging assumptions;
- producing a second engineering opinion.

DeepSeek acts primarily as a reviewer, not the authoritative implementer.

---

## 3. Tasks That Should Not Normally Consume OpenAI Codex Usage

Avoid using OpenAI Codex merely for broad prompts such as:

- "Review everything again."
- "Think of every possible edge case."
- "Find anything that might be wrong."
- "Compare several architectural ideas."
- "Explain this diff."
- "Suggest more tests."

When practical, perform these analysis-heavy tasks with DeepSeek first.

Then send only the concrete findings that require repository verification back to OpenAI Codex.

For small tasks where delegation and handoff would cost more time than it saves, let OpenAI Codex complete the task directly.

---

## 4. When to Trigger a DeepSeek Review

Do not review every tiny change.

Prefer DeepSeek review after a meaningful stage such as:

- completion of a major feature;
- a large or cross-module diff;
- database or schema migration work;
- persistent user-data changes;
- update / backup / restore changes;
- introduction of a significant dependency;
- a risky refactor;
- a difficult bug that required multiple attempts;
- preparation for merging into `main`;
- preparation for a release.

Low-risk, localized changes can normally remain Codex-only.

---

## 5. Review Handoff

After completing a meaningful implementation stage, OpenAI Codex should prepare a concise review package containing:

- requirement being implemented;
- commit hash or diff range;
- files changed;
- short implementation summary;
- relevant architectural constraints;
- tests already performed;
- known uncertainties or risks.

Do not send the entire repository history unless necessary.

The goal is to give the reviewer the smallest sufficient context.

A suggested review package format:

```text
Stage:
[short name]

Requirement:
[what this stage is supposed to achieve]

Commit / Diff:
[commit hash or diff range]

Changed files:
[list]

Implementation summary:
[brief explanation]

Relevant constraints:
[list]

Verification already performed:
[list]

Known uncertainties / risks:
[list]
```

---

## 6. DeepSeek Review Format

DeepSeek should classify findings as:

### Must Fix

Likely correctness, regression, data-loss, security, or requirement violations.

### Verify

Plausible concerns that require checking against the real repository or runtime.

### Worth Considering

Non-critical maintainability, performance, or design improvements.

### No Action Needed

Alternative implementation preferences that do not demonstrate an actual problem.

For every finding, explain:

- what may be wrong;
- why;
- what evidence supports the concern;
- what should be verified.

Do not present speculation as confirmed fact.

Do not recommend unrelated refactors merely because another implementation style is preferred.

---

## 7. Returning Review Findings to OpenAI Codex

External review findings are suggestions, not instructions.

When DeepSeek review feedback is returned to OpenAI Codex:

1. verify each finding against the actual current repository;
2. reproduce the issue when practical;
3. reject findings that do not apply;
4. fix only findings supported by evidence;
5. run relevant tests after changes.

Do not change correct code merely because another model proposed a different implementation.

DeepSeek narrows the problem space.

OpenAI Codex proves the answer against the real project.

---

## 8. Repository Authority

GitHub and the current checked-out repository are the authoritative project state.

AI conversation history is not authoritative when it conflicts with:

- current source code;
- tests;
- runtime behavior;
- database state;
- committed project documentation.

When in doubt, verify against the repository and runtime evidence.

---

## 9. Concurrency Rule

By default, only OpenAI Codex should modify the authoritative working tree.

DeepSeek should remain read-only / reviewer-oriented.

Do not allow two agents to modify the same working tree concurrently.

If DeepSeek is ever used for implementation, it must work on a separate branch or isolated worktree, and its changes must be reviewed before integration.

---

## 10. Cost / Usage Principle

Use the least expensive capable model for the task, but do not trade away correctness or user-data safety merely to reduce usage.

General preference:

**DeepSeek**
→ broad review, analysis, edge-case generation, second opinions, test design

**OpenAI Codex**
→ implementation, repository investigation, execution, testing, integration, Git operations, final verification

The purpose is not to maximize the number of AI agents involved.

The purpose is to reduce duplicated work, unnecessary Codex usage, and unverified changes.

---

## 11. Reasoning Level Guidance

The user manually controls the OpenAI model reasoning level.

Do not assume that the highest reasoning level should be used by default.

Default preference:

- **Medium** for normal implementation work.
- **High** for difficult investigation, architecture, migrations, cross-module problems, or unresolved bugs.
- **Highest** only for unusually difficult, high-risk, or repeatedly unresolved problems.

At the end of a logical project stage, before beginning the next substantially different stage, briefly evaluate whether the current reasoning level is appropriate.

Only recommend a change when it is likely to materially improve:

- quality;
- reliability;
- debugging efficiency;
- or usage efficiency.

If the current reasoning level appears unnecessarily high for the next stage, proactively recommend lowering it.

---

## 12. Medium

Prefer **Medium** for:

- normal feature implementation;
- clear bug fixes;
- UI work;
- routine refactoring;
- ordinary tests;
- straightforward repository work;
- tasks with clear acceptance criteria;
- low-risk follow-up work after a difficult issue has already been resolved.

Medium should be the normal default for day-to-day development.

---

## 13. High

Recommend **High** for:

- architecture changes;
- database/schema migrations;
- persistent user-data changes;
- difficult lifecycle or state bugs;
- cross-module debugging;
- unclear root causes;
- significant dependency decisions;
- large or risky refactors;
- bugs that survived an initial reasonable fix attempt;
- update / backup / restore logic where data integrity matters;
- compatibility work across old and new data formats.

---

## 14. Highest

Recommend **Highest** only when:

- High reasoning has already failed to resolve the problem;
- several plausible root causes remain after investigation;
- the task has unusually high data-loss or compatibility risk;
- a major architectural decision requires unusually deep analysis;
- the problem is exceptionally difficult and expensive to get wrong;
- repeated failed attempts indicate that deeper reasoning is likely to materially help.

Do not recommend Highest merely because:

- the task is long;
- many files are involved;
- the implementation is tedious;
- the repository is large;
- or more reasoning might theoretically be useful.

After a difficult issue has been resolved, recommend returning to Medium when the remaining work is routine.

---

## 15. When to Recommend a Reasoning-Level Change

Do not recommend switching levels in the middle of an active implementation or debugging operation unless continuing at the current level would clearly be wasteful or unsafe.

Prefer changing reasoning levels at:

- task boundaries;
- feature-stage boundaries;
- after a major bug has been resolved;
- before a high-risk migration or architectural stage;
- before a particularly difficult investigation.

When a recommendation is warranted, report it concisely:

```text
Recommended reasoning level for next stage: Medium / High / Highest

Reason:
[one short sentence]
```

If no change is needed, do not mention reasoning level.

The purpose is to preserve expensive reasoning capacity for tasks that actually benefit from it, not to maximize reasoning depth.

---

## 16. Language

Respond in Chinese by default unless the user explicitly requests another language.

Use Chinese for:

- explanations;
- plans;
- analysis;
- review summaries;
- questions;
- completion reports.

Keep the following in their original form when accuracy benefits:

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

## 17. Final Workflow Principle

For this repository:

1. requirements and product decisions are clarified first;
2. OpenAI Codex performs authoritative implementation and verification;
3. DeepSeek is used selectively for lower-cost review and analysis;
4. review findings return to Codex for evidence-based validation;
5. GitHub / the checked-out repository remains the source of truth;
6. reasoning level is adjusted only at meaningful stage boundaries.

**DeepSeek narrows the problem space. OpenAI Codex proves the answer against the real project.**
