# Frontend

The frontend is a React/TypeScript/Vite application with a dark, technical, square-edged visual foundation. The source design tokens are in `src/styles.css`.

From the repository root:

```powershell
npm.cmd install --prefix frontend
npm.cmd run dev --prefix frontend
npm.cmd run lint --prefix frontend
npm.cmd run format:check --prefix frontend
npm.cmd test --prefix frontend
npm.cmd run build --prefix frontend
```

Development requests under `/api` proxy to FastAPI on `127.0.0.1:8000`. The production build is emitted to `frontend/dist` and served by FastAPI.
