# AGENTS.md

本仓库为前后端一体仓库：前端基于 Soybean Admin（Element Plus 变体 `@sa/elp`），位于 `frontend/`；后端为 Django，位于 `backend/`。

## 必读规则（分层路由）

编辑代码前，先按文件类型加载对应技能文件并严格遵循：

| 目标文件 | 必读技能 |
| --- | --- |
| `**/*.vue` | `.agents/skills/vue-sfc-structure/SKILL.md`、`.agents/skills/ui-details/SKILL.md` |
| `**/*.{ts,tsx,js,jsx}` | `.agents/skills/typescript-functional-style/SKILL.md` |

更细的项目规则见 `.trae/rules/`（Trae 项目规则，自动生效）。

## 核心约束

- 技术栈：Vue 3 + Vite + TypeScript + Element Plus + UnoCSS + Pinia；pnpm monorepo，子包在 `frontend/packages/`（`@sa/*`）。
- 所有前端命令必须在 `frontend/` 目录下执行：`pnpm dev` / `pnpm build` / `pnpm typecheck` / `pnpm lint`。禁止使用 npm / yarn。
- 组件必须使用 `<script setup lang="ts">`，模板单一根元素；页面组件在 `frontend/src/views/` 下按路由结构组织，组件命名 `view.*` 约定。
- 优先复用 `@sa/*` 子包与 `frontend/src/hooks/` 既有实现；新增 helper 前先检查是否已存在。
- 样式优先 UnoCSS 原子类；Element Plus 全局定制样式只能写进 `frontend/src/styles/scss/element-plus.scss`。
- 路由由后端菜单控制（`VITE_AUTH_ROUTE_MODE=dynamic`），不在页面组件中硬编码路由路径。

## 禁止行为

- 禁止引入 Element Plus 之外的第三方 UI 组件库（本项目不使用 Naive UI / Ant Design Vue）。
- 禁止 `any` 类型、硬编码颜色值。

## 提交规范

- Conventional Commits：`type(scope): 中文 subject`；pre-commit / commit-msg 钩子会在 `frontend/` 下执行 typecheck、lint 与提交信息校验。

## 参考

- Soybean Admin 文档：https://docs.soybeanjs.cn
- Element Plus 文档：https://element-plus.org
