# 📚 SoybeanAdmin 前端学习资料库

> 针对本项目的**前端学习笔记合集**，从零基础语法到能读懂并维护 SoybeanAdmin 工程。
> 本目录集中存放所有教程文档，并给出推荐的阅读顺序与学习路线。

---

## 📖 文档一览

| 文档 | 内容 | 定位 |
|------|------|:---:|
| `JavaScript入门到精通.md` | JavaScript 基础：变量、函数、对象、数组、BOM/DOM、事件 | 基础入门 |
| `ES6教程.md` | ES6 新语法：let/const、解构、模板字符串、箭头函数、Promise、Set/Map、模块化 | 基础入门 |
| `Vue3快速上手.md` | Vue3 核心：setup、ref/reactive、computed/watch、组件通信、pinia、路由 | 基础入门 |
| `soybean-admin学习文档-JS补充.md` | JS 教程缺失但本项目高频：可选链、async、Object.assign、函数式 | **项目补充** |
| `soybean-admin学习文档-ES6补充.md` | ES6+ 缺失但本项目高频：空值合并、对象展开、`.at()`、satisfies | **项目补充** |
| `soybean-admin学习文档.md` | Vue3 缺失但本项目高频：defineModel、script setup、icons、hooks、路由 + **完整学习路线** | **项目补充（核心）** |

---

## 🧭 推荐阅读顺序

```
JavaScript入门到精通 → ES6教程 → Vue3快速上手
        ↓                    ↓              ↓
JS补充文档         →    ES6补充文档  →  soybean-admin学习文档（核心）
```

**一句话路线**：先看基础（JS → ES6 → Vue3），再看「项目补充文档」（尤其主文档 `soybean-admin学习文档.md`），从基础语法平滑过渡到理解真实工程代码。

---

## 🚀 快速上手（新手必读）

如果你是新手、想尽快进入本项目，**优先阅读主文档**：

> 📄 **`soybean-admin学习文档.md`**

它的开头有「📚 学习资料索引」，文末（**第 15 章**）有完整的：

- **4 阶段学习地图**（JS → ES6 → Vue3 → 项目）
- **各阶段核心语法清单**（含重点方向）
- **5 步实操路径**（推荐从「弹窗表单」`menu-operate-modal.vue` 入手）
- **新手常见误区**

---

## 🗂️ 配套工程结构

学习时对照项目源码效果最好：

```
src/
  views/          路由页面（一个目录一个功能）
  components/     通用组件
  hooks/          复用逻辑（useXxx）
  store/modules/  pinia 状态
  service/api/    请求封装层
  router/         路由（文件系统路由）
  locales/        国际化文案
```

---

*本目录由个人学习整理而成，作为 SoybeanAdmin 项目的辅助学习资料。*
