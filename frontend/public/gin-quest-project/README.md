# Gin Quest · 任务管理 API

Go 1.25+，Gin 1.12.0，GORM 1.31.1，JWT v5.3.1；SQLite 使用 glebarez 纯 Go 驱动，无需安装 C 编译器或外部数据库。
这是可运行的教学项目，包含注册、密码哈希、短期 JWT、按用户隔离的任务 CRUD、分页、软删除、持久化、请求 ID、测试与优雅关闭。

## 先决条件与依赖

先从 https://go.dev/dl/ 安装当前受支持的 Go 稳定版本（至少 1.25）。旧版 Go 可能依照 go.mod 自动下载工具链，需要网络。目录中的依赖版本是本课程复现基线，不代表最新安全补丁；公网使用前审查依赖与运行环境。

所有命令在解压后的 gin-quest-project 目录执行。首次需要访问 Go 模块代理：

```text
go mod tidy
go test -tags=nomsgpack ./...
go vet -tags=nomsgpack ./...
```

nomsgpack 关闭本项目未使用的 MsgPack 绑定功能，减少编译依赖。保留 go.mod、go.sum，CI 中使用相同构建标记。

## Windows PowerShell

```powershell
$env:JWT_SECRET = go run ./cmd/key
go run -tags=nomsgpack . -migrate
go run -tags=nomsgpack .
```

## macOS / Linux

```sh
export JWT_SECRET="$(go run ./cmd/key)"
go run -tags=nomsgpack . -migrate
go run -tags=nomsgpack .
```

密钥仅在首次生成后安全保存；重启继续使用同一个 JWT_SECRET，不要每次重启重新生成。任何密钥变更都会使旧令牌失效。程序不会自动读取 .env 文件。
默认监听 127.0.0.1:8080，SQLite 文件 quest.db 位于工作目录。配置项：ADDR、DB_PATH、JWT_SECRET。不要提交真实密钥。
-migrate 使用 AutoMigrate 为本地教学库建表，执行后退出；生产环境应改为经过评审的版本化迁移。

## PowerShell 调用示例（另开终端）

```powershell
$base = 'http://127.0.0.1:8080/api/v1'
$body = '{"email":"you@example.com","password":"my-long-password-123"}'
Invoke-RestMethod "$base/auth/register" -Method Post -ContentType 'application/json' -Body $body
$login = Invoke-RestMethod "$base/auth/login" -Method Post -ContentType 'application/json' -Body $body
$headers = @{ Authorization = "Bearer $($login.access_token)" }
Invoke-RestMethod "$base/notes" -Method Post -Headers $headers -ContentType 'application/json' -Body '{"title":"Learn Gin"}'
Invoke-RestMethod "$base/notes?page=1&size=10" -Headers $headers
Invoke-RestMethod "$base/notes/1" -Method Patch -Headers $headers -ContentType 'application/json' -Body '{"done":true}'
Invoke-RestMethod "$base/notes/1" -Method Delete -Headers $headers
```

预期注册返回 201；登录返回 access_token；创建返回 201；查询与修改返回 200；删除返回 204 无正文。请在干净数据库上使用 id=1，其他情况使用创建响应中的 id。浏览器直接打开 /healthz 能测试存活，但不能替代登录 API 的调用。

## 接口契约

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | /healthz | 存活 |
| GET | /readyz | 数据库连接可用性，不检查全部表结构 |
| POST | /api/v1/auth/register | email、password |
| POST | /api/v1/auth/login | 返回 15 分钟 access token |
| GET | /api/v1/notes | page=1、size=10，size 最大 100 |
| POST | /api/v1/notes | title |
| GET | /api/v1/notes/:id | 当前用户的任务 |
| PATCH | /api/v1/notes/:id | 可选 title、done，至少一个 |
| DELETE | /api/v1/notes/:id | 当前用户的任务，软删除 |

业务错误形如 {"error":{"message":"…"}}。未知字段会被拒绝。正文上限 16 KiB。ShouldBindJSON 不保证拒绝尾随的第二个 JSON 对象，严格单文档协议需使用自定义解码器并确认 EOF；手册有说明。

## 构建与运行

```text
go build -tags=nomsgpack -trimpath -o gin-quest .
```

Windows 输出名改为 gin-quest.exe。仍需配置 JWT_SECRET，并先执行 -migrate。Ctrl+C 触发最多 5 秒的优雅关闭。

Docker（需要自行安装并运行 Docker，镜像构建需要网络）：

```sh
docker build -t gin-quest:local .
docker volume create gin-quest-data
docker run --rm --env JWT_SECRET --mount source=gin-quest-data,target=/data gin-quest:local -migrate
docker run --rm --env JWT_SECRET -p 127.0.0.1:8080:8080 --mount source=gin-quest-data,target=/data gin-quest:local
```

以上示例仅绑定宿主机回环地址。新建的命名卷由镜像初始化目录权限；使用已有卷或宿主机 bind mount 时，需保证 UID 10001 可写。备份 SQLite 前停止写入或使用 SQLite 的一致性备份机制，不要随意复制正在写入的文件。

## 测试覆盖与边界

测试包含登录、CRUD、false 零值更新、跨用户读/改/删隔离、分页限制、非法字段、错误密码、过期 JWT、签名算法限制、数据库重新打开后的持久化。
教学版未实现：登录限流、密码找回、刷新令牌/撤销、分布式部署、生产迁移、TLS 入口、CORS 前端集成、审计。要对外使用须先补齐相应功能与测试。SQLite 单连接为教学取舍，并非高吞吐架构。

PostgreSQL 迁移为手册中的扩展任务，当前源码与测试实际使用 SQLite，不声称已经验证 PostgreSQL 或容器部署。
