# 材料来源

- `course_scripts/libero_custom_task_builder.py` 与 `course_scripts/custom_vla_eval.py`：用户提供的课程代码，按原始字节复制，SHA256 记录在同目录。没有添加新的许可证或将其标记为原创代码。
- `docs/大作业操作指导.pdf`：用户提供的课程要求，作为实验方法参考。
- LeRobot：上游 [huggingface/lerobot](https://github.com/huggingface/lerobot)，实验固定 v0.6.1，不在此重复分发整个上游仓库。
- 策略 [lerobot/smolvla_libero](https://huggingface.co/lerobot/smolvla_libero) 和骨干 [SmolVLM2-500M-Video-Instruct](https://huggingface.co/HuggingFaceTB/SmolVLM2-500M-Video-Instruct)：实验时使用的公开模型，此仓库不存储权重。
- `artifacts/`：实际课程脚本生成的任务、统计、原始录像和运行日志；保留原始路径与失败记录。
- `figures/`：从原始录像抽取并排版的关键帧；用于分析，不是新生成的仿真结果。
- `tools/`、说明文档与报告草稿：本次实验整理时编写的辅助材料。辅助工具不修改教师评测逻辑。

各上游项目及课程材料的权利属于相应权利人；本项目不为第三方材料另行授予许可。报告中的实验观测与推断分开陈述。
