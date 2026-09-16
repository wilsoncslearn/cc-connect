# 个人多电脑部署（Windows）

Git 同步源码、修复、此目录的部署脚本及共享配置；**不上传 Token、登录状态、聊天记录、数据库或各电脑的真实配置**。私密仓库也不作为凭据库。

## 交给 Agent 的部署提示词（Telegram + 本机 Codex）

如果目标是 **Telegram 文字/图片、手机 `/` 菜单、与桌面 Codex 共用历史、在指定侧栏项目下显示并可接续对话、验收后登录自启动**，可在 Agent 已打开本仓库的前提下直接输入：

> 请阅读并执行 `deploy/personal/README.zh-CN.md` 中“交给 Agent 的部署提示词（Telegram + 本机 Codex）”的完整要求，在当前 Windows 电脑完成部署或检查补齐已有部署。使用仓库现有修复和 YOLO 模板，只接 Telegram、复用本机 Codex，与桌面共用 Codex 历史，让 Telegram 创建的任务显示在我指定的桌面侧栏项目（例如 Telegram）下，验证项目归属、桌面续聊和手机命令菜单，通过验收后再配置登录自启动。本机路径、代理和凭据仅保存在本地；缺少的信息问我，不要猜，不要重复启动，不要自动提交或推送 Git。

### 完整要求（给执行 Agent）

以下是执行提示词，不是已经完成的验收结果。读取当前版本源码和本机状态后再操作；不要照搬另一台机器的路径、凭据、端口、版本号或验收结论。

