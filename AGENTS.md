# Project Agent Guidelines (GSD + Roo + Ralph + CodeRabbit)

This repository integrates four complementary AI engineering workflows:
1. **Get Shit Done (GSD)** - Spec-driven phase architecture & anti-context-rot execution
2. **Roo Code Modes** - Role-based persona boundaries (Architect, Coder, Reviewer, Debugger)
3. **Ralph Loop** - Autonomous iterative execution over `prd.json` with test backpressure
4. **CodeRabbit** - Pre-commit and pre-merge AI code review

---

## 1. Get Shit Done (GSD) Workflow
When executing substantial tasks:
- **Phase 1: Discuss & Scope**: Clarify requirements, constraints, and architecture before writing code.
- **Phase 2: Spec & Breakdown**: Break features into atomic, testable user stories in `prd.json`.
- **Phase 3: Execute in Waves**: Execute tasks one by one with clean, focused context.
- **Phase 4: Verify & Ship**: Run unit tests, browser tests, and static checks before marking complete.

---

## 2. Ralph Loop Autonomous Cycle
When running in Ralph mode:
1. Read `prd.json` and `progress.txt` (check Codebase Patterns first).
2. Pick the highest priority story where `passes: false`.
3. Implement that single story.
4. Run project quality checks (typecheck, lint, test).
5. If checks pass, commit changes: `feat: [Story ID] - [Story Title]`.
6. Update `prd.json` to set `passes: true` for the completed story.
7. Append findings and learnings to `progress.txt`.
8. If ALL stories pass, output `<promise>COMPLETE</promise>`.

---

## 3. CodeRabbit Quality Gate
Before staging or committing code, run local CodeRabbit analysis:
```bash
coderabbit review --agent
# or using alias:
cr review --agent
```
Address any security vulnerabilities, memory leaks, or unhandled edge cases flagged by CodeRabbit.

---

## 4. Roo Code Personas
- **Architect (`.roomodes` / architect)**: High-level design, milestone mapping, PRD authoring.
- **Coder (`.roomodes` / code)**: Precision implementation, clean code, minimal diffs.
- **Reviewer (`.roomodes` / reviewer)**: Code diff audit, edge cases, CodeRabbit analysis.
- **Debugger (`.roomodes` / debugger)**: Root-cause analysis, reproduction tests, surgical fixes.
