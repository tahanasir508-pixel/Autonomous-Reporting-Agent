\# Autonomous Reporting Agent



An AI-assisted sales reporting system that validates sales data, detects anomalies, tracks their lifecycle, and generates structured reports with optional AI-written summaries.



\## Features



\* \*\*Data validation:\*\* Checks required columns, missing values, negative values, and duplicate records.

\* \*\*Anomaly detection:\*\* Identifies unusual sales patterns at product and regional levels.

\* \*\*Anomaly lifecycle tracking:\*\* Classifies findings as new, ongoing, or resolved.

\* \*\*AI-generated summaries:\*\* Summarizes findings using a configured AI service.

\* \*\*Automated reporting:\*\* Saves dated Markdown reports containing revenue totals and anomaly findings.

\* \*\*Batch processing:\*\* Processes historical datasets and generates reports for individual dates.

\* \*\*Streamlit dashboard:\*\* Provides authentication and dataset-upload workflows.

\* \*\*PDF and email modules:\*\* Includes components for exporting and delivering reports.



\## Technology Stack



\* Python

\* Pandas and NumPy

\* Streamlit

\* Google Gen AI SDK

\* SQLAlchemy



\## How It Works



1\. Extract sales data and validate its structure and values.

2\. Detect anomalies at product and regional levels.

3\. Track new, ongoing, and resolved anomalies.

4\. Generate an AI summary when the configured service is available.

5\. Save the results in a dated Markdown report.



The reporting pipeline is designed to preserve structured findings even when AI summary generation fails.



\## Setup



Create and activate a Python virtual environment:



```powershell

python -m venv .venv

.\\.venv\\Scripts\\Activate.ps1

```



Install the project dependencies:



```powershell

python -m pip install -r requirements.txt

```



Configure any required API keys and authentication settings locally. Never commit API keys, passwords, OAuth tokens, or private configuration files.



\## Run the Daily Report



The daily pipeline expects a `sales\_data.csv` file in the project directory.



```powershell

python run\_daily\_report.py

```



Generated reports are saved in the `reports/` directory.



\## Run the Dashboard



```powershell

streamlit run dashboard.py

```



\*\*Note:\*\* The dashboard currently imports `voice\_ui.py`, which was not found during the initial project inspection. Restore the missing module or correct the import before relying on the dashboard.



\## Expected Sales Data



The CSV should contain these columns:



| Column              | Description                |

| ------------------- | -------------------------- |

| `date`              | Sales record date          |

| `region`            | Sales region               |

| `product`           | Product name or identifier |

| `units\_sold`        | Number of units sold       |

| `revenue`           | Revenue for the record     |

| `transaction\_count` | Number of transactions     |



Historical datasets should contain several weeks of records to establish useful anomaly-detection baselines.



\## Security



\* Keep API keys and credentials out of Git.

\* Do not commit private databases, uploaded datasets, or generated reports.

\* Use environment variables or a secrets manager for sensitive configuration.

\* Review authentication and data isolation before public deployment.



\## Project Status



This project combines data validation, anomaly detection, anomaly lifecycle tracking, and AI-assisted reporting. Dashboard integrations and deployment configuration should be verified before production use.



