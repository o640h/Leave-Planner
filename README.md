# Leave Planner

Leave Planner is a local Windows desktop application for one operator managing annual leave for a consultant team. It replaces the one-workbook-per-consultant workflow with shared consultant records, job plans, entitlement calculations, public holidays, leave booking, balances, audit history, and recovery tools.

The application uses React and TypeScript, FastAPI, SQLite, WebView2, and PyInstaller. Its data remains on the operator's device under `%LOCALAPPDATA%\LeavePlanner`.

Policy documents and the reference workbook are retained in [`docs/reference`](docs/reference); calculation and maintenance notes are in [`docs/explanations`](docs/explanations).
