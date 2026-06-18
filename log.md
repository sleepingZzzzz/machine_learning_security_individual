# 实验记录 log.md

> 本文件为对外/可提交的实验主记录（私有深度反思见 .log/记录.md）。

## 记录原则（务必遵守）

1. **全量快照**：每次 exp 都把所有结果与超参存入 `runs/expN/`（config.json / run_manifest.json / results.csv / curves*.png / meta.json）。
2. **逐次入册**：每次实验都在本文件追加一条记录，不覆盖历史。
3. **每条记录必含**：① 与当前最 SOTA baseline 的对比结果；② 本次主要改动点；③ 潜在可迭代的方向。
4. **对比对象**：恒为「当前最 SOTA 的 baseline」，即 **n 最大的 `baselineN`**（不是简单的上一次实验）。
5. **对比呈现方式**：
   - 若对比双方的**评估数据类型一致**（同设定/同指标/可比样本）→ 用**一张表格并列**，计算 **δ 差值**，并附文字解析。
   - 若**评估数据类型不一致** → **分别给出 baseline 与本次实验的两张数据表**，不强行算 δ，附文字解析说明为何不可直接比。
6. **baseline 判定**：当某次实验在主指标上达到历史最佳时，记为 `baselineN`（N = 第几次历史最佳）。
7. **主指标定义**：本项目为攻击方视角，主指标 = 黑盒迁移设定下，目标（鲁棒）模型的 `pgd_transfer` AUC，**越低越强**；clean accuracy 与白盒 PGD 作参照，不同 track 不混比。

## baseline 索引

- **baseline1 = exp1**：流水线 + 白盒 PGD 有效性确立（攻击能力上界参照，当前最 SOTA baseline）。
- 迁移 track 暂无达成"强于 gaussian 基线"的记录（详见 exp2）。

---

## exp1 — 白盒有效性验证（baseline1）

- **时间**：2026-06-17 23:50 | **样本**：1000（均衡 1/类）| **设定**：white-box PGD（在被评模型自身上 craft）
- **超参**：PGD steps=20, random_start=True, step=eps/4；batch=16；ε∈{0, 1/255, 2/255, 4/255, 6/255, 8/255}；gaussian var=0.001 | **耗时**：431.7s

| 模型 | clean | pgd AUC（↓更强） | gaussian AUC | pgd@8/255 |
|---|---|---|---|---|
| Standard_R50（非鲁棒） | 0.769 | **0.001512** | 0.023749 | 0.000 |
| Engstrom2019Robustness（鲁棒） | 0.624 | 0.011282 | 0.019531 | 0.141 |

- **结论**：白盒 PGD 对非鲁棒模型 ε≥2/255 即打到 0%，对鲁棒模型缓降至 14.1%——攻击实现与流水线正确，鲁棒训练确有效。
- **与最 SOTA baseline 对比**：首次实验，无在先 baseline，本次即设为 baseline1。
- **主要改动点**：建立端到端流水线（数据子集 → PGD/gaussian → robust_accuracy → AUC(梯形) → runs 快照）。
- **潜在可迭代点**：① 进入更现实的黑盒迁移设定；② 扩大样本数稳定估计；③ 引入更多架构的鲁棒目标。
- **baseline 判定**：首次历史最佳 → **baseline1**（白盒攻击能力上界）。

---

## exp2 — 黑盒迁移（核心负面结果）

- **时间**：2026-06-18 22:17 | **样本**：4000（均衡 4/类）| **设定**：transfer（替身 Standard_R50 上 craft PGD → 迁移到 3 个 held-out 鲁棒目标）
- **超参**：PGD steps=20, random_start=True, step=eps/4；batch=64（显存 ~10GB）；ε 同 exp1；gaussian var=0.001 | **耗时**：1071.9s

### 与当前最 SOTA baseline（baseline1 = exp1）对比

评估数据类型**不一致**：baseline1 为 white-box / 1000 张 / 被评模型自身 craft；exp2 为 transfer / 4000 张 / 替身 craft 后迁移。两者设定与样本数均不同，**不可直接算 δ**，故分别列表。

**baseline1（exp1）数据表**

| 模型 | clean | pgd AUC | gaussian AUC | pgd@8/255 |
|---|---|---|---|---|
| Standard_R50（非鲁棒，白盒） | 0.769 | 0.001512 | 0.023749 | 0.000 |
| Engstrom2019Robustness（鲁棒，白盒） | 0.624 | 0.011282 | 0.019531 | 0.141 |

**本次（exp2）数据表**

| 目标模型 | clean | pgd_transfer AUC（↓更强） | gaussian AUC | transfer@8/255 |
|---|---|---|---|---|
| Engstrom2019Robustness | 0.619 | 0.019277 | 0.019374 | 0.610 |
| Singh2023 ConvNeXt-T-ConvStem | 0.729 | 0.022794 | 0.022891 | 0.725 |
| Singh2023 ViT-S-ConvStem | 0.715 | 0.022345 | 0.022425 | 0.710 |

**文字解析**：

- **核心发现**：exp2 中替身上的 `pgd_transfer` AUC 与 `gaussian` 噪声基线几乎相等（每个目标差距 <0.0001），三目标曲线全程平坦——**朴素 PGD 从非鲁棒替身到鲁棒目标的迁移≈无效**，未打出任何攻击信号。
- **与 baseline1 的跨设定对照**：同一攻击（PGD）对同一鲁棒模型 Engstrom，白盒（baseline1，AUC 0.011，@8/255 降至 0.141）有效，但迁移（exp2，AUC 0.019，@8/255 仍 0.610）后退化到与噪声同级。这一"白盒强、迁移废"的落差，正是本项目要攻克的迁移 gap，也是 exp2 的核心价值。
- 注：batch 16→64 仅影响显存/吞吐，不影响攻击效果；样本 1000→4000 仅提升估计稳定性。

- **主要改动点**：白盒 track → 黑盒迁移 track；替身/目标解耦（craft 一次、多目标共享）；样本 4×、新增 ConvNeXt-T / ViT-S 两种架构鲁棒目标；数据离线化（download.py --from-local-val 绕开 Kaggle 429）；修复 import re 快照 bug。
- **潜在可迭代点**：① 迁移增强（MI/DI/TI、CW margin loss）；② 集成替身（torchvision resnet50/convnext_tiny/vit_b_16/swin_t）；③ per-model 四图 + 替身白盒对照（已于工具侧实现，待带 --whitebox 实跑产出）；④ 用替身白盒曲线量化"迁移 gap"。
- **baseline 判定**：迁移攻击未强于 gaussian 基线，**未达成主指标历史最佳，不记新 baseline**；保留为迁移 track 的首个对照点与负面结论锚点。
