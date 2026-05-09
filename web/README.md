# loop-monitor web

React + TypeScript frontend for Loop Monitor, built with Vite.

## Setup

```bash
npm ci
```

## Development

```bash
npm run dev
```

Starts the Vite dev server (default port 5173). The `/api/*` prefix is proxied to the backend at `http://127.0.0.1:18792`.

## Build

```bash
npm run build
```

Outputs to `../static/dist/`. FastAPI serves this at `/v2` when the directory exists.

## Type-check

```bash
npm run typecheck
```
