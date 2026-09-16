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

JSON 路径建议用 `/`；反斜杠必须写成 `\\`。两个平台的账号字段都需要填写。用户白名单禁止 `*`。

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

## Telegram 与本机 Codex 桌面共用任务

### 已上传什么，未自动化什么

- **已上传**：任务可见性修复及回归测试。检测到 `state_5.sqlite` 时，仅把目标任务的来源分类从 `exec` 改为 `cli`，不改写 JSONL 历史首行，避免破坏历史分页偏移。详情见 [分支说明](../../FORK-NOTES.zh-CN.md)。
- **未上传**：这台电脑已有的聊天历史、登录凭据和数据库；clone 仓库不会把这些数据带到笔记本。
- **未自动化**：既有历史迁移，以及此前通过“归档再恢复”释放桌面任务写入锁的本机操作。不要把可见性修复理解成完整的历史同步服务。

### 新电脑部署条件与验收

1. 从本仓库源码编译，不要用上游 npm / Release 程序替代，否则不保证包含本分支修复。
2. 在笔记本登录 Codex，使用模板的 `backend = "exec"`。确认 cc-connect 运行账号与桌面端一致，并核对两者实际使用同一个 Codex 数据目录（包括 `CODEX_HOME` 等覆盖设置）；不要为了绕过写入锁另建隔离目录，否则桌面无法直接共享那些任务。
3. 按本机配置填写工作目录、原生 Codex 路径、代理和平台凭据。启动同一机器人账号前，先停止另一台电脑的接入实例。
4. 从 Telegram 新建任务并发送测试消息，确认回复后，检查本机桌面端是否能找到该任务且历史正确。再通过 Telegram 的 `/list`、`/switch` 核对并选择同一任务；不要只凭标题判断是同一个任务。
5. 桌面与手机交替测试，不要同时执行；先验证文字、图片回复及任务可见性，再配置开机启动。如果不显示，先检查数据目录与程序版本，不要直接覆盖或改写历史文件。

### 写入锁仍有限制

本分支**没有解决** `already has an active writer`。即使桌面没有正在生成回复，也可能仍持有该任务的写入锁。本机曾验证的临时交接方式：确认任务执行结束后，在桌面归档再恢复该任务，随后不重新打开桌面任务，回 Telegram 继续。此操作不保证适用于所有 Codex 版本，也没有自动执行；不要删除锁文件或强行并发写入。

该修复依赖 Codex 内部数据库结构；换电脑或升级 Codex 后需要重新验收。把后端改成 `app_server` 不等于复用桌面现有服务，也不保证消除写入锁。

## 离线回归检查

```powershell
.\deploy\personal\check.ps1
```

仅在临时目录写入假凭据，检查路径、模板更新备份、白名单和本机配置保留行为，不连接平台、不启动或安装服务。
