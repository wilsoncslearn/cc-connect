# 此分支与原版的区别

比较基准：chenhg5/cc-connect 的 `757b4df0`，不是对上游未来版本的差异承诺。

## 源码改动

1. **微信正常回复不再误用主动推送额度**：依据回复上下文是否来自用户消息分类，普通文字和图片消息的回复走回复通道；定时任务等主动推送仍受原有限额约束。
2. **Codex 桌面任务可见性兼容修复**：检测到 `state_5.sqlite` 时，仅将目标任务的 `source` 从 `exec` 改为 `cli`，不改写 JSONL 首行，避免破坏分页历史使用的字节偏移。旧版无数据库的路径保持原逻辑。
3. **回归测试**：覆盖微信文字/图片回复在主动推送额度耗尽后仍可发送、主动推送仍受限，以及 Codex 仅更新目标行、保留任务标题、保持 JSONL 字节不变和重复执行。

## 不属于源码改动

- 微信与 Telegram 接入、`yolo` 权限模式原版已支持。
- `deploy/personal/` 新增共享的 YOLO 配置模板和 Windows 部署脚本，详见该目录的 `README.zh-CN.md`。各电脑的路径、代理及账号凭据放在仓库外的 `machine.local.json`，不提交；克隆本仓库不会自动启动服务。
- 历史迁移、备份及归档后恢复任务的操作属于本机修复，不是新增的自动同步功能。
- 不包含运行配置、Bot Token、登录凭据、聊天记录或本机编译的可执行文件。

## 已知限制

- 不支持桌面与 cc-connect 同时写入同一任务。`/unlock` 可自动执行单任务归档再恢复、验证释放后交给手机；依赖本机可访问的中文桌面控件，详见部署文档。手机接管后不要在桌面重新打开该任务，也不要删除锁文件。
- SQLite 修复依赖当前 Codex 的 `state_5.sqlite` / `threads.source` 内部结构，不是稳定公开接口；Codex 更新后需要重新验证。
- 改为 `backend = "app_server"` 不代表复用桌面现有服务，不能保证消除写入冲突。

## 定向回归检查

```sh
go test ./agent/codex ./platform/weixin ./platform/telegram -count=1
```

## 本次验证（2026-09-16，Windows）

- 上述三个模块的定向回归测试通过。
- `go build -tags 'no_web,goolm' ./cmd/cc-connect` 通过。
- 默认 `go test ./...` 未通过：缺少 Web 前端 `dist` 产物、部分测试依赖 Unix 命令/脚本或符号链接行为，且一次依赖下载超时；不能视为全量测试通过。

- 个人部署补充验证：PowerShell 7 / Windows PowerShell 5.1 离线脚本检查、临时目录编译及命令参数定向测试通过。`config` 包另有两项既有 Windows 路径测试失败（HOME 与 USERPROFILE、路径分隔符差异），未修改这些无关测试。

## Windows `/unlock`：由诊断升级为单任务交接

`deploy/personal/unlock.py` 与 `unlock-desktop.ps1` 通过原生 Windows UI Automation 归档再恢复目标任务，验证实际锁释放且原后端身份不变；没有强杀兜底、私有 IPC 伪造或数据库写入。旧确认码拒绝执行。复用自定义 exec 命令和 `{{request_b64}}` 数据封装、`exec_allow_from` 单命令白名单，不开放通用管理员权限。

仅操作当前聊天绑定、项目匹配、唯一名称、未置顶且空闲的目标。持久恢复记录支持归档成功但恢复失败后再次 `/unlock` 恢复；不确定时明确失败。两个脚本需安装在同一目录。细节及限制见 `deploy/personal/README.zh-CN.md`。

Hana 的 `/rc` 与 `/exitrc` 通过共享桌面引擎管理桥接附着关系；本实现不是该架构移植，也不承诺双端同时输入。当前 Codex 外部协同接口未提供本机所需的单任务释放入口，因此使用已验证的原生界面交接。

13 项 Python 回归通过；原始报错任务实测归档、恢复、锁释放成功，后端 PID 与创建时间保持不变。没有结束真实 Codex 进程，未宣称真实 Telegram 重发链路已验收。

此前定向 Go 测试和全部 CUJ 已通过。Windows 下 `go test ./core ./config` 的 6 个路径/HOME 相关失败，用 HEAD 原代码 overlay 复测同样失败；未把变更标为全套测试通过。
