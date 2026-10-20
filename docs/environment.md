# 环境与复现

## 已确认的运行环境

2026-10-20，AutoDL 云端实例：Ubuntu 22.04 基础镜像、RTX 3090 24GB、Python 3.12.15、PyTorch 2.8.0+cu128、torchvision 0.23.0、MuJoCo 3.8.1、LeRobot v0.6.1。CUDA 可用，EGL 创建成功，官方单任务 smoke test 完成。完整 `pip freeze`、GPU 与源码版本已由工作流实际采集，见 [环境快照](../artifacts/course_records/environment_20261020T031302_487523Z/)。

```text
源码                 /root/autodl-tmp/course/lerobot
课程脚本要求的入口   /root/lerobot（指向上述源码）
Conda 环境            /root/autodl-tmp/course/conda-envs/lerobot
HF_HOME               /root/autodl-tmp/course/huggingface
策略模型              lerobot/smolvla_libero
骨干模型              HuggingFaceTB/SmolVLM2-500M-Video-Instruct
```

这些路径描述当前实验实例。新环境可使用不同的存储位置，但必须让 `~/lerobot` 指向 LeRobot 工程，因为课程脚本固定使用此路径。不要在本仓库根目录直接 `pip install -e .`：本仓库是实验工程，LeRobot 依赖从上游单独安装。

## 新建环境时的主要安装命令

以下为当前成功环境的主要安装步骤，省略 AutoDL 账号和实例创建。默认 Ubuntu root 容器，先安装系统依赖：

```bash
apt-get update
apt-get install -y git ffmpeg libegl1 libgl1 build-essential tmux
mkdir -p /root/autodl-tmp/course
source "$(conda info --base)/etc/profile.d/conda.sh"
conda create -p /root/autodl-tmp/course/conda-envs/lerobot --override-channels -c conda-forge python=3.12 pip -y
conda activate /root/autodl-tmp/course/conda-envs/lerobot
cd /root/autodl-tmp/course
git -c http.version=HTTP/1.1 clone --branch v0.6.1 --depth 1 https://github.com/huggingface/lerobot.git
```

在 `~/lerobot` 不存在时建立链接：

```bash
ln -s /root/autodl-tmp/course/lerobot /root/lerobot
cd /root/lerobot
python -m pip install torch==2.8.0 torchvision==0.23.0 --index-url https://download.pytorch.org/whl/cu128
python -m pip install -e ".[smolvla,libero,evaluation]" "torch==2.8.0" "torchvision==0.23.0"
python -m pip install imageio imageio-ffmpeg matplotlib
python -m pip check
export HF_HOME=/root/autodl-tmp/course/huggingface
export HF_HUB_DISABLE_XET=1
export MUJOCO_GL=egl
export MPLBACKEND=Agg
```

不要重复执行 `ln -s` 到已有目录中；已有实例使用 [后续实验步骤](next-steps.md)。本项目不会自动下载权重。首次运行需要先按课程 PDF 完成模型缓存和官方验收，再切换离线评测。网络受限时可按 AutoDL 提供的 `/etc/network_turbo` 加速 GitHub/Hugging Face；其代理可能拖慢 pip，安装依赖与下载模型时分别检查网络。

模型缓存至少包含策略、视觉语言骨干的权重、配置、tokenizer/processor，以及 LIBERO 资产。单独下载一个 `model.safetensors` 不能替代完整缓存。

## 固定的评测协议

教师脚本两份原样保存在 `course_scripts/`，SHA256 见同目录 JSON。工作流通过独立子进程调用它们，不改相机、图像尺寸、动作适配或成功判定。新任务：5 episodes、CUDA、种子 0–4、固定初始状态索引 0、empty cameras 默认 1、视频默认 20 fps、观测默认 256×256。没有覆盖默认的 max steps。

Scene B 三个任务采用相同句式和目标篮子，改变目标物体。对象身份和形状等同时变化，不能把差异直接归因于某个单一物理属性。A/C 增加场景与目标类型覆盖，属于跨场景比较，不是严格的单变量消融。

## 本地核对

本地只需 Python 标准库即可检查已有材料和生成统计，不需要能工作的 CUDA GPU：

```bash
python -m unittest discover -s tests -v
python tools/workflow.py summarize --project-root artifacts --out experiments
```

原始日志、JSON 中的 `/root/lerobot` 是记录路径。下载后通过 `artifacts/` 同名层级读文件；恢复到新云端实验时，应重新生成任务元数据，不能直接把包含旧绝对路径的 JSON 当作可随处执行的配置。