```text
请在当前 Windows 电脑部署或完善本仓库的个人 Telegram + Codex 接入，实际执行并留下脱敏验收记录，不要只给我安装教程。

1. 先检查，不要覆盖已有部署
   - 阅读 AGENTS.md、本 README、FORK-NOTES.zh-CN.md、部署模板及相关实现。
   - 检查 Git 工作区、已有进程、计划任务和本地部署记录；优先复用已配置且正常的实例。
   - 未经明确要求不删除历史、不重置工作区、不拉取覆盖本地改动，不自动 commit/push。
   - 新部署先与我确认一个根目录，源码 repo 和本机运行目录 local 分开放在下面；local 必须在 Git 工作区外。已有部署不要擅自搬家。

2. 检查依赖和本机 Codex 可用性
   - 检查 Git、PowerShell、源码要求的 Go 版本、Codex 原生 exe 和本机现有配置。
   - 查看 Codex 登录状态，并执行一个不改文件的最小实际请求。若本机已有可用的自定义 provider，不要仅因 login status 显示未登录就要求重新登录。
   - 不覆盖 Codex 的模型、provider、凭据、代理或桌面配置。缺少依赖或凭据时告诉我；凭据通过本机文件填写，不要求我贴在聊天里。

3. 配置 Telegram-only 和 YOLO
   - 使用仓库已有修复及 YOLO/exec 模板，只保留 Telegram 平台；不要求填写微信，也不填假微信凭据来绕过检查。
   - 本机路径、Token、用户白名单和代理仅写入仓库外的本地文件，限制其 ACL；命令行、日志、截图、Git diff 和报告中不得泄露凭据。
   - 仅允许我提供并确认的 Telegram 数字用户 ID，不使用通配符；说明 YOLO 不提供 Codex 沙箱和命令审批。不要为了显示菜单而开启管理员权限。
   - 原 deploy.ps1 的 Check/Start/Install 面向双平台，且每次调用会刷新 config.toml；Telegram-only 应在本地做适配，不直接照用双平台入口。
   - 按仓库方式构建。Build 刷新模板后，在停机状态下恢复并校验本地 Telegram-only 配置，不丢失后续设置的 codex_home。

4. 验证网络和机器人身份
   - 读取本机已有、明确启用的代理，或向我询问；不要猜端口。只对需要的进程或 Telegram 配置代理，不改系统全局或 Codex 的网络配置。
   - 使用 getMe 验证当前 Bot 身份，检查 webhook 是否与现有用途冲突；不要擅自删除未知 webhook，也不要另起 getUpdates 消费者争抢消息。
   - 启动前提醒我停止旧电脑上使用同一个 Bot 的实例并获得确认；如果我确认是独立的新 Bot，则不必停用不同 Bot 的旧实例。

5. 与桌面 Codex 共用一份历史
   - 查明桌面实际使用的 CODEX_HOME，不把 cc-connect 的 data_dir 当成 Codex 历史目录。
   - 将机器人 agent.options.codex_home 在本地显式设为桌面同一目录；保留 cc-connect 自身的数据、会话映射和日志目录独立。
   - 复用本机 Codex 配置，不复制/替换数据库、登录状态或聊天文件，不为 Telegram 建另一套隔离的 Codex 历史。
   - 使用仓库现有任务可见性修复。若需要处理 source 分类，仅按当前版本兼容逻辑处理目标记录；不要改写 JSONL 首行或破坏字节偏移。
   - 明确说明：共用历史、先后续聊不等于支持同一任务同时被桌面和机器人写入。不要删除锁来绕过 active writer。

6. 让手机任务显示在指定的桌面侧栏项目下
   - 共享历史不等于项目归属。核实目标项目和 Telegram 任务 ID，优先使用桌面支持的入口关联；只处理本部署任务，不搬工作目录、不覆盖其他项目归属。
   - 必须离线修复时，先核实当前版本结构并备份，仅合并目标归属（部分版本为 .codex-global-state.json 的 thread-project-assignments），不改聊天、数据库或凭据；写入前复查进程和文件，原子写入并回读。脚本、ID 和备份只留本地。
   - 使用独立于 Codex 的一次性 Windows 计划任务等待用户正常退出，不依赖普通后台子进程；以当前用户运行，无开机/周期触发，有超时和日志。成功后重开桌面并清理任务，失败则报告，不强杀、不盲重试。
   - 按任务 ID 核验指定侧栏项目和历史，不能只看后台接口成功。已有任务补齐不代表后续新任务自动归组，后者须另行验证。

7. 注册并核验手机 / 命令菜单
   - 先用 getMyCommands 和 getChatMenuButton 检查默认菜单、当前私聊范围及相关语言覆盖。
   - 以当前运行版本实际支持并注册的命令为准，不编造命令、不固定命令数量。缺失或手机不显示时，补注册或刷新必要的范围/语言，将私聊菜单按钮设为 commands。
   - 修改前备份脱敏菜单记录，修改后通过 API 回读核验，再让我在手机重新进入聊天确认菜单可见；不能把 API 成功说成已验证手机画面。
   - 如添加私聊专属菜单，留下升级后从新默认列表刷新专属菜单的本地方法，避免旧列表覆盖新命令。

8. 实际验收后才能启用自启动
   - 与我配合验证 Telegram 文字回复、接收图片并正确识别、向 Telegram 发送图片。区分原生发图接口验证与模型主动调用工具回图，未测的不说通过。
   - 确认 Telegram 创建的任务出现在我指定的 Codex 桌面侧栏项目下，记录任务 ID、当时的标题及实际项目归属；不只检查全局列表或聊天文件存在。
   - 在机器人空闲并暂停后，对测试任务进行一次不调用工具、不改文件的桌面续聊验证，用原对话中的测试信息检验历史确实可读，且续写的是同一个任务。
   - 测试结束后安全释放桌面占用再恢复机器人，不让两端同时写入。当前版本若需归档再恢复来释放占用，先确认任务已结束，并复核恢复后的任务可见性；有 source 回退时复用仓库兼容修复，不删除历史。
   - 说明实际支持的交接方式与限制。不能验证的环节标为待确认，不伪造成功。

9. 安全交接到 Windows 登录自启动
   - 验收通过后复用仓库原生 daemon install，先停止手动实例并确认没有残留进程。安装会立即启动，不使用 --force 覆盖未知服务。
   - 检查安装器实际读取的文件名；当前实现使用工作目录下的 config.toml，不能以为 --config 指向其他文件名就会保留该文件名。
   - 捕获配置所需的本机环境变量，不设置 CC_DAEMON_NO_CAPTURE_SECRETS；启动脚本、备份和服务元数据视为敏感文件，限制 ACL。
   - 说明原生服务文件可能位于用户配置目录，而非部署根目录；不要为改变服务文件位置而修改 USERPROFILE 或另建 CODEX_HOME。
   - 检查登录触发、用户身份、隐藏窗口、启动延迟、电池供电、运行时间上限和防重复设置，并确认代理在登录后可用。不擅自更改全机电源/睡眠策略。
   - 不只看任务状态：确认只有一个目标 exe、Telegram 已连接、旧会话仍在、切换后仍能收发。
   - Windows 上停止计划任务可能留下子进程；只在确认本部署身份、exe 路径及任务空闲后处理残留。若有活动请求，等待完成而不是强杀。
   - 必要时生成仓库外的本地安全启动/停止/重启脚本，并验证它能处理残留进程。不要把登录后启动称为未登录即可运行，也不要声称已做未实际执行的重启测试。

10. 交付与维护
   - 将本机运行配置、管理脚本、项目归属修复/回滚记录、升级注意事项、菜单刷新方法和脱敏验收结果留在本地；共享文档只能包含通用步骤和占位符。
   - 提醒：安装时捕获的环境变量不会随 machine.local.json 自动更新；改凭据/代理后需要按原生流程安全重新安装，不是只重启。
   - 提醒：关机、睡眠或代理不可用时无法回复；源码 Git 同步不等于跨电脑同步配置和聊天历史。
   - 最后报告已通过、待确认、已知限制、实际目录和管理方法，核查 Git diff，确保没有本机信息或凭据进入仓库。
```

