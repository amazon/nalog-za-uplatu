---
name: openspec-retrospec
description: Retroactively document already-applied staged git changes as an OpenSpec change. Captures what was built from git diff and generates proposal, design, and tasks artifacts that precisely reflect those changes.
license: MIT
compatibility: Requires openspec CLI and git.
metadata:
  author: openspec
  version: "1.0"
---

Retroactively document staged git changes as a new OpenSpec change.

I'll inspect your staged changes and generate:
- proposal.md (what & why)
- design.md (how)
- tasks.md (implementation steps)

When done, the change is ready to archive immediately.

---

**Input**: Optionally provide a kebab-case change name. If omitted, one will be derived from the staged diff.

**Steps**

1. **Get the staged diff**

   ```bash
   git diff --staged
   ```

   If there are no staged changes, stop and inform the user:
   > "No staged changes found. Stage your changes with `git add` and try again."

   Parse the diff to understand:
   - Which files were modified/added/deleted
   - What the actual code changes are (not just file names)
   - The nature and scope of the change

2. **Determine the change name**

   If the user provided a name, use it.

   Otherwise, derive a short kebab-case name from the diff content (e.g., changes to height and QR field lengths → `adjust-slip-dimensions-and-qr-fields`).

   **Do NOT ask the user** unless the diff is completely ambiguous (empty or binary-only).

3. **Create the change directory**

   ```bash
   openspec new change "<name>"
   ```

   This creates a scaffolded change at `openspec/changes/<name>/` with `.openspec.yaml`.

   If a change with that name already exists, use the **AskUserQuestion tool** to ask whether to continue it or pick a different name.

4. **Get the artifact build order**

   ```bash
   openspec status --change "<name>" --json
   ```

   Parse the JSON to get:
   - `applyRequires`: artifact IDs needed (e.g., `["tasks"]`)
   - `artifacts`: list with status and dependencies

5. **Create artifacts in sequence, each grounded in the diff**

   Use the **TodoWrite tool** to track artifact progress.

   Loop through artifacts in dependency order (no pending dependencies first):

   a. **For each artifact that is `ready`**:
      - Get instructions:
        ```bash
        openspec instructions <artifact-id> --change "<name>" --json
        ```
      - The instructions JSON includes:
        - `context`: Project background (constraints for you - do NOT include in output)
        - `rules`: Artifact-specific rules (constraints for you - do NOT include in output)
        - `template`: The structure to use for your output file
        - `instruction`: Schema-specific guidance for this artifact type
        - `outputPath`: Where to write the artifact
        - `dependencies`: Completed artifacts to read for context
      - Read any completed dependency files for context
      - **Write the artifact grounded exclusively in the staged diff** — do not describe intended future changes or aspirations, only what the diff actually contains
      - Use `template` as the structure; apply `context` and `rules` as constraints — do NOT copy them into the file
      - **Verify**: After writing, re-read the artifact and cross-check every claim against the diff. Correct any mismatches before continuing.
      - Show brief progress: "Created <artifact-id>"

   b. **Continue until all `applyRequires` artifacts are complete**
      - After each artifact, re-run `openspec status --change "<name>" --json`
      - Stop when all `applyRequires` artifact IDs have `status: "done"`

   c. **If context is genuinely ambiguous** (e.g., intent behind a magic number change):
      - Use **AskUserQuestion tool** to clarify
      - Then continue

6. **Show final status**

   ```bash
   openspec status --change "<name>"
   ```

   Summarize:
   - Change name and location
   - Artifacts created with one-line descriptions
   - "All artifacts created and verified against staged diff."
   - Prompt the user:
     > "These changes are already applied. Run `/opsx:archive` to archive this change, or ask me to do it."

7. **Archive after user confirms**

   Wait for user confirmation to archive (explicit reply or `/opsx:archive`).

   When confirmed, invoke the **openspec-archive-change** skill for this change.

---

**Artifact Grounding Rules**

- Every requirement, decision, and task in the artifacts **must correspond to an actual change in the diff**
- Do NOT add speculative, aspirational, or "next steps" content
- Do NOT omit changes that are present in the diff — tasks.md must account for all modified files/behaviors
- If the diff contains a change whose intent is unclear, describe the mechanical change and note the uncertainty rather than guessing intent
- For `tasks.md`: each task should map to a concrete, identifiable change in the diff (file + behavior); mark all tasks `- [x]` since the work is already done

**Artifact Creation Guidelines**

- Follow the `instruction` field from `openspec instructions` for each artifact type
- The schema defines what each artifact should contain - follow it
- Read dependency artifacts for context before creating new ones
- Use `template` as the structure for your output file - fill in its sections
- **IMPORTANT**: `context` and `rules` are constraints for YOU, not content for the file
  - Do NOT copy `<context>`, `<rules>`, `<project_context>` blocks into the artifact
  - These guide what you write, but should never appear in the output

**Guardrails**
- If no staged changes exist, stop immediately and tell the user
- Base all artifact content solely on the staged diff — nothing else
- Always verify each artifact against the diff after writing
- Mark all tasks `- [x]` (already complete) in tasks.md
- Always read dependency artifacts before creating a new one
- Verify each artifact file exists after writing before proceeding to next
- After archiving, confirm the archive location to the user
