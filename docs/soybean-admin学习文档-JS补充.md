# SoybeanAdmin JavaScript 补充教程

> 本文件**补充**《JavaScript入门到精通.md》中较少涉及、但进入 SoybeanAdmin 项目**极为常用**的 JavaScript 知识点。
> 阅读前提：已通读 JS 入门到精通（基础语法、函数、对象、BOM、DOM 等）。
> 本项目的 JS 运行在 **TypeScript + Vue3** 环境中，大量使用 ES6+ 语法（见《ES6补充教程》）和现代 JS 特性。

---

## 目录

1. [为什么本项目你需要再学这些 JS](#1-为什么本项目你需要再学这些-js)
2. [现代数组方法（高频）](#2-现代数组方法高频)
3. [对象方法扩展（高频）](#3-对象方法扩展高频)
4. [可选链与空值合并](#4-可选链与空值合并)
5. [解构赋值的项目实战](#5-解构赋值的项目实战)
6. [展开与剩余运算符的项目实战](#6-展开与剩余运算符的项目实战)
7. [字符串方法进阶](#7-字符串方法进阶)
8. [函数式思维：回调与迭代](#8-函数式思维回调与迭代)
9. [异步编程在项目中的形态](#9-异步编程在项目中的形态)
10. [项目中出现的 JS 反模式与规范](#10-项目中出现的-js-反模式与规范)
11. [实战：读一段本项目代码](#11-实战读一段本项目代码)

---

## 1. 为什么本项目你需要再学这些 JS

《JavaScript入门到精通》讲的是**纯浏览器 JS**（BOM/DOM/事件）。而 SoybeanAdmin 中：

- 几乎没有直接的 DOM 操作（改由 Vue 模板驱动）
- 大量使用**数据处理**（数组/对象的转换、过滤、映射）
- 大量使用**异步**（请求、await）
- 到处是**解构 + 展开 + 箭头函数**的组合

所以你需要把 JS 的重点从「操作页面」切换到「**操作数据**」。

---

## 2. 现代数组方法（高频）

《ES6教程》第七章讲了 `every/some/filter/forEach/map`，但项目里还有更高频的：

### 2.1 `.map()` 转换——用得最多

把一个数组变成另一个数组（同样是 ES6，但项目里几乎每个列表都用）：

```js
// 把页面名数组转成下拉选项数组
const options = allPages.map(page => ({ label: page, value: page }));
```
// 通俗理解：.map() ——"流水线加工厂"
> .map()是专门给数组使用的
```js
// 想象你现在有一条工厂流水线：
// 传送带上送过来一排原料数组：[1, 2, 3]
// 流水线上有一个工人（你的函数），给他的指令是："把送过来的每个东西都乘以 10"
// 出来一条全新的成品数组：[10, 20, 30]

// 用代码来看：
const numbers = [1, 2, 3];
// item 就代表传送带上依次送过来的每个元素 (先是 1，再是 2，最后是 3)
const newNumbers = numbers.map(item => item * 10);
console.log(newNumbers); // [10, 20, 30]
```
> .map() 的 3 个死规则：
> 1.进来几个，出去几个：原数组有 3 个元素，处理完后一定还是 3 个元素。
> 2.不改变原数组：原本的 numbers 依然是 [1, 2, 3]，它生成的是全新的数组。
> 3.=> 后面写什么，新数组里就放什么：
> - item => item + "号" ---> ["1号", "2号", "3号"]
> - item => "苹果"      ---> ["苹果", "苹果", "苹果"]

### 2.2 `.find()` 查找单个

返回**第一个**满足条件的元素（没有则 `undefined`）：

```js
const item = list.find(x => x.id === 3);
```

### 2.3 `.includes()` 判断包含

```js
if (!allPages.includes(routeName)) { ... }
```

### 2.4 `.filter()` 过滤（JS 教程有，项目常用）

```js
const active = list.filter(x => x.status === 1);
```

### 2.5 `.reduce()` 归约

把数组归并成单个值，项目常用于求和/分组：

```js
const total = arr.reduce((sum, item) => sum + item.count, 0);
```

### 2.6 链式调用

这些方法可以串联（ES6 教程提到但强调不够），项目里非常常见：

```js
const localIcons = Object.keys(svgIcons)
  .map(item => item.split('/').at(-1)?.replace('.svg', '') || '')
  .filter(Boolean);
```

> `.map()` 后接 `.filter()` 是最典型的组合。**记住：这些方法都不修改原数组，而是返回新数组。**

---

## 3. 对象方法扩展（高频）

《ES6教程》第十九章讲了 `Object.is/assign/setPrototypeOf`，项目里最常用的是：

### 3.1 `Object.keys()`/`Object.values()`/`Object.entries()`

把对象转成数组，用于遍历或转换：

```js
// keys：对象键的数组
const keys = Object.keys(svgIcons);

// entries：[[key, value], ...]，常用于遍历对象
const tagMap = { 1: 'info', 2: 'primary' };
Object.entries(tagMap).forEach(([key, val]) => { ... });
```

// 通俗理解 Object.keys() ——"只要菜单名，不要菜"
```js
// 想象你手里有一张菜单（对象 Object）：
// 宫保鸡丁：38 元
// 麻婆豆腐：22 元

// 在 JS 里写出来就是：
const menu = {
  "宫保鸡丁": 38,
  "麻婆豆腐": 22
};
// Object.keys(menu) 的唯一作用，就是把所有的“菜名（Key）”拔出来，装进一个数组里：
const dishNames = Object.keys(menu);

console.log(dishNames);
// 结果：["宫保鸡丁", "麻婆豆腐"]  （注意：价格/Value 被完全忽略了）
```
> 记住一句话：Object.keys(对象) 就是把对象的左边（键名）全部抽出来，变成一个数组。

### 3.2 `Object.assign()` 合并对象——项目合并表单数据

本项目在「编辑回显」时大量使用（`menu-operate-modal.vue`、`role-operate-drawer.vue`、`user-operate-drawer.vue`）：

```js
// 刷新时重置 model
model.value = createDefaultModel();

// 编辑时把行数据合并进 model
Object.assign(model.value, rest, { layout, page, routePath: path });
```


> `Object.assign(target, ...sources)`：把 sources 的属性复制到 target 上并返回 target。**后传入的覆盖前传入的**。这比手写 `a.x = b.x` 逐个赋值高效很多。

---

## 4. 可选链与空值合并

> 这两者是 ES2020 特性，**《JS教程》和《ES6教程》都没讲**，但项目里几乎每行都在用。

### 4.1 可选链 `?.`

安全地访问嵌套属性，中间任何一层是 `null/undefined` 就返回 `undefined`，不会报错：

```js
const iconName = item.split('/').at(-1)?.replace('.svg', ''); // 取不到就 undefined
formRef.value?.validate(); // formRef 不存在时不报错
```

对比传统写法（项目里已不用）：

```js
// 老写法
const x = (a && a.b && a.b.c);
// 新写法
const x = a?.b?.c;
```

### 4.2 空值合并 `??`

当左侧为 `null/undefined` 时，取右侧默认值。注意与 `||` 的区别：

```js
const name = value ?? '默认名';
// value 为 null/undefined 时取 '默认名'
// 但 value 为 0 或 '' 时 ?? 保留 0/''，而 || 会取 '默认名'
```

### 4.3 空值合并赋值 `??=`（项目少用但要知道）

```js
a ??= b; // 等价于 a = (a ?? b);
```

---

## 5. 解构赋值的项目实战

《ES6教程》第三章有解构，但项目里最常见的用法补充一下：

### 5.1 函数返回值解构（hooks 的核心）

项目所有 `useXxx` hooks 都返回对象，调用时解构：

```js
const { formRef, validate, restoreValidation } = useForm();
const { bool: visible, setTrue: openModal } = useBoolean();  // 可重命名
```

### 5.2 对象解构 + 剩余运算符剔除字段

提交前把辅助字段拆出来，剩余的作为参数：

```js
const { layout, page, pathParam, ...params } = model.value;
// params 里不含 layout/page/pathParam，直接作为请求参数
```

### 5.3 数组解构（较少但有用）

```js
const [newTemp, newHeight] = value;
```

---

## 6. 展开与剩余运算符的项目实战

《ES6教程》第九、十章讲了 rest 参数和 spread，补充项目场景：

### 6.1 数组复制与合并

```js
const allPages = [...props.allPages]; // 复制副本，避免改原数组
const newList = [...list1, ...list2]; // 合并
```

### 6.2 对象展开合并（比 Object.assign 更常用）

```js
const editingData = { ...item }; // 浅拷贝对象（本项目 menu/index.vue 常用）
const newObj = { ...obj, name: '新值' }; // 覆盖某属性
```

> 项目里 `{ ...item }` 常用来**浅拷贝后回显**，避免直接改原数据。

### 6.3 rest 剩余参数收集

```js
function foo(first, ...rest) { ... }  // rest 是数组
```

---

## 7. 字符串方法进阶

《JS教程》讲过基本字符串，补充项目高频的：

| 方法 | 作用 | 项目场景 |
|------|------|---------|
| `.replace('a','b')` | 替换 | 图标名去 `.svg` 后缀 |
| `.split('/')` | 按分隔符拆成数组 | 解析路径取文件名 |
| `.includes('xx')` | 是否包含 | 判断路由名 |
| `.trim()` | 去首尾空格 | 校验输入 |
| `.startsWith()`/`.endsWith()` | 判断开头/结尾 | 判断前缀 |
| `.toUpperCase()`/`.toLowerCase()` | 大小写 | 规范化 |

```js
// 示例：取图标文件名（去路径、去后缀）
item.split('/').at(-1)?.replace('.svg', '')
```

---

## 8. 函数式思维：回调与迭代

《JS教程》讲了函数，但项目用的是**回调式函数式编程**：

### 8.1 函数是一等公民（传给方法）

数组方法、`computed`、`watch` 的回调全部是「传一个函数」：

```js
const result = arr.filter(item => item % 2 === 0);  // 回调函数交给 filter
```

### 8.2 箭头函数简化（ES6教程第六章）

项目全程用箭头函数，且大量**简写**：

```js
// 单参单表达式（无 return、无花括号）
const double = n => n * 2;

// 用在回调里
arr.map(x => x + 1);
```

> **注意箭头函数的 `this` 是词法作用域**（继承外层），项目里回调里要用到外层 `this/value` 时箭头函数非常安全。

---

## 9. 异步编程在项目中的形态

《ES6教程》第十四章讲了 Promise，项目在此基础上使用 **async/await**（ES2017），更简洁：

### 9.1 `async/await`

```js
// 请求接口，拿到 { error, data }
const { error, data } = await fetchGetAllRoles();
if (!error) {
  roleOptions.value = data.map(...);
}
```

- `async` 函数内用 `await` 等待 Promise 完成
- 错误用 `try/catch` 或项目封装的 `error` 字段处理

### 9.2 项目的请求返回统一结构

```js
const { error, data } = await api();   // 解构出错误和数据
if (!error) { /* 成功处理 */ }
```

### 9.3 并行请求 `Promise.all`

需要并发请求时用（ES6教程讲过 all）：

```js
const [userRes, orderRes] = await Promise.all([getUser(), getOrder()]);
```

---

## 10. 项目中出现的 JS 反模式与规范

理解「项目为什么不这么写」：

| 反模式 | 问题 | 项目做法 |
|--------|------|---------|
| 直接改 DOM | 与 Vue 响应式冲突 | 全部交给模板绑定 |
| 用 `var` | 无块级作用域、易污染 | 一律 `const`/`let` |
| 手写 `for` 循环操作 DOM | 繁琐 | 用 `map`/`forEach` |
| `==` | 类型隐式转换有坑 | 用 `===` |
| 直接 `console.log` | 需手动清理 | 用 `no-console` 约束 |
| 修改原数组 | 难追踪 | 用展开 `.map` 生成新数组 |

---

## 11. 实战：读一段本项目代码

以 `src/utils/icon.ts` 为例，这一行就串起了本篇多个知识点：

```js
const keys = Object.keys(svgIcons)      // 1. Object.keys 拿所有键（字符串数组）
  .map(item => item.split('/')           // 2. 每个键用 '/' 拆成数组
              .at(-1)                    // 3. at(-1) 取最后一个元素 = 文件名
              ?.replace('.svg', '')      // 4. 可选链 + 去掉 .svg
              || '')                     // 5. 空值合并兜底成空串
  .filter(Boolean);                      // 6. 过滤掉空串（Boolean 简写）
```

**逐行拆解：**
1. `Object.keys(svgIcons)` → 拿到所有路径组成的数组
2. `.map(...)` → 对每个路径做转换
3. `.split('/').at(-1)` → 取最后一个 `/` 后的片段（文件名）
4. `?.replace('.svg', '')` → 去除 `.svg` 后缀；取不到则为 `undefined`
5. `|| ''` → `undefined` 时兜底为空串
6. `.filter(Boolean)` → 移除空串（`Boolean('' )=== false`）

这一小段就综合运用了：**Object.keys、链式方法、箭头函数、可选链、空值合并、filter(Boolean)**，正是本项目数据的典型处理方式。

---

## 附：本项目高频 JS 特性速查

| 特性 | 属于 | JS教程 | 本篇 |
|------|:---:|:---:|:---:|
| `.map()` / `.filter()` | ES5 | ✅ | ✅ 组合使用 |
| `.find()` / `.includes()` | ES6 | ❌ | ✅ |
| `Object.assign()` | ES6 | ✅ | ✅ 项目高频 |
| `Object.keys()` | ES5 | ⚠️ | ✅ 项目高频 |
| 可选链 `?.` | ES2020 | ❌ | ✅ |
| 空值合并 `??` | ES2020 | ❌ | ✅ |
| async/await | ES2017 | ❌ | ✅ |
| 对象展开 `{...x}` | ES2018 | ❌ | ✅ |
