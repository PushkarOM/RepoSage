# React + Vite

This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Oxc](https://oxc.rs)
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/)

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the ESLint configuration

If you are developing a production application, we recommend using TypeScript with type-aware lint rules enabled. Check out the [TS template](https://github.com/vitejs/vite/tree/main/packages/create-vite/template-react-ts) for information on how to integrate TypeScript and [`typescript-eslint`](https://typescript-eslint.io) in your project.

## Security notes

`npm audit` will report 1 high-severity advisory: **GHSA-qwww-vcr4-c8h2 — React Router RSC Mode CSRF Bypass** (affects `react-router 7.12.0 - 8.2.0`).

This is a **false positive for this project**: the vulnerability exists in React Server Components (RSC) action handling. This project uses `react-router-dom` in client-rendered SPA mode only (no RSC, no server actions).

The advisory is patched in `react-router-dom@8.x`, which would be a major-version migration. Until then, the warning is acceptable. If `npm audit` ever surfaces additional advisories, treat them as real.
