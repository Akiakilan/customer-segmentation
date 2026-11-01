# AI Prompt History — Customer Segmentation Project

This document records the AI assistance used during the YottaFlex customer segmentation project. ChatGPT and Claude were used independently for different parts of the work.

**Accuracy note:** The entries below are topic-level summaries/reconstructed examples, not verbatim exports of the original conversations. They should not be represented as exact transcripts.

## 1. ChatGPT (OpenAI)

ChatGPT was used for requirement analysis, technical guidance, troubleshooting, validation and documentation.

### 1. Understanding the Assignment
"Help me understand the YottaFlex 72-hour Code Challenge. Break down the customer segmentation problem into implementation requirements, entities, business rules, data generation and validation tasks."

### 2. Project Structure
"Review my Customer Segmentation project structure and help me prepare the repository for the YottaFlex AI Forward Deployed Engineer assignment."

### 3. Python Environment Troubleshooting
"Help me resolve Python virtual environment activation issues in PowerShell and troubleshoot missing dependencies."

### 4. Synthetic Data Generation
"Guide me through generating the full-scale synthetic dataset using seed 20261022, with 50,000 customers, 200,000 orders and 1 million engagement events."

### 5. Data Validation
"Help me run the validation script and understand primary-key uniqueness, foreign-key integrity and validation results."

### 6. Reproducibility
"Help me generate the dataset twice using the same seed and compare SHA-256 checksums to verify reproducibility."

### 7. GitHub Repository
"Guide me through organizing the project files, configuring .gitignore, committing changes and pushing the project to GitHub."

### 8. Final Review
"Help me review the project against the YottaFlex assignment requirements and prepare the final submission."

## 2. Claude (Anthropic)

Claude was used independently for other parts of the project. The following are reconstructed examples of the prompt topics discussed for this project. They are not guaranteed to match the original wording exactly.

### 1. Project Architecture
"Help me plan an end-to-end customer segmentation workflow using customer, order, product, engagement and support data. Explain the entities, relationships and overall architecture."

### 2. Synthetic Data Design
"Suggest a realistic synthetic data generation approach with consistent primary keys, foreign keys, relationships and a fixed random seed."

### 3. Segmentation and Business Rules
"Help me define customer segments using purchase history, engagement activity and support information. Explain how business rules can determine eligible actions."

### 4. Data Quality and Validation
"Review the validation approach for customer segmentation data, including key constraints, referential integrity, date consistency and data quality checks."

### 5. Edge Cases and Business Logic
"Identify potential edge cases involving customer consent, product returns, conflicting segment memberships and incorrect action attribution."

## 3. Candidate Review and Validation Record

The candidate executed the project locally, installed dependencies, generated the full-scale datasets, ran validation scripts, inspected terminal outputs and performed reproducibility checks.

Each of the two full-scale runs reported:
- 187 PASS
- 0 FAIL
- 29 INFO

Core data, ground-truth, schema and database exports matched during the SHA-256 checksum comparison.

## 4. Prompt History Qualification

The ChatGPT entries summarize project discussions. The Claude entries are reconstructed examples based on the described independent use of Claude. They are not original prompt transcripts. If the recruitment guidelines specifically require exact prompts, the original conversation exports should be attached or supplied separately where available.
