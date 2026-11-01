# AI Prompt History

## Important note about fidelity

This file is a **reconstructed topic-level history**, not a verbatim export of every prompt. It records the assistance topics that can be substantiated from the available project discussion. Wording below is summarized and must not be presented as exact original prompt text.

The candidate used ChatGPT and Claude independently for different parts of the project. The original Claude conversation was not available when this file was prepared, so Claude's exact prompts and responses are not reproduced or guessed. Add the original Claude transcript/export and any available ChatGPT transcript before submission if the recruitment team expects a complete verbatim prompt history.

## ChatGPT — recorded discussion topics

The following are summaries of actual topics discussed during the project:

1. **Assignment analysis:** Asked for help understanding and organizing the YottaFlex 72-hour customer-segmentation challenge and its requirements.
2. **Project review:** Discussed whether the Customer Segmentation project and repository structure covered the assignment's expected deliverables.
3. **Environment troubleshooting:** Reported that PowerShell blocked `Activate.ps1` and asked how to run the project's Python environment safely.
4. **Dependency troubleshooting:** Reported `ModuleNotFoundError: No module named 'numpy'` and received instructions to install dependencies from `requirements.txt` using the virtual-environment Python executable.
5. **Full-scale generation:** Ran the generator with seed `20261022`, 50,000 customers, 200,000 orders and 1,000,000 engagement events; shared the terminal output for review.
6. **Data validation:** Ran `src/validate_data.py` against the full output and shared the result `PASS 187 FAIL 0 INFO 29`.
7. **Reproducibility:** Generated a second full-scale output with the same seed and parameters, then compared SHA-256 checksums across the generated files.
8. **Checksum interpretation:** Shared the comparison showing matching core data, ground-truth, schema and database artifacts, and investigated differences/missing validation-report files.
9. **GitHub readiness:** Reviewed repository structure, `.gitignore`, Git status, commits and push status before final submission.
10. **AI disclosure:** Discussed preparing an AI usage disclosure and prompt-history record for the recruitment guidelines.

## Claude — original history to attach

Claude was used independently for other parts of the project. Exact Claude prompts and the corresponding tasks have not been supplied in the available conversation, so they are intentionally not invented here.

**Action before submission:** Export or copy the relevant Claude conversation(s) and append them below, preserving the original prompt wording and, where practical, dates/timestamps. If multiple Claude conversations were used, list each separately and identify the task it supported.

### Claude transcript

_Paste the original Claude prompts and relevant responses here. Do not replace exact prompts with reconstructed wording._

## Candidate review and validation record

The candidate ran the project locally, installed dependencies, executed both full-scale generation runs, ran validation on both outputs, reviewed the terminal results and performed the checksum comparison. The observed validation result for each full-scale output was **187 PASS, 0 FAIL, 29 INFO**. The checksum comparison confirmed matches for the core data and schema/database artifacts; not every metadata/report file matched in the initial comparison.
