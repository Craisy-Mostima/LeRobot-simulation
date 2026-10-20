# 在现有 AutoDL 实例补完实验

本步骤面向已验收 CUDA、EGL、SmolVLA，且已完成牛奶任务的实例。无需重装环境、重新克隆 LeRobot 或重新下载模型。

## 1. 上传工作流压缩包

在本地找到 `cloud_workflow.zip`，上传到 JupyterLab 的 `/root/autodl-tmp/course/`。不要把这个包传进模型缓存目录。它仅包含课程脚本、实验计划和工作流代码，不含模型或重复的牛奶录像。

在**云端 Terminal** 执行：

```bash
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate /root/autodl-tmp/course/conda-envs/lerobot
export HF_HOME=/root/autodl-tmp/course/huggingface
export HF_HUB_DISABLE_XET=1
export MUJOCO_GL=egl
export MPLBACKEND=Agg
cd /root/autodl-tmp/course
python -m zipfile -e cloud_workflow.zip .
python LeRobot-simulation-workflow/tools/workflow.py prepare
```

`prepare` 仅调用原版生成器创建并验证四个新任务；不会开始 VLA 评测。已经完成的牛奶任务会验证并跳过。生成器使用所选任务的 `y` 自动回答“生成并验证”，不改写原脚本。

## 2. 检查预览与 Goal

依次在 Jupyter 文件浏览器中打开以下 `.png`。路径中的 `/root/lerobot` 与当前 LeRobot 数据盘源码位置相连。

```text
/root/lerobot/custom_libero_tasks/scene_B/put_the_ketchup_in_the_basket.png
/root/lerobot/custom_libero_tasks/scene_B/put_the_butter_in_the_basket.png
/root/lerobot/custom_libero_tasks/scene_A/put_the_black_bowl_on_the_stove.png
/root/lerobot/custom_libero_tasks/scene_C/put_the_black_book_in_the_back_compartment_of_the_caddy.png
```

核对指令、场景、目标物体、位置和初始目标尚未满足。目标谓词在 `experiments/plan.json`，生成器输出也会显示。若报错或预览不对，保留日志，先解决后再运行评测。

## 3. 执行四个任务，各五次

确认预览后，在同一个已激活环境的云端 Terminal 执行：

```bash
python -u /root/autodl-tmp/course/LeRobot-simulation-workflow/tools/workflow.py evaluate
```

顺序为番茄酱、黄油、黑碗、黑书，共新增 20 次。程序逐个调用课程原版评测脚本，使用已下载缓存离线加载。每个任务保存独立日志、五段视频和 `results.json`。一个任务正常结束但成功率 0% 时会继续下一个；程序报错则停止，避免把运行错误当成任务失败。

终端需保持运行。若希望断开浏览器后继续，可先在云端运行 `tmux new -s course-eval`，在该会话中重新激活环境并执行上述命令；按 Ctrl+B 再按 D 脱离，之后 `tmux attach -t course-eval` 查看。不要同时运行两批评测。

每次最大步数沿用教师默认：A=300、B/C=520。视频的 26 秒等播放时长不是实际计算耗时；不能用一次 smoke test 推算整批必定多久完成。

重复执行会跳过完整的结果，保留牛奶的 0/5；若发现部分输出，会拒绝覆盖并给出目录。中断后先保留现场，把对应任务的不完整输出目录改名归档到项目外，再重试；不要删除或替换已经完成的失败结果。`prepare` 中断后的任务文件同理，先检查和归档；日志始终保留。

## 4. 验证并打包全部结果

看到 `BATCH COMPLETE` 后执行：

```bash
python /root/autodl-tmp/course/LeRobot-simulation-workflow/tools/workflow.py export --out /root/autodl-tmp/course/course_all_results.tar.gz
```

只有五个任务各五次、统计一致且全部录像存在时才会打包。包中包含任务文件、25 段原视频、原始统计、日志、环境快照、逐文件 SHA256。首次牛奶实验也会被收集。

从 Jupyter 下载 `/root/autodl-tmp/course/course_all_results.tar.gz`，放到本机这份课程目录，再交给助手检查、导入仓库和分析。下载确认完整后可关闭 GPU 实例；不要先释放仍保存唯一结果的磁盘。

本地导入命令（在本仓库目录执行）为：

```powershell
python tools/import_results.py ../course_all_results.tar.gz
```

导入器先验证压缩包路径、全部 SHA256、五任务统计和 25 个视频文件，再复制新文件。相同的旧牛奶文件会保留；同名内容不一致时停止，避免覆盖原始证据。导入会更新汇总表，报告和视频观察仍需根据实际内容填写。

## 5. 视频检查、报告与 GitHub

所有新增录像逐段检查：选中物体、抓持、搬运、放置、邻物碰撞、恢复、结束条件。填写 `experiments/video_review.csv`，把观察与假设区分开。保留全部失败视频，并选有代表性的成功/失败关键帧。

接下来更新自动汇总和七部分报告，核对引用与原始结果，再统一推送到目标仓库 `Craisy-Mostima/LeRobot-simulation`。目前本地项目只是准备状态，新增四个任务还没有成绩，不能写成已完成的 25 次实验。
