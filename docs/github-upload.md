# 项目上传与后续更新

目标仓库：[Craisy-Mostima/LeRobot-simulation](https://github.com/Craisy-Mostima/LeRobot-simulation)。源码、25 段 MP4、任务定义、日志、结果 JSON、环境快照、关键帧和报告保存在同一个仓库目录中。

本机仓库位于课程目录下的 `LeRobot-simulation` 文件夹。下载压缩包、模型权重和 Conda 环境不属于这个 Git 仓库；复现实验使用上游依赖与已记录的模型 ID。

## 查看上传后的内容

- GitHub 仓库首页 `README.md`：实验汇总与入口。
- `course_scripts/`：两份课程原版代码。
- `artifacts/custom_vla_outputs/`：五任务结果、全部 25 段原视频。
- `artifacts/course_records/`：原始日志、依赖和环境记录、校验清单。
- `artifacts/custom_libero_tasks/`：任务 BDDL、JSON、PNG。
- `reports/report.md`：多任务报告。
- `docs/artifacts.md`：按任务逐个列出视频与日志链接。

视频文件页面可用 Raw 下载；是否出现内嵌播放器取决于 GitHub 页面支持。仓库包含真实 MP4 文件。

## 以后修改文件后如何更新

在此仓库的 PowerShell 终端运行（若 Git 不在 PATH，使用本机 Git 程序的完整路径）：

```powershell
git status
git add .
git commit -m "Update experiment results and report"
git push origin main
```

`git status` 用于先查看待上传内容；没有新改动时无需创建空提交。首次推送可用 `git push -u origin main` 建立分支关联。当前视频都小于 2 MB，直接存入 Git，无需 LFS。

实验数据导入前运行 `tools/import_results.py` 验证导出包；已有证据内容不一致时会停止。原始文件按字节保存，Git 属性禁用了原始证据的换行转换，以保持 SHA256 可复核。