**使用边界：** 这段提示词用于复现流程，不是无需交互的一键安装器。新电脑仍需提供本机凭据、确认目录和同 Bot 的旧实例交接，并配合手机验收；依赖版本、网络和 Codex 内部结构变化可能需要重新验证。本机适配脚本不会因为只克隆源码就自动出现，Agent 应检查已有文件，缺少时在本地生成。项目归属修复可能需要正常退出桌面一次。

如果机器人已能正常回复，只需补齐这次的**桌面项目显示效果**，可单独输入：

> 请按 `deploy/personal/README.zh-CN.md` 第 6 项补齐桌面项目归属，让现有 Telegram 任务显示在我指定的项目下，并验证侧栏及历史。不重装、不搬目录、不改凭据，不提交或推送 Git。

## 手动部署入口（默认微信 + Telegram）

以下原生脚本示例仍面向双平台；只接 Telegram 时按上面的 Agent 要求在本地适配，不直接运行双平台 Check/Start/Install。

## 新电脑首次部署

前提：Git、Go 1.25+、已安装且实际请求可用的本机 Codex CLI 配置（官方登录或已有可用的自定义 provider；不要覆盖已有配置）。先克隆自己的私密仓库，再在仓库根目录执行：

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
- **未自动化**：既有历史迁移和桌面项目归属；已有任务修复不代表新任务自动归组，项目归属按上方第 6 项处理。单任务写入锁交接可另行安装下述 `/unlock`，不随基础部署自动启用。

### 新电脑部署条件与验收

1. 从本仓库源码编译，不要用上游 npm / Release 程序替代，否则不保证包含本分支修复。
2. 在笔记本登录 Codex，使用模板的 `backend = "exec"`。确认 cc-connect 运行账号与桌面端一致，并核对两者实际使用同一个 Codex 数据目录（包括 `CODEX_HOME` 等覆盖设置）；不要为了绕过写入锁另建隔离目录，否则桌面无法直接共享那些任务。
3. 按本机配置填写工作目录、原生 Codex 路径、代理和平台凭据。启动同一机器人账号前，先停止另一台电脑的接入实例。
4. 从 Telegram 新建任务并发送测试消息，确认回复后，检查本机桌面端是否能在指定侧栏项目下找到该任务、归属正确且历史完整。再通过 Telegram 的 `/list`、`/switch` 核对并选择同一任务；不要只凭标题判断是同一个任务。
5. 桌面与手机交替测试，不要同时执行；先验证文字、图片回复及任务可见性，再配置开机启动。如果不显示，先检查数据目录与程序版本，不要直接覆盖或改写历史文件。

### 写入锁仍有限制

桌面即使没有正在生成回复，也可能仍持有任务写入锁。下述 `/unlock` 自动执行本机验证过的单任务归档再恢复，并确认写入锁释放；这不是同时写入方案，手机接管后不要重新打开桌面同一任务。不要删除锁文件或强行并发写入。

该修复依赖 Codex 内部数据库结构；换电脑或升级 Codex 后需要重新验收。把后端改成 `app_server` 不等于复用桌面现有服务，也不保证消除写入锁。

## 离线回归检查

```powershell
.\deploy\personal\check.ps1
```

仅在临时目录写入假凭据，检查路径、模板更新备份、白名单和本机配置保留行为，不连接平台、不启动或安装服务。

## Windows 单任务交接命令 `/unlock`

手机发送 `/unlock`，桥接器直接运行固定脚本，不新建 Agent 对话、不调用模型。脚本通过 Windows UI Automation 调用桌面现有的**归档聊天 → 取消归档**控件，再读取实际写入锁确认释放。原任务保留，桌面后端不重启；手机收到成功提示后在原任务重发消息。

```text
/unlock                         # 释放当前手机绑定任务的桌面占用
/unlock <完整任务ID>             # 仅允许本聊天已经绑定的目标
/unlock check [完整任务ID]       # 只诊断，不操作桌面
/unlock confirm <旧确认码>       # 已停用，拒绝执行
```

目标不在本聊天绑定记录中时先 `/switch <完整任务ID>`；不接受任意 PID。无锁时不操作桌面；失败不会声称解锁成功。不会重发之前失败的手机消息。

### 安装条件与权限

