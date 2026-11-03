# 剩余功能联合交付 Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans within each independent domain, then integrate and review.

**Goal:** 完成用户批准的动态纳管、云资源/指标、治理提醒、JumpServer 与漏洞订阅代码及前端。

**Architecture:** 扩展 monitoring 与 cmdb，新增 cloud_governance、integrations、security；复用现有 RBAC、加密、Celery 和通知投递。数据库保存配置与采集结果，外部系统为可诊断的适配器。真实联调不能在没有部署凭据的情况下宣称通过。

**Tech Stack:** Django/DRF/Celery、Vue3/Element Plus、既有 SDK。

## Global Constraints

- 不连接真实外部系统，不读取部署 INI 或秘密文件，不执行部署数据库迁移。
- 不重置现有修改、不提交；前端遵循三项项目技能，pnpm 在 frontend 执行。
- 外部写操作仅限明确纳管对象，幂等更新；失败不能当作空清单或触发删除。
- 凭据加密、留空保留、不在响应/日志/标签泄露；执行前复核授权，定时任务有互斥、恢复和错误记录。
- 只声明实际已实现的提供方/资源类型；不支持或缺少 SDK 返回明确原因，不提供假按钮。

## Review Focus

- 新资产纳管范围和授权、配置更新与后台任务竞态。
- 分页/部分失败不会清空原资产或覆盖有效指标；缓存抓取不直接调用云 API。
- 通知去重、失败重试与事件状态，不把投递排队视为发送成功。
- JumpServer 映射、外部同名资产、协议/平台及实例标识。
- 漏洞解析变更、首次采集、重复公告、任意目标 URL 与通知模板转义。

## Tasks

- [x] 动态分组/规则纳管：持久策略、预览/确认、定时发现新主机，只管理本策略目标，不自动清理退出范围的主机；前端与测试。
- [x] 云资源：RDS/Redis 目录、云监控指标缓存和 Prometheus 出口、余额/到期策略与去重提醒，前端和支持矩阵。
- [x] JumpServer：配置/测试/预览/同步/记录、稳定映射与重试，前端和文档。
- [x] 安全订阅：公告采集、订阅筛选、历史、去重通知与重试，前端和文档。
- [x] 统一注册应用/路由/菜单/权限/Beat、迁移与 API 契约；独立复核和全量回归。
- [x] 文档记录真实环境验收清单和未具备的联调条件，不冒充验收通过。

## 交付与验收边界

代码与自动回归已完成，真实服务联调待测试环境验收。支持矩阵、部署顺序和验收清单见 [部署验收说明](../../2026-10-28-monitoring-completion-deployment.md)。不支持的云厂商不视为已完成适配。
