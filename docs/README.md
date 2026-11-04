# Technical Documentation

This folder holds the technical documentation of the Empório da Música customer service agent. The [project README](../README.md) covers setup and gives a summary; these documents go into depth.

| Document | Content |
|---|---|
| [1. Overview](01-overview.md) | Executive summary, business problem, objectives, inputs and capabilities |
| [2. Architecture](02-architecture.md) | Layers, design principles and agent tools |
| [3. Technical Decisions](03-technical-decisions.md) | Choices, rationale, alternatives considered and prompt strategy |
| [4. Business Rules](04-business-rules.md) | Store rules implemented in code and where |
| [5. Data Analysis](05-data-analysis.md) | Data profiling findings, assumptions and validation |
| [6. Security and Error Handling](06-security-and-error-handling.md) | Privacy, prompt injection, secrets and error behaviour |
| [7. Quality Assurance](07-quality-assurance.md) | Automated tests, CI and the behavioural evaluation |
| [8. Operations](08-operations.md) | Installation, commands and configuration |
| [9. Limitations and Roadmap](09-limitations-and-roadmap.md) | Known limitations and recommended next steps |

## Building the PDF

The submission PDF is generated from the README and these documents:

```bash
pip install -e ".[docs]"
python scripts/build_docs_pdf.py --output "Technical Report.pdf"
```

The script needs Google Chrome or Microsoft Edge installed. It uses them in headless mode to print the document.