1. 先安装支持 `{{request_b64}}` 和 `exec_allow_from` 的本分支桥接程序，不要只把配置复制到旧版。
2. Windows + Python 3.12（仅标准库）+ Windows PowerShell 5.1。将 `unlock.py`、`unlock-desktop.ps1` **放在同一私人运行目录**；其他用户不可写脚本、配置、状态或 Codex 数据目录。PowerShell 文件保留 UTF-8 BOM。
3. 固定 `--home` 为桌面 Codex 数据目录，`--workspace` 为任务实际工作目录，`--store` 为对应桥接 sessions JSON。若侧栏项目名称不同于工作目录末级名称，在本地 `exec` 开头设置 `$env:CC_UNLOCK_DESKTOP_PROJECT = 'YOUR_DESKTOP_PROJECT_LABEL';`，仅用于界面定位，不改变工作目录授权范围。脚本只读 Codex 数据库；归档状态由桌面原生操作更新，不直接改写聊天或学习进度。
4. 仅为该固定命令配置 `exec_allow_from`（精确用户 ID，以逗号分隔，不支持 `*`）。**无需设置 `admin_from`**，不会授予 `/shell`、重启或动态增添命令权限。
5. 首次修改配置需重启桥接器，先确认手机没有运行中的任务。已有命令只更新这两个脚本无需重启桌面或桥接器；不要启动重复机器人进程。
6. 重启后确认默认命令菜单包含 `unlock`；若此前设置过私聊或语言专属菜单，也须同步更新，否则旧菜单会遮蔽新命令。回读各作用域的 `getMyCommands` 验证后，在手机发送 `/unlock check` 验收；菜单注册成功不等于实际解锁成功。

以下是需要替换路径和 ID 的顶层配置示例：

```toml
[[commands]]
name = "unlock"
description = "释放当前任务的桌面占用（不结束进程）"
exec_allow_from = "YOUR_EXACT_USER_ID"
work_dir = 'C:\Users\YOU\.cc-connect\unlock'
exec = """[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new(); & 'C:\\Path\\To\\python.exe' -B -X utf8 'C:\\Users\\YOU\\.cc-connect\\unlock\\unlock.py' --home 'C:\\Users\\YOU\\.codex' --workspace 'C:\\Path\\To\\Project' --store 'C:\\Users\\YOU\\.cc-connect\\sessions\\PROJECT.json' --state-dir 'C:\\Users\\YOU\\.cc-connect\\unlock\\state' --request-b64 '{{request_b64}}' """
```

`{{request_b64}}` 安全传递桥接器提供的 `args`、`session_key`、`user_id`，不会把用户参数拼成 shell 源码；勿混用 `{{args}}`、`{{1}}`。只有可信本地配置可定义 exec 模板。

### 防护与已知边界

- Windows Restart Manager 与字节锁探测确认占用；检查 PID、创建时间、程序路径及桌面父进程。成功必须同时满足：任务已恢复、原后端仍运行、实际锁探测通过。
- 不含进程终止、锁文件删除、直接数据库写入或私有 IPC 控制。旧强杀确认码不再执行。
- 要求目标**唯一名称、未置顶、空闲且无待处理状态**，并能在已展开的项目侧栏中定位；不符合时拒绝操作，不猜测目标。
- 依赖可访问的桌面窗口和中文控件名称，会短暂打开设置页。不保证锁屏、无交互桌面、其他语言或未来版本；本机测试版本为 Codex 26.908.4834.0。
- 依赖内部 `state_5.sqlite`、`thread-writer-locks` 布局。升级后需重新验证。不是稳定的公开释放 API，也不是 Hana 的共享引擎远程控制。
- `state/desktop-ui.lock` 只串行化本脚本的界面操作，不是 Codex 写入锁。期间不要手动切换或操作目标任务；完成后不要在桌面重新打开它，否则可能重新持锁。
- 操作前写入 `state/<任务ID>.pending.json`。若已归档但恢复失败，下次 `/unlock` 会先恢复同一目标。身份不符或归档结果不确定时拒绝继续；按提示检查桌面，不要删除记录后盲目重试。
- `state/audit.jsonl` 记录请求与结果，只有 `released_verified` 表示完整释放验证成功。界面操作成功本身不等于已解锁。

### 回归检查

```powershell
python -B -X utf8 -m unittest discover -s deploy/personal -p test_unlock.py -v
go test ./core -run 'TestCUJ|TestExpandExecCommand|TestEngine_ScopedExec|TestEngine_AdminFrom_GatesCustomExecCommand'
go test ./config -run TestCommandConfig_ScopedExecRoundTrip
```

14 项 Python 测试覆盖授权、默认任务解析、归档恢复、失败恢复记录、身份变化、无锁与不误报成功；原生测试子进程收到输入后自行释放锁，不强杀进程。另在原始报错任务上实测原生控件交接成功，归档后恢复、锁已释放、原 Codex 后端 PID 和创建时间不变；这不等于已经观察到手机重发消息成功。
