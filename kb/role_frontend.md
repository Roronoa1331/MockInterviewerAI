# 前端开发岗位知识库

## 岗位概述

前端开发工程师负责构建用户界面，使用 HTML、CSS、JavaScript 及现代框架（React、Vue）开发交互式 Web 应用。核心职责包括页面实现、性能优化、跨浏览器兼容性保障以及与后端 API 的集成。常见场景：SPA 单页应用、SSR 服务端渲染、移动端 H5、微信小程序。

## 核心技术栈

- **基础三件套**：HTML5（语义化标签、表单、Canvas/SVG）、CSS3（Flexbox、Grid、动画、变量）、JavaScript（ES6+）
- **主流框架**：React（Hooks、Redux、Context API、React Router）、Vue（2.x/3.x、Vuex/Pinia、Vue Router、Composition API）
- **TypeScript**：静态类型、接口（interface）、泛型、枚举、装饰器、tsconfig
- **工程化工具**：Webpack、Vite、Babel、ESLint、Prettier、Husky
- **Node.js 与全栈**：Express、Koa、Next.js（SSR/SSG）、Nuxt.js
- **测试**：Jest、Vitest、React Testing Library、Cypress（E2E）
- **网络与安全**：HTTP/HTTPS、CORS、WebSocket、XSS/CSRF 防御、CSP

## JavaScript 核心能力与评分要点

候选人应掌握：原型链与继承（prototype、__proto__、class 的语法糖本质）、闭包与作用域（词法作用域、变量提升、let/const 的块级作用域）、事件循环（EventLoop：宏任务 vs 微任务执行顺序）、Promise 与 async/await（链式调用、错误处理、并发控制 Promise.all/race）、ES6+ 特性（解构赋值、展开运算符、生成器/迭代器、Map/Set/WeakMap）、模块化（ESM 的静态分析 vs CommonJS 动态加载）。

**评分要点（技术知识维度）**：
- 满分回答：能准确解释底层机制，给出代码示例，说明实际应用场景与陷阱
- 中等回答：知道概念但无法说明原理，或给不出实际例子
- 低分回答：概念混淆（如闭包与作用域不分），或有明显技术错误

## CSS 与布局能力评分要点

候选人应掌握：盒模型（content-box vs border-box）、BFC（块级格式上下文触发条件与应用）、Flexbox 布局（flex 容器与项目属性）、Grid 布局（grid-template 定义、区域命名）、层叠上下文与 z-index、CSS 变量（--var 自定义属性）、CSS-in-JS（Styled Components/Emotion 原理）、媒体查询与响应式设计。

**评分要点（技术知识维度）**：
- 高分：能解释 BFC 消除浮动原因，说明 Flex/Grid 的适用场景差异
- 中分：能用但说不清原理
- 低分：对布局模型有明显误解

## React 与 Vue 框架深度评分要点

**React**：生命周期与 Hooks 的对应关系（componentDidMount→useEffect）、Hooks 规则与原理（useState 链表实现）、虚拟 DOM Diff 算法（同层比较、key 的作用）、性能优化手段（memo、useMemo、useCallback、Code Splitting 懒加载）、Concurrent Mode 与 Suspense 基本概念。

**Vue**：响应式原理（Vue 2 的 Object.defineProperty vs Vue 3 的 Proxy 对比）、组件通信方式（props/emit、provide/inject、Vuex/Pinia、EventBus）、Composition API 与 Options API 对比、v-if vs v-show 区别、keep-alive 原理、nextTick 原理。

**评分要点（技术知识维度）**：
- 高分：能比较两个框架的响应式原理差异，能分析优缺点
- 中分：熟悉一种框架但不了解其底层
- 低分：只会用 API 但无法解释行为

## 性能优化评分要点

候选人应了解：懒加载（Lazy Loading，图片/路由懒加载）、代码分割（Code Splitting：webpack SplitChunks/动态 import）、Tree Shaking（Dead Code Elimination）、CDN 加速与缓存策略（强缓存 Cache-Control、协商缓存 ETag/Last-Modified）、浏览器渲染流程（Parse HTML→CSSOM→Layout→Paint→Composite，回流 Reflow vs 重绘 Repaint）、Web Vitals（LCP 最大内容绘制、FCP 首次内容绘制、CLS 累计布局偏移、FID/INP 交互响应）。

**评分要点（技术知识维度）**：
- 高分：结合具体场景给出优化方案，并了解量化指标与工具（Lighthouse、Chrome DevTools）
- 中分：了解优化手段但无法说明为什么有效
- 低分：只提到"用 CDN"等表面手段

## 工程化与前端安全评分要点

**工程化**：Webpack 构建流程（Entry→Loader→Plugin→Output）、Loader 与 Plugin 的区别（Loader 处理文件转换，Plugin 是生命周期钩子）、HMR 热更新原理、Babel 编译 ES6→ES5 的流程（AST 转换）、monorepo 工具（Turborepo/Nx/pnpm workspace）。

**安全**：XSS（存储型/反射型/DOM 型，防御：转义输出、CSP）、CSRF（跨站请求伪造，防御：SameSite Cookie、CSRF Token）、点击劫持（X-Frame-Options）、HTTPS（TLS 握手、证书）、同源策略与 CORS（preflight 请求）。

**评分要点（技术知识维度）**：
- 高分：理解安全威胁的完整攻击链，能说明防御措施的实现细节
- 中分：知道威胁名称但不了解原理和防御
- 低分：对安全概念有明显误解

## 算法与数据结构评分要点

前端岗位要求基础算法能力：时间/空间复杂度分析、常见排序（快排、归并、堆排）、链表/树/图的遍历（DFS/BFS）、动态规划基础（背包、最长公共子序列）、哈希表应用、双指针/滑动窗口。

**评分要点**：能手写核心代码，分析复杂度，说明算法的应用场景。

## 综合评分规则

### 评分维度（满分 100 分）
1. **技术准确性（40 分）**：技术概念是否正确，有无明显错误
2. **深度理解（30 分）**：能否解释底层原理，而非仅背诵概念
3. **实战经验（20 分）**：能否结合项目经历给出具体示例
4. **表达清晰度（10 分）**：逻辑是否清晰，术语使用是否准确

### 难度分级
- **难度 1**（基础）：应届生或 1 年内经验，如 CSS 选择器优先级、基础 JavaScript 语法、HTML 语义化
- **难度 2**（中级）：2~3 年经验，能深入解释 React Hooks 工作原理、Vue 响应式机制、浏览器渲染流程
- **难度 3**（高级）：3 年以上，涉及性能优化方案设计、工程化配置、框架源码分析、架构设计

## 行为题评估要点

- **失败经历**：重点考察候选人是否有反思能力，能说明从失败中学到了什么，以及如何避免再次发生
- **冲突处理**：关注沟通方式和解决路径（技术讨论、需求对齐），而非结果是否完美
- **责任心与 Ownership**：是否主动承担任务，是否有端到端的交付意识，是否关注线上质量
- **技术决策**：能否说明某项技术选型（如选 Vue 还是 React）的理由和权衡
