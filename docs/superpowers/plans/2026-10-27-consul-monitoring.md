# Consul 与监控管理 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement task-by-task.

**Goal:** 首批连接、目标、服务注册、同步记录和配置导出的前后端闭环。

**Architecture:** apps/consul 管连接和 Agent 客户端，apps/monitoring 管目标、注册语义和队列记录；引用现有 CMDB，复用通知/权限/审计框架。

**Tech Stack:** Django、DRF、Celery、requests、Vue3、Element Plus。

**Spec:** docs/superpowers/specs/2026-10-27-consul-monitoring-design.md

## Global Constraints

- Consul 核心，不做 HTTP SD 替代。Token 加密且不可读回，留空保留。
- 外部实例只读，稳定注册 ID；注册中的连接/目标不能被更改。
- 不执行部署迁移、真实注册/注销；测试外部 HTTP 采用 mock。
- 前端复用项目 UI、动态菜单，pnpm 校验；保留工作区已有修改，不提交。

## Review Focus

- Token 不进入返回值、日志、审计、异常；连接失败不能当空清单。
- 失败同步不丢失旧注册记录；重试不创建重复实例。
- 目标变更/删除不遗留注册；排队期间互斥。
- Blackbox 真实目标与 Exporter 地址不可混淆。
- 普通无权限用户不能访问新接口，菜单种子不覆盖用户图标。

## Task 1 — 连接和 Agent 客户端

- [x] apps/consul/test_consul.py 首先验证模块缺失；再实现 apps/consul 的 models、serializers、client、views、urls、migration。
- [x] 验证加密留空、URL 拒绝、超时/禁止重定向、服务列表、认证与审计。

## Task 2 — 目标及同步闭环

- [x] 写测试验证目标生成、reserved meta、外部 ID 冲突、注销、失败保留和重复队列拒绝。
- [x] 实现 monitoring/models.py、serializers.py、registration.py、tasks.py、views.py、urls.py 和迁移；API 同步排队，Celery run_sync(record_id)。
- [x] 生成 Prometheus Consul YAML 和基础告警规则，Blackbox relabel 正确。

## Task 3 — 前端与动态菜单

- [x] frontend/src/service/api/monitoring.ts 定义精确 DTO；新增 monitoring/consul、monitoring/targets 页面。
- [x] 接入 seed_data 菜单及权限；生成路由，表格居中、复用搜索组件、抽屉校验、Token 留空说明、错误和同步状态。

## Task 4 — 验证与文档

- [x] 隔离 backend 检查、迁移一致性、相关测试、OpenAPI；前端修改文件 lint/typecheck/build。
- [x] 独立复核修复后记录结果；部署文档注明迁移、初始化菜单和重启 API/Worker/Beat。

## 执行记录与裁决

- 在当前工作区实施，不移动或清除既有修改；未提交、未操作部署数据库、未访问真实 Consul/主机。
- Ruling: 首批只管理连接指向的 Agent 实例；跨节点 Catalog 浏览后续交付，避免将目录中的任意实例误当成本 Agent 可写资源。已同步修订设计。
- 独立复核确认的四项问题已修复并复核：节点检查聚合、注销后删除且保留历史、CMDB 主机选择、抽屉请求竞态保护。
- 外部写入不确定性单独保存；任务中断、超时后禁止直接删除/移动，先重试注册或注销确认。
- 官方 Prometheus Consul SD 结构不支持 `token_file`；使用其 HTTP 客户端 `authorization.credentials_file` 与 Consul Bearer 认证，不在导出中暴露 Token。
- 除不可信元数据地址、重定向外允许受控内网 Agent；URL 和 DNS 结果均检查已知元数据及链路本地地址。不引入任意健康检查脚本执行入口。
- 已通过：完整后端 1056 passed、6 skipped、39 subtests passed，仅第三方 django-celery-beat 的 2 条 UTC 弃用警告；最后补充的非法 URL 校验随新应用 24 项专项全部通过。权限/审计相关 98 项阶段回归、前端 83 项契约、修改文件 ESLint、类型检查、构建、Django 检查、迁移一致性、严格 OpenAPI 均通过。
- 真实 Consul/Prometheus 联调与浏览器视觉验收需在部署测试环境完成，见 `docs/2026-10-27-consul-monitoring-deployment.md`。
