# SoybeanAdmin ES6 补充教程

> 本文件**补充**《ES6教程.md》中没有、但进入 SoybeanAdmin 项目**极其常用**的现代 JavaScript（ES6+）知识点。
> 阅读前提：已通读《ES6教程》（let/const、解构、模板字符串、箭头函数、Array API、Promise、Set、Map、模块化等）。
> 本篇聚焦「ES6 教程没细讲、但项目代码里每行都在用」的高频语法。

---

## 目录

1. [ES2020+：可选链与空值合并（项目最高频）](#1-es2020可选链与空值合并项目最高频)
2. [ES2018：对象展开与 rest 简化](#2-es2018对象展开与-rest-简化)
3. [ES2017：async/await（替代 Promise 链）](#3-es2017asyncawait)
4. [ES6 之后的新数组方法](#4-es6-之后的新数组方法)
5. [satisfies / as const](#5-satisfies--as-const)
6. [Symbol 与迭代器在项目中的实际角色](#6-symbol-与迭代器在项目中的实际角色)
7. [Set/Map 的项目用法（超越教程）](#7-setmap-的项目用法)
8. [模块化的 TypeScript 形态](#8-模块化的-typescript-形态)
9. [其他高频 ES6+ 细节](#9-其他高频-es6-细节)
10. [实战：一段本项目代码的完整拆解](#10-实战一段本项目代码的完整拆解)

---

## 1. ES2020+：可选链与空值合并（项目最高频）

> 《ES6教程》没有任何 ES2020 内容，但这是**本项目每行都在用**的两个语法。

### 1.1 可选链 `?.`

访问可能不存在的属性/方法，安全短路：

```js
// 取图标名：路径取不到最后一段就返回 undefined，不报错
item.split('/').at(-1)?.replace('.svg', '')

// 调用可能不存在的表单实例
formRef.value?.validate()

// 深层嵌套不再需要层层 if
user?.profile?.name
```

对应老写法：

```js
// 老写法：三目或 && 链
const name = (user && user.profile && user.profile.name)
// 新写法
const name = user?.profile?.name
```

### 1.2 空值合并 `??`

左侧为 `null/undefined` 时取右侧默认值：

```js
const a = value ?? '默认值';
```

**与 `||` 的关键区别**（项目极易踩坑）：

```js
0 ?? '默认' // 0（?? 保留 0）
0 || '默认' // '默认'（|| 把 0 当 falsy）

'' ?? '默认' // ''（保留空串）
'' || '默认' // '默认'
```

> 需要「保留 0 / 空串」这类合法值时用 `??`；需要「过滤所有假值」时用 `||`。

### 1.3 `?.` 与 `??` 组合（项目常见）

```js
item.split('/').at(-1)?.replace('.svg', '') || ''
// 取不到 → undefined → 由 || 兜底为空串
```

---

## 2. ES2018：对象展开与 rest 简化

《ES6教程》讲了数组 spread（第十章）和 rest 参数（第九章），但**对象展开**（ES2018）没讲，而项目里极常用。

### 2.1 对象展开 `{ ...obj }`

```js
// 浅拷贝对象（回显数据前复制，避免改原数据）
const editingData = { ...item };

// 覆盖某属性生成新对象
const newObj = { ...obj, name: '新值' };

// 合并多个对象
const merged = { ...a, ...b };
```

> 与 `Object.assign` 效果类似但更声明式、更常用。

### 2.2 对象 rest 剔除字段（`...剩余`）

提交参数前把「辅助字段」拆出来，剩下的作为请求体：

```js
const { layout, page, pathParam, ...params } = model.value;
// params 里只剩提交给接口需要的字段
```

---

## 3. ES2017：async/await

《ES6教程》第十四章专注 Promise 和 `.then` 链。项目**全面使用 `async/await`**，更接近同步写法。

### 3.1 基本形态

```js
// 项目统一请求返回 { error, data }
const { error, data } = await fetchGetAllRoles();
if (!error) { /* 处理 */ }
```

### 3.2 `async` 函数

任何函数前加 `async` 即可在内部使用 `await`：

```js
async function getRoleOptions() {
  const { data } = await fetchGetAllRoles();
  roleOptions.value = data;
}
```

### 3.3 与 Promise 的关系

- `async` 函数**返回一个 Promise**
- `await` 会**暂停**该 `async` 函数，等待 Promise 完成
- 错误处理：`try/catch`，或使用项目封装的 `{ error, data }`

### 3.4 并行：`Promise.all`

```js
const [res1, res2] = await Promise.all([getA(), getB()]);
```

---

## 4. ES6 之后的新数组方法

《ES6教程》第七章到 ES5/ES6 为止。这些是更新的、项目常用：

| 方法 | 版本 | 作用 | 项目场景 |
|------|:---:|------|---------|
| `.find()` | ES6 | 返回首个匹配元素 | 查找目标项 |
| `.includes()` | ES2016 | 是否包含 | 判断是否存在 |
| `.flat()` | ES2019 | 数组拉平 | 展开嵌套数组 |
| `.flatMap()` | ES2019 | 映射+拉平 | 一对多映射 |
| `.at(-1)` | ES2022 | 从末尾取元素 | **`split('/').at(-1)` 取最后一段** |
| `.findIndex()` | ES6 | 查找下标 | 定位后删除 |

**`at()` 特别重要**——ES6 里取最后一个元素要写 `arr[arr.length - 1]`，现在直接用 `arr.at(-1)`：

```js
const fileName = path.split('/').at(-1);  // 取最后一个路径段
```

---

## 5. satisfies / as const

> 项目在 `useFormRules`（`src/hooks/common/form.ts`）等地方用了 `satisfies`，这是 TS 4.9+ 特性，《ES6教程》是 JS 教程当然没有，但看项目代码时需认识。

### 5.1 `satisfies`

让一个对象**既满足某个类型，又保留字面量精确类型**：

```ts
const grid = { 1: 'a', 2: 'b' } satisfies Record<number, string>;
// 类型检查符合 Record，同时保留具体键
```

### 5.2 `as const`

让值变成**只读字面量类型**（用于常量配置）：

```ts
const OPTIONS = ['a', 'b'] as const;
// type 变成 readonly ['a', 'b']
```

---

## 6. Symbol 与迭代器在项目中的实际角色

《ES6教程》第十一、十二章讲了 Symbol 和迭代器。在 Vue 项目中的实际体现：

- 数组、字符串、Set、Map 可被 `for...of` 遍历，靠的就是内部的 `Symbol.iterator` 接口。
- 本项目几乎**不手动创建 Symbol**，但**底层处处依赖**（如 Vue 的响应式内部也用到 Symbol）。
- 认识 `Symbol.iterator` 即可：能 `for...of` 的数据都可迭代。

```js
const arr = ['a', 'b'];
const it = arr[Symbol.iterator]();
it.next(); // { value: 'a', done: false }
```

---

## 7. Set/Map 的项目用法

《ES6教程》讲了 Set/Map 的增删查，补充项目中的实际形态：

### 7.1 Set 去重

```js
const unique = [...new Set(arr)];
```

### 7.2 Map 用作更灵活的映射表

比起用对象当映射，Map 的键可以是任意类型：

```js
const map = new Map();
map.set('key1', value1);
map.get('key1');
map.has('key1');
```

> 注意：项目里**大多用普通对象或 `Record`** 做映射（如表格列的 `tagMap` 用对象 `{ 1: 'info', 2: 'primary' }`），因为更简洁。Set/Map 在需要「键是对象」或「频繁增删」时才更合适。

---

## 8. 模块化的 TypeScript 形态

《ES6教程》第二十章讲了 ES6 模块（export/import）。本项目是 TypeScript，在此基础上：

### 8.1 `import type` 仅导入类型

```ts
import type { Ref } from 'vue';   // 只导入类型，编译后消失
```

### 8.2 命名导出 + 解构导入

```ts
// useForm.ts
export function useForm() { ... }

// 使用处
import { useForm } from '@/hooks/common/form';
const { formRef, validate } = useForm();
```

### 8.3 默认导出

```ts
// 某些组件/单值
export default function() { ... }
```

### 8.4 路径别名 `@/`

```ts
import SvgIcon from '@/components/custom/svg-icon.vue';
// @ 代表项目根目录 src/，由 vite 配置
```

---

## 9. 其他高频 ES6+ 细节

### 9.1 `const`/`let` 的团队习惯

项目遵循：**能用 `const` 就用 `const`；需要重新赋值才用 `let`；绝不用 `var`**。

```js
const option = {...};   // 不会重新赋值
let count = 0;          // 会变化
```

### 9.2 模板字符串已是标配

```js
const label = `${name} (${code})`;
```

### 9.3 默认参数 + 解构

```js
function connect({ host = '127.0.0.1', port = 3306 } = {}) { ... }
```

### 9.4 for...of 遍历

```js
for (const item of list) { ... }   // 遍历值
// 而不是 for...in（遍历键，易踩坑）
```

---

## 10. 实战：一段本项目代码的完整拆解

下面这段来自 `src/utils/icon.ts`，几乎串联了本篇所有知识点：

```js
const keys = Object.keys(svgIcons)      // 对象 → 键数组
  .map(item => item.split('/')           // 箭头函数 + split
              .at(-1)                    // at(-1) 取最后一段（ES2022）
              ?.replace('.svg', '')      // 可选链（ES2020）
              || '')                     // 空值合并（ES2020）
  .filter(Boolean);                      // 过滤空值
```

| 知识点 | 本篇章节 |
|--------|---------|
| `Object.keys` | JS补充 3.1 |
| `.map` 链式 | JS补充 2 |
| 箭头函数简写 | ES6六章 |
| `.split` + `.at(-1)` | 本篇 4 |
| `?.` 可选链 | 本篇 1.1 |
| `\|\|` 兜底 | 本篇 1.2 |
| `.filter(Boolean)` | JS补充 2 |

**这就是 SoybeanAdmin 数据的典型处理范式：函数式、链式、一次转换完成。**

---

## 附：本项目 ES6+ 特性速查表

| 特性 | 版本 | ES6教程 | 本篇 |
|------|:---:|:---:|:---:|
| 可选链 `?.` | ES2020 | ❌ | ✅ |
| 空值合并 `??` | ES2020 | ❌ | ✅ |
| 对象展开 `{...x}` | ES2018 | ❌ | ✅ |
| async/await | ES2017 | ❌ | ✅ |
| `.find()` / `.includes()` | ES6/ES2016 | ❌ | ✅ |
| `.at(-1)` | ES2022 | ❌ | ✅ |
| `satisfies` / `as const` | TS4.9 | ❌ | ✅ |
| `import type` | TS | ❌ | ✅ |
| for...of | ES6 | 部分 | ✅ 强调 |
