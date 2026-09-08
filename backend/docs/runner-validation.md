# Runner 隔离验证

T06 使用注入的 fake Runner 验证执行边界、失败/取消/超时、无回调、未知事件/no_log、adhoc 参数和目录生命周期。它不能证明真实 SSH、WinRM、网关或多 Worker 可用。

2026-09-08 本机为 Windows。`docker version --format '{{.Server.Version}}'` 无法连接 `docker_engine` 管道（文件不存在），并提示无法读取本机 Docker 配置。未启动 Docker、未拉取镜像、未连接任何生产或附件资产。因此 T07 的真实执行验收未完成。

`apps/ops/test_runner_integration.py` 提供明确 opt-in 的 localhost-only 真 Runner 用例（成功、失败、取消）。默认收集为 3 项 skipped，并清楚标注缺少隔离 Worker opt-in；它们不是通过项。在一次性 Linux Worker 内、安装项目锁定依赖及 Ansible 后执行：

```sh
DEVOPS_ISOLATED_RUNNER_TEST=yes python -m pytest apps/ops/test_runner_integration.py -q
```

测试使用固定 `localhost ansible_connection=local` 与 `/bin/true`、`/bin/false`、`/bin/sleep`，不能传入远程地址，不读取生产配置建立连接。执行目录自动清理。集成环境仍使用默认隔离测试 settings，不触及已有数据库。

未验证项：真实隔离执行成功/失败/取消、多主机、SSH 密钥、网关、WinRM、共享归档。需要可用的一次性 Linux Worker，以及后续明确授权的 Windows 测试目标。不要将 fake 或 SQLite 测试结果写作这些项目已完成。
