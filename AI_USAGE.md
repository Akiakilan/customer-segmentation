# AI Usage Disclosure

## AI tools used

- **ChatGPT (OpenAI)**
- **Claude (Anthropic)**

Both tools were used independently during different parts of the project. They were used as development assistants; their outputs were not treated as proof that the implementation was correct.

## How AI assistance was used

The following describes the assistance discussed and used during development. It is a summary, not a claim that either tool performed every task listed.

### ChatGPT

ChatGPT assisted with:
- Breaking down the YottaFlex brief into implementation and verification tasks.
- Discussing the customer-data model, entity relationships, segmentation, action eligibility and suppression concepts.
- Explaining synthetic data generation, deterministic seeds and validation concepts.
- Troubleshooting the Windows/Python environment and missing dependencies.
- Guiding execution of the full-scale generator and validator.
- Planning the checksum comparison for repeat runs and reviewing the observed results.
- Reviewing GitHub repository structure and submission readiness.

### Claude

Claude was also used independently for other parts of the project. The precise prompts, outputs and task-by-task allocation should be taken from the original Claude conversation history. They are not reconstructed here because the exact Claude prompts were not provided for this disclosure.

## Candidate work and review

The candidate worked in the local development environment, ran the generator and validation commands, inspected terminal output, compared generated artifacts, and managed the GitHub repository. The candidate is responsible for understanding and explaining the submitted code, business rules, assumptions, design choices and limitations.

## Verification evidence observed during development

The full-scale generator was run twice with seed `20261022`, using:
- 50,000 customers
- 200,000 orders
- 1,000,000 engagement events

Both runs reported zero SQLite foreign-key-check violations. Both datasets passed the project's validator with **187 PASS, 0 FAIL, 29 INFO**.

A SHA-256 comparison showed matching core CSV exports, ground-truth exports, JSON exports, schema/data-dictionary files, SQLite database and SQL seed export. The source manifest and validation summary files were not identical in the initial comparison; the validation summary was subsequently generated for the second output as well. Therefore, this disclosure claims reproducibility only for the compared core artifacts, not byte-for-byte identity of every file in the output folders.

## Limitations of this disclosure

This document is a summary of AI use, not a verbatim transcript. The exact Claude prompt history and any exact ChatGPT prompts not preserved in the conversation should be added from the original chat exports if available. Do not represent reconstructed summaries as exact prompts.
