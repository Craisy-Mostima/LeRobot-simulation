# LeRobot simulation：自定义任务评测

使用 **LeRobot v0.6.1、LIBERO、SmolVLA**，在 AutoDL RTX 3090 上运行课程原版脚本。项目保存任务定义、原始统计、日志、全部 rollout 录像与分析；没有训练或微调模型。

**当前进度：1/5 个任务完成，共 5/25 次正式评测。** 其余四个任务属于待执行计划，不能计入成功率。完成补充实验并逐段检查视频后，再形成最终报告。

| ID | 场景 | 指令 | Episodes | 成功数 / 成功率 | 状态 |
| --- | --- | --- | --- | --- | --- |
| T01 | B | Put the milk in the basket. | 5 | 0/5，0.0% | 已完成并检查五段视频 |
| T02 | B | Put the ketchup in the basket. | — | 待测 | 已计划 |
| T03 | B | Put the butter in the basket. | — | 待测 | 已计划 |
| T04 | A | Put the black bowl on the stove. | — | 待测 | 已计划 |
| T05 | C | Put the black book in the back compartment of the caddy. | — | 待测 | 已计划 |

五个任务、每个五次是本项目的实验设计。课程建议每个最终任务至少五次，没有规定必须选五种任务。不同场景使用课程脚本各自默认的步数上限：A 为 300，B/C 为 520；每个任务固定初始状态索引 0，seeds 0–4。五次重复不等于五个不同布局。

## 从这里开始

- 已配置好的云端实例：[补充实验操作步骤](docs/next-steps.md)。
- 配置与复现说明：[运行环境](docs/environment.md)。
- 计划及机器可读结果：[plan.json](experiments/plan.json)、[summary.csv](experiments/summary.csv)。
- 已完成分析：[牛奶入篮报告](reports/T01_milk_basket.md)。
- 多任务报告：[待完成草稿](reports/report.md)。
- 原始课程要求：[PDF](docs/大作业操作指导.pdf)。

## 已完成的牛奶入篮任务

五次均执行到 520 步且未满足 `(In milk_1 basket_1_contain_region)`。录像中机械臂接近并扰动牛奶，随后抬起，但没有建立稳定抓持搬运，后续反复动作未恢复完成任务。视频不足以定位到唯一底层技术原因。

![牛奶任务四个关键时刻](figures/episode_00_关键帧.png)

| Episode | Seed | 结果 | 步数 | 原始录像 |
| --- | --- | --- | --- | --- |
| 00 | 0 | FAILURE | 520 | [播放 / 下载](artifacts/custom_vla_outputs/scene_B/put_the_milk_in_the_basket/episode_00.mp4) |
| 01 | 1 | FAILURE | 520 | [播放 / 下载](artifacts/custom_vla_outputs/scene_B/put_the_milk_in_the_basket/episode_01.mp4) |
| 02 | 2 | FAILURE | 520 | [播放 / 下载](artifacts/custom_vla_outputs/scene_B/put_the_milk_in_the_basket/episode_02.mp4) |
| 03 | 3 | FAILURE | 520 | [播放 / 下载](artifacts/custom_vla_outputs/scene_B/put_the_milk_in_the_basket/episode_03.mp4) |
| 04 | 4 | FAILURE | 520 | [播放 / 下载](artifacts/custom_vla_outputs/scene_B/put_the_milk_in_the_basket/episode_04.mp4) |

GitHub 的文件页是否内嵌播放取决于页面支持；链接始终保留完整原视频，可用 Raw 下载。视频每段约 1.3 MB，目前直接存入 Git，无需 LFS。未来单文件大于 100 MiB 时需使用 LFS 或 Release，参见 [GitHub 文件大小限制](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github)。

## 项目内容

```text
course_scripts/    课程原版两份 Python 脚本及 SHA256 校验
tools/             独立工作流工具；不修改模型、相机或动作处理
experiments/       五任务计划、汇总统计、逐段视频检查表
artifacts/         任务 BDDL/JSON/PNG、结果 JSON、全部 MP4、运行日志
figures/           视频关键帧与对照图
reports/           单任务分析与多任务报告草稿
docs/              环境、操作步骤、课程指导 PDF、来源说明
tests/             工作流的统计与覆盖保护检查（无需 GPU）
```

原始 JSON 保留 `/root/lerobot/...` 实验路径，便于核对，不修改原始证据。仓库阅读时使用上述相对链接。代码不包含模型权重、环境目录或账号凭据；复现实验需另外取得公开模型缓存。官方 smoke test 的 1/1 成功仅用于环境验收，不纳入自定义任务统计。

课程脚本与 PDF 的来源及原样保存情况见 [provenance](docs/provenance.md)。
