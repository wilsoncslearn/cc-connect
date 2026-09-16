# 个人多电脑部署（Windows）

Git 同步源码、修复、此目录的部署脚本及共享配置；**不上传 Token、登录状态、聊天记录、数据库或各电脑的真实配置**。私密仓库也不作为凭据库。

## 新电脑首次部署

前提：Git、Go 1.25+、已安装并独立登录的 Codex CLI。先克隆自己的私密仓库，再在仓库根目录执行：

```powershell
.\deploy\personal\deploy.ps1 -Action Prepare
```

编辑 `%USERPROFILE%\.cc-connect\personal-deploy\machine.local.json`：

| 本机字段 | 填写内容 |
| --- | --- |
| `CC_WORK_DIR` | 这台电脑已有的工作目录，绝对路径 |
| `CC_CODEX_CMD` | Codex 原生 `.exe` 的绝对路径，不是 npm `.cmd` 包装脚本 |
| `CC_TELEGRAM_TOKEN` / `CC_TELEGRAM_USER_ID` | Bot Token / 允许使用的数字用户 ID；多个 ID 用逗号分隔 |
| `CC_WEIXIN_TOKEN` / `CC_WEIXIN_USER_ID` | 微信登录 Token / 允许使用的用户 ID |
| `CC_WEIXIN_ACCOUNT_ID` | 本机微信账号标识，默认 `default` |
| `CC_WEIXIN_BASE_URL` | 默认微信接口地址；一般不用改 |
| `CC_TELEGRAM_PROXY` / `CC_WEIXIN_PROXY` | 各平台本机代理；不用则保留空字符串 |

JSON 路径建议用 `/`；反斜杠必须写成 `\`。两个平台的账号字段都需要填写。用户白名单禁止 `*`。

```powershell
.\deploy\personal\deploy.ps1 -Action Check
.\deploy\personal\deploy.ps1 -Action Build
.\deploy\personal\deploy.ps1 -Action Start
```

- `Check` 只校验本机字段和路径，不验证 Token 是否有效，不连接机器人、不安装服务。
- `Build` 使用 `no_web,goolm` 标签，不含 Web 管理页面；可用 `-GoCommand 'C:/path/to/go.exe'` 指定 Go。
- `Start` 前台运行，Ctrl+C 停止。**不要在原有同账号实例仍运行时启动第二个实例。**
- 默认共享设置是 `mode = "yolo"`、`backend = "exec"`：Codex 不使用沙箱，也不请求命令审批。只授权自己，消息触发的操作拥有当前 Windows 用户权限。
- 路径使用 TOML 数组传递，保留路径中的空格。

需要开机启动时，先停止前台实例，再运行：

```powershell
.\deploy\personal\deploy.ps1 -Action Install
```

复用 cc-connect 原生 `daemon install`，安装后立即启动。已有服务时拒绝覆盖，不传 `--force`；迁移已有部署应先明确交接，不能直接并行启动。

安装程序会将配置引用的环境变量保存到本地计划任务启动脚本，**其中可能包含 Token**。本机 JSON、启动脚本、备份文件均视为敏感文件，不要上传。不要设置 `CC_DAEMON_NO_CAPTURE_SECRETS`，否则服务重启时不会自动保留这些变量。

## 更新与换电脑

1. 修改共享模板/源码/脚本后正常 `git add`、`git commit`、`git push`；另一台电脑 `git pull --ff-only`。这不是后台自动同步。
2. 各电脑独立保留 `machine.local.json`，不从其他电脑覆盖路径/代理。脚本不会覆盖已有本机 JSON。
3. 更新本机部署前，先停止该部署并确认进程退出，再运行 `Check`、`Build`。服务控制使用本机二进制的 `daemon stop` / `daemon start`。
4. 修改本机变量或新增模板环境变量后，已有服务捕获的环境不会自动更新；需要确认停止后卸载并重新安装该服务。单纯重启不会重新读取 JSON。
5. 同一个 Telegram Bot / 微信登录只保留一台电脑作为活动接入端；另一台接管前先停旧实例。此方案不提供多实例协调。

每次调用会刷新运行目录的 `config.toml`；内容不同则先保存带唯一后缀的 `.bak`。如果微信扫码工具将新 Token 写进了生成配置，**先转存到本机 JSON** 再刷新。不要把生成配置作为个人模板编辑。

可通过 `-RuntimeDir` 指定仓库外的另一目录；后续调用必须使用同一目录。不要使用指向仓库内的目录链接。脚本拒绝直接使用仓库内部目录，并在对应二进制仍运行时拒绝更新。

本方案不搬运 Codex 聊天历史、数据库、微信登录缓存，不解决桌面与手机同时写同一任务的锁冲突。当前正在运行的旧部署不会因为拉取这些文件自动改变。

## 离线回归检查

```powershell
.\deploy\personal\check.ps1
```

仅在临时目录写入假凭据，检查路径、模板更新备份、白名单和本机配置保留行为，不连接平台、不启动或安装服务。
