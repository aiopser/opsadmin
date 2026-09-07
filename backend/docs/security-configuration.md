# 安全配置（V2）

生产必须以 `DJANGO_SETTINGS_MODULE=devops.production_settings` 启动 API/ASGI/Worker，并显式提供独立的 `DEVOPS_SECRET_KEY`（至少 50 字符）、Fernet 格式 `DEVOPS_CREDENTIAL_ENCRYPTION_KEY`、逗号分隔 `DEVOPS_PRODUCTION_ALLOWED_HOSTS` 和 `DEVOPS_CORS_ALLOWED_ORIGINS`。部署数据库和队列必须是新环境，不能沿用旧环境；此文不授权部署。

凭据密文仅由独立凭据密钥解密，解密失败显式报错，不回退 Django SECRET_KEY 或旧格式。开发环境同样需要新凭据密钥；测试进程生成自己的临时密钥。

refresh 只从 JSON body 的 refreshToken 字段读取。退出接口同样要求该字段，只允许吊销当前用户的 token。refresh 吊销持久化到 SimpleJWT blacklist 表，保留第三方迁移。生产 access token 最长有效期为 5 分钟；退出不声称已吊销现存 access token，禁用用户会在每次认证时拒绝访问。

生产启用 CSRF 中间件保护 Session/admin 表单；DRF SessionAuthentication 自身执行 CSRF 验证，JWT Authorization header 认证不依赖 CSRF token。反向代理需正确提供 HTTPS 请求语义，当前未信任任意转发头。

2026-09-07 使用临时测试密钥及不可用本地数据库地址运行 `check --deploy`，未连接外部服务：退出 0，无 Django 安全告警；5 项现有 drf-spectacular schema 警告（日志 API 匿名 Serializer 3 项、dict_code 参数 1 项、PublicConfigApiView 无 Serializer 1 项）仍需 API schema 整理，不属于已通过的 OpenAPI 验收。

操作日志不记录 query/body/header，也不记录内部异常或错误响应原文。反向代理的访问日志同样必须省略查询串和敏感头；应用无法改写外部代理的历史日志。
