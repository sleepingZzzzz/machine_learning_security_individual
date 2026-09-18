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

- **baseline1 = exp1**：流水线 + 白盒 PGD 有效性确立（攻击能力上界参照）。
- **baseline2 = exp3**：首个有效的黑盒迁移攻击——把替身换成**鲁棒模型** Salman2020Do_R50 后，`pgd_transfer` 在**全部 4 个目标**（含非鲁棒 Standard_R50）上均强于 gaussian 基线。
- **baseline3 = exp9**：**鲁棒多架构集成替身**（Salman2020Do_R50 + Debenedetti XCiT-S12，概率平均 + MI）——4 目标均值 AUC 历史最佳，3/4 目标较 exp3 更强（含最难的 Transformer ViT-S 与非鲁棒 Standard_R50）。**当前最 SOTA baseline**。
  - *补充验证（同数据集，换样本量）*：exp10 用同款配方在官方均衡 **1000** 提交集上复跑，结论一致（详见 exp10），**不另记 baseline**。
  - *补充验证（换数据集）*：exp11 用同款配方迁到 **CIFAR-10** 均衡子集，4/4 目标仍强于 gaussian，跨数据集泛化成立（详见 exp11），**不参与 baseline AUC 排名**。

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

---

## exp3 — 鲁棒替身的黑盒迁移（baseline2，首个有效迁移攻击）

- **时间**：2026-06-18 23:55 | **样本**：4000（均衡 4/类）| **设定**：transfer（替身 **Salman2020Do_R50（鲁棒 RN50）** 上 craft PGD → 迁移到 4 个 held-out 目标）
- **超参**：PGD steps=20, random_start=True, step=eps/4；batch=64；ε 同前；gaussian var=0.001 | **耗时**：1299.4s
- **设定改动**：替身 Standard_R50（非鲁棒）→ **Salman2020Do_R50（鲁棒）**；目标集新增非鲁棒 **Standard_R50**（满足 PDF 第 8 条，且替身/目标完全 held-out 不泄漏）。

### 本次（exp3）数据表

| 目标模型 | clean | pgd_transfer AUC（↓更强） | gaussian AUC | δ=transfer−gaussian | transfer@8/255 |
|---|---|---|---|---|---|
| Standard_R50（非鲁棒） | 0.768 | **0.019500** | 0.023710 | **−0.004210** | 0.392 |
| Engstrom2019Robustness（鲁棒） | 0.619 | **0.015081** | 0.019388 | **−0.004307** | 0.326 |
| Singh2023 ConvNeXt-T-ConvStem（鲁棒） | 0.729 | 0.020480 | 0.022896 | −0.002416 | 0.554 |
| Singh2023 ViT-S-ConvStem（鲁棒） | 0.715 | 0.020141 | 0.022439 | −0.002298 | 0.555 |

**所有目标 δ 均为负 → 迁移攻击在每个模型上都强于 gaussian 基线**（满足 PDF line 17-18 的硬指标），exp2 的负面结论被逆转。

### 主要改动消融对比（exp3 vs exp2，同为 transfer / 4000 / batch64，仅替身不同）

评估类型一致（共享 3 个鲁棒目标，同设定）→ 用 δ 表。`pgd_transfer` AUC（↓更强）：

| 目标 | exp2（替身 Standard_R50，非鲁棒） | exp3（替身 Salman2020Do_R50，鲁棒） | δ=exp3−exp2 |
|---|---|---|---|
| Engstrom2019Robustness | 0.019277 | 0.015081 | **−0.004196** |
| Singh2023 ConvNeXt-T-ConvStem | 0.022794 | 0.020480 | **−0.002314** |
| Singh2023 ViT-S-ConvStem | 0.022345 | 0.020141 | **−0.002204** |

**文字解析**：仅把替身从非鲁棒换成鲁棒，三个鲁棒目标的迁移 AUC 全部显著下降；exp2 中 transfer−gaussian 仅 ≈−0.0001（等价噪声），exp3 升到 −0.0023～−0.0043（真实攻击信号）。**直接验证：鲁棒替身的对抗扰动更具可迁移性**（鲁棒特征语义对齐、跨模型通用性更强）。

### 与当前最 SOTA baseline（baseline1 = exp1）对比

评估类型**不一致**（baseline1 为 white-box / 1000；exp3 为 transfer / 4000），**不强行算 δ**，分别列表。

**baseline1（exp1，白盒）数据表**

| 模型 | clean | pgd AUC | gaussian AUC |
|---|---|---|---|
| Standard_R50（白盒） | 0.769 | 0.001512 | 0.023749 |
| Engstrom2019Robustness（白盒） | 0.624 | 0.011282 | 0.019531 |

（exp3 数据见上方"本次数据表"。）

**文字解析**：白盒是攻击能力上界。对同一鲁棒模型 Engstrom，迁移 AUC 已从 exp2 的 0.0193（≈gaussian）逼近到 exp3 的 0.0151，向白盒上界 0.0113 大幅靠拢——**迁移 gap 被实质性缩小**，但仍未达白盒水平，留有提升空间。

### 假设验证

"**在鲁棒目标上能打成功 ⇒ 在非鲁棒目标上也能打成功**"——**成立**。非鲁棒目标 Standard_R50 在 ε=8/255 下 robust acc 从 0.768 暴跌到 0.392（gaussian 仅到 0.741），是绝对降幅最大的目标；同一攻击对鲁棒目标也普遍有效。

- **主要改动点**：替身 非鲁棒→鲁棒（Salman2020Do_R50）；目标集 +Standard_R50（非鲁棒被评估目标，held-out）；四宫格 per-model panels 产出（`curves_panels.png`）。
- **潜在可迭代点**：① loss CE→CW/margin；② 迁移增强 MI/DI/TI；③ 集成替身（鲁棒+非鲁棒混用，权衡 craft 成本）；④ 进一步缩小与白盒上界的 gap；⑤ 带 `--whitebox` 出替身白盒对照虚线，量化迁移 gap。
- **baseline 判定**：主指标（目标 pgd_transfer AUC，且需强于 gaussian）首次在迁移设定下达成且全目标有效 → **历史最佳，记为 baseline2**。

---

## exp4 — 鲁棒替身 + 经典迁移增强（margin+MI+DI+TI，负面结果，未升级 baseline）

- **时间**：2026-06-19 00:55 | **样本**：4000 | **设定**：transfer（替身 Salman2020Do_R50，4 目标 held-out），与 exp3 唯一差异 = 攻击方法
- **超参/增强**：loss=**margin**，MI momentum=1.0，DI prob=0.7，TI kernel=5(σ=3.0)；PGD steps=20，step=eps/4，batch=64 | **耗时**：1387.2s

### 与当前最 SOTA baseline（baseline2 = exp3）对比

评估类型**一致**（同 transfer / 4000 / 同替身 / 同目标，仅攻击方法不同）→ 用 δ 表。`pgd_transfer` AUC（↓更强）：

| 目标 | exp3（朴素 PGD） | exp4（margin+MI+DI+TI） | δ=exp4−exp3 |
|---|---|---|---|
| Standard_R50（非鲁棒） | **0.019500** | 0.021416 | **+0.001916 ❌明显变弱** |
| Engstrom2019（鲁棒） | **0.015081** | 0.015408 | +0.000327 ❌略弱 |
| Singh2023 ConvNeXt-T（鲁棒） | **0.020480** | 0.020585 | +0.000105 ≈持平 |
| Singh2023 ViT-S（鲁棒） | **0.020141** | 0.020281 | +0.000140 ≈持平 |

ε=8/255 处 robust acc（↓更强），变弱更直观：

| 目标 | exp3@8/255 | exp4@8/255 | 攻击变弱 |
|---|---|---|---|
| Standard_R50 | 0.392 | 0.565 | **+17.3pp** |
| Engstrom2019 | 0.326 | 0.360 | +3.4pp |
| Singh ConvNeXt-T | 0.554 | 0.566 | +1.1pp |
| Singh ViT-S | 0.555 | 0.563 | +0.8pp |

**文字解析（核心发现）**：四件套在所有目标上均略降，且**变弱幅度随目标对高频(非鲁棒)特征的依赖度递增**（非鲁棒 ≫ 鲁棒RN50 > 鲁棒CNN/ViT）。机制：
1. **TI 高斯平滑低通滤波梯度、抹掉高频分量**，而非鲁棒模型最吃高频扰动 → 专门"误伤"Standard_R50（17pp）。
2. **替身已是鲁棒模型，其扰动本就低频/语义化/可迁移**（exp3 成功之因）；再叠 DI/TI 无新可迁移性可挖，只剩牺牲攻击强度，边际收益为负。
3. **DI 在难攻的鲁棒替身上稀释已弱的梯度**。
结论：**鲁棒替身的迁移性与经典 MI/DI/TI 不叠加，TI 与"攻击非鲁棒目标"直接冲突。**

- **主要改动点**：在 exp3 基础上加 `transfer_pgd_linf`（margin+MI+DI+TI），其余不变。
- **潜在可迭代点**：① 消融定位元凶（先关 TI，再 margin-only）；② 结构杠杆=集成替身（鲁棒+非鲁棒混用，直面频率权衡）；③ 鲁棒替身欠优化时增 PGD steps。
- **baseline 判定**：弱于 baseline2，**不升级 baseline**；记为"鲁棒替身 × 经典增强不叠加"的边界发现。

---

## exp5 — 仅 margin loss（消融：归因定位，未升级 baseline）

- **时间**：2026-06-19 01:xx | **样本**：4000 | **设定**：transfer（替身 Salman2020Do_R50，4 目标 held-out），与 exp3 唯一差异 = loss（CE→margin）
- **超参/增强**：loss=**margin**，MI=0，DI=0，TI=0（其余全关）；PGD steps=20，step=eps/4，batch=64 | **耗时**：1560.6s

### 与当前最 SOTA baseline（baseline2 = exp3）对比

评估类型**一致**（同 transfer / 4000 / 同替身 / 同目标，仅 loss 不同）→ δ 表。`pgd_transfer` AUC（↓更强）：

| 目标 | exp3（CE） | exp5（margin） | δ=exp5−exp3 |
|---|---|---|---|
| Standard_R50（非鲁棒） | 0.019500 | 0.019577 | +0.000077 |
| Engstrom2019（鲁棒） | 0.015081 | 0.015207 | +0.000126 |
| Singh2023 ConvNeXt-T（鲁棒） | 0.020480 | 0.020427 | −0.000053 |
| Singh2023 ViT-S（鲁棒） | 0.020141 | 0.020058 | −0.000083 |

**所有 |δ| < 1.3e-4，两升两降，小于 PGD 随机起点的 run-to-run 波动** → margin 与 CE 在鲁棒替身迁移设定下**效果无法区分，纯中性**。

### 归因结论（三轮串联）

| 实验 | 攻击方法 | 相对 exp3 |
|---|---|---|
| exp3 | CE 朴素 PGD | baseline2（基准） |
| exp4 | margin+MI+DI+TI | 明显变差（非鲁棒 −17.3pp@8/255） |
| exp5 | **仅 margin** | ≈持平 |

**文字解析**：exp5(仅 margin)≈exp3 → margin 不是 exp4 退步主因；故 **exp4 的退步全部来自 MI/DI/TI**（TI 低通滤波误伤高频敏感的非鲁棒目标；鲁棒替身上 DI/TI 边际收益为负）。margin 中性的原因：鲁棒替身损失曲面平滑、梯度良态，CE 未饱和，margin 与 CE 指向几乎相同。

- **主要改动点**：在 exp3 基础上仅把 loss 换成 margin。
- **潜在可迭代点**：① 单独测 margin+MI / margin+DI / margin+TI 拆分各组件正负收益（→ exp6/7/8）；② 结构杠杆=集成替身（鲁棒+非鲁棒混用）。
- **baseline 判定**：与 baseline2 无显著差异，**不升级 baseline**；价值在于"margin 中性 + 锁定 MI/DI/TI 为 exp4 元凶"的干净归因。

---

## exp6 / exp7 / exp8 — 单组件拆分消融（margin+MI / +DI / +TI，均未升级 baseline）

- **时间**：2026-06-19 上午 | **样本**：4000 | **设定**：transfer（替身 Salman2020Do_R50，4 目标 held-out），batch=32（防显存溢出），均在 margin 基础上各开一个组件
  - **exp6 = margin + MI**（momentum=1.0）｜耗时 1680.3s
  - **exp7 = margin + DI**（di_prob=0.7）｜耗时 1706.7s
  - **exp8 = margin + TI**（ti_kernel=5, σ=3.0）｜耗时 1707.6s
- **目的**：在替身为鲁棒模型的前提下，逐一判定 MI/DI/TI 各自的正负收益。

### 主对照表：`pgd_transfer` AUC（↓更强，加粗=该行最强；对比对象 baseline2=exp3，同设定）

| 目标 | exp3 CE | exp5 margin | exp6 +MI | exp7 +DI | exp8 +TI |
|---|---|---|---|---|---|
| Standard_R50（非鲁棒） | **0.019500** | 0.019577 | 0.019646 | 0.020473 | 0.021163 |
| Engstrom2019（鲁棒RN50） | **0.015081** | 0.015207 | 0.015197 | 0.015109 | 0.015596 |
| Singh ConvNeXt-T（鲁棒） | 0.020480 | 0.020427 | **0.020375** | 0.020379 | 0.020725 |
| Singh ViT-S（鲁棒） | 0.020141 | 0.020058 | **0.020001** | 0.020137 | 0.020337 |
| **4 目标均值** | **0.018801** | 0.018817 | 0.018805 | 0.019025 | 0.019455 |

均值排序：**exp3 ≈ exp6(MI) < exp5(margin) < exp7(DI) < exp8(TI)**。

### 非鲁棒 Standard_R50 @8/255（最干净信号，↓更强）

| exp3 CE | exp5 margin | exp6 +MI | exp7 +DI | exp8 +TI |
|---|---|---|---|---|
| 0.392 | 0.402 | 0.412 | 0.465 | 0.544 |

**单调变弱**：每叠加一个组件对非鲁棒目标都更弱，TI 最甚。

### 各组件正负收益裁定（替身=鲁棒模型前提下）

- **MI（exp6）：整体中性**。对跨架构鲁棒目标（ConvNeXt/ViT）微小正收益，对同架构 RN50（Standard/Engstrom）微小负收益，净 ≈ 0；与 baseline2 并列（均值差 4e-6，纯噪声）。
- **DI（exp7）：净负**，几乎全压在非鲁棒 Standard_R50（AUC +0.00097，@8/255 退 7pp），鲁棒目标基本中性。
- **TI（exp8）：净负且最重，所有目标都退**，非鲁棒最甚（AUC +0.00166）。坐实 exp4 退步主因 = TI（低通滤波误伤高频）。
- 伤害排序：**TI ≫ DI > MI(≈0)**。

**文字解析（结论）**：在**替身为鲁棒模型**的条件下，margin / MI / DI / TI **没有任何一个带来明确正收益**——margin、MI 中性，DI、TI 反噬（尤其对非鲁棒目标）。原因：鲁棒替身产生的扰动本就低频、语义化、可迁移（baseline2 成功之因），这些为"非鲁棒替身过拟合"设计的增强在此无可迁移性可挖，DI/TI 的正则/平滑反而牺牲攻击强度。**故这几个组件均不构成新 SOTA，baseline2(exp3) 保持不变。**

- **主要改动点**：在 exp5(margin) 基础上各单开一个组件（exp6 MI / exp7 DI / exp8 TI）。
- **潜在可迭代点**：① 唯一具微弱跨架构正向的 MI，仅值得带入"集成替身"轮叠加验证；② 结构杠杆=集成替身（鲁棒+非鲁棒混用）；③ 其它结构方向：更强优化器（APGD）、增 PGD steps、更换/扩充鲁棒替身、ILA 中间层特征攻击。
- **baseline 判定**：三者均与 baseline2 无显著差异或更差，**均不升级 baseline**。

---

## exp9 — 鲁棒多架构集成替身（baseline3，新 SOTA）

- **时间**：2026-06-19 12:xx | **样本**：4000 | **设定**：transfer（4 目标 held-out），batch=32 | **耗时**：3341.7s（≈56min，×2 craft）
- **替身**：**Ensemble[Salman2020Do_R50 + Debenedetti2022Light_XCiT-S12]**（鲁棒 CNN + 鲁棒 Transformer），**概率平均**组合（解决 logit 尺度失配），loss=CE，MI=1.0，DI=0，TI=0
- **设计依据**：exp4–exp8 证明经典攻击增强在鲁棒替身上无正收益 → 转向结构杠杆；集成多样性应由**高质量鲁棒成员**提供，故选纯鲁棒、跨架构（CNN+Transformer）。

### 与当前最 SOTA baseline（baseline2 = exp3）对比

评估类型**一致**（同 transfer / 4000 / 同 4 目标，仅替身：单鲁棒→鲁棒集成）→ δ 表。`pgd_transfer` AUC（↓更强）：

| 目标 | exp3（单 Salman） | exp9（集成） | δ=exp9−exp3 |
|---|---|---|---|
| Standard_R50（非鲁棒） | 0.019500 | **0.018044** | **−0.001456 ✅** |
| Engstrom2019（鲁棒RN50） | **0.015081** | 0.015757 | +0.000676 ❌ |
| Singh ConvNeXt-T（鲁棒） | 0.020480 | **0.019743** | **−0.000737 ✅** |
| Singh ViT-S（鲁棒） | 0.020141 | **0.019076** | **−0.001065 ✅** |
| **4 目标均值** | 0.018801 | **0.018155** | **−0.000645 ✅ 净降 3.4%** |

ε=8/255 robust acc（↓更强）：

| 目标 | exp3@8/255 | exp9@8/255 | 变化 |
|---|---|---|---|
| Standard_R50 | 0.392 | 0.319 | **−7.3pp ✅** |
| Engstrom2019 | 0.326 | 0.372 | +4.6pp ❌ |
| Singh ConvNeXt-T | 0.554 | 0.511 | **−4.3pp ✅** |
| Singh ViT-S | 0.555 | 0.485 | **−7.0pp ✅** |

4 目标 transfer 仍全部强于各自 gaussian（真实有效攻击）。

### 文字解析（架构对齐机制，3 升 1 降高度自洽）

- **唯一回退是 Engstrom（鲁棒 RN50）**：exp3 单替身 Salman 本身是鲁棒 RN50，与 Engstrom **同架构**，迁移近"准白盒对齐"；集成把 RN50 信号与 XCiT(Transformer) 平均，稀释了同架构红利 → Engstrom 略退（+0.00068）。
- **提升最大的是 ViT-S（−0.00107）**：新增 XCiT 是 **Transformer，与 ViT-S 架构对齐** → 大幅增强；多样化梯度同时带动 ConvNeXt 与非鲁棒 Standard_R50。
- 结论：**集成以"Engstrom 的少量同架构优势"换"其余 3 目标（含最难的 Transformer 与非鲁棒）的普遍提升"，均值净降 3.4%**——正是集成多样性价值，契合"对未知/多架构泛化迁移"的真实评分口径。

- **主要改动点**：单鲁棒替身 → 鲁棒多架构集成替身（概率平均 + MI）；新增 `src/models/ensemble.py`、config `SURROGATE_MODE/ENSEMBLE`、run `--surrogate-ensemble`。
- **潜在可迭代点**：① 加鲁棒 ConvNeXt（异谱系，如 Liu2023 ConvNeXt-B）补现代 CNN 多样性；② 给 RN50 成员升权（0.6/0.4）试图找回 Engstrom；③ 更强优化器 APGD。
- **baseline 判定**：主指标均值 AUC 历史最佳、3/4 目标更强且改善最有价值的两类 → **历史最佳，记为 baseline3（当前最 SOTA）**。

---

## exp10 — baseline3 在官方 1000 提交集上的补充验证（非新 baseline）

- **时间**：2026-06-19 13:12 | **样本**：**1000（均衡 1/类，`indices_1000_seed42.csv`，即提交集）** | **设定**：transfer（4 目标 held-out），batch=32 | **耗时**：591.3s（≈9.9min，约为 exp9 的 1/5.6）
- **替身/方法**：**与 baseline3(exp9) 完全相同**——Ensemble[Salman2020Do_R50 + Debenedetti2022Light_XCiT-S12]，概率平均，loss=CE，MI=1.0，DI=0，TI=0。**唯一差异 = 评估集 4000 dev → 1000 submission**（经新增 `--submission` 走官方均衡 1000）。
- **目的**：本次**不是方法迭代**，而是验证 baseline3 的强度是否为 4000 dev 集的偶然产物，并产出贴合作业"subset of 1000 samples"要求的官方规模结果。

### 与当前最 SOTA baseline（baseline3 = exp9）对比

指标完全同类型（同 transfer / 同替身 / 同 4 目标 / 同 ε / 同 AUC 口径），仅**评估样本集不同**（4000 dev vs 1000 submission）。故用 δ 表并列，但 **δ 应解读为"抽样差异/一致性"，而非攻击强弱的升级**。`pgd_transfer` AUC（↓更强）：

| 目标 | exp9（4000 dev） | exp10（1000 sub） | δ=exp10−exp9 | δ% |
|---|---|---|---|---|
| Standard_R50（非鲁棒） | 0.018044 | 0.018061 | +0.000017 | +0.09% |
| Engstrom2019（鲁棒RN50） | 0.015757 | 0.015984 | +0.000227 | +1.44% |
| Singh ConvNeXt-T（鲁棒） | 0.019743 | 0.020008 | +0.000265 | +1.34% |
| Singh ViT-S（鲁棒） | 0.019076 | 0.019196 | +0.000120 | +0.63% |
| **4 目标均值** | 0.018155 | 0.018312 | +0.000157 | +0.87% |

### "攻击 vs gaussian 基线"间隔（核心硬指标，越大越好）

| 目标 | gauss exp9 | gauss exp10 | **间隔(gauss−pgd) exp9** | **间隔 exp10** |
|---|---|---|---|---|
| Standard_R50 | 0.023687 | 0.023853 | 0.005643 | 0.005792 |
| Engstrom2019 | 0.019377 | 0.019759 | 0.003620 | 0.003775 |
| Singh ConvNeXt-T | 0.022889 | 0.023047 | 0.003146 | 0.003039 |
| Singh ViT-S | 0.022427 | 0.022437 | 0.003351 | 0.003241 |

ε=8/255 robust acc（↓更强）：

| 目标 | exp9@8/255 | exp10@8/255 | 差 |
|---|---|---|---|
| Standard_R50 | 0.319 | 0.320 | +0.1pp |
| Engstrom2019 | 0.372 | 0.382 | +1.0pp |
| Singh ConvNeXt-T | 0.511 | 0.524 | +1.3pp |
| Singh ViT-S | 0.485 | 0.502 | +1.7pp |

### 文字解析

- **结论高度一致**：4 目标 `pgd_transfer` AUC 最大漂移仅 +0.00027（相对 ≤1.4%），符号/排序/量级全部与 exp9 吻合；ε=8/255 处差异 ≤1.7pp。1000 集上鲁棒精度 AUC 略高（攻击看似略弱一丝）是 4× 缩样的抽样噪声，**无方向性变化**。
- **硬指标保持**：4 目标 transfer 全部仍强于各自 gaussian，且"攻击−基线"间隔在两套数据上几乎相等（差异 ≤0.0002）——baseline3 击败基线的结论**不依赖具体评估集**。
- **模式一致**：仍是 Engstrom（与替身成员 Salman 同 RN50 骨干）最易攻、ConvNeXt/ViT（异构鲁棒）最难，印证 exp9 的"架构对齐"解释。
- **意义**：证明 baseline3 的强度非 4000 dev 偶然，并给出贴合作业"1000 samples"要求的官方规模结果。

- **主要改动点**：仅评估集 4000 dev → 1000 submission（新增 `--submission` 标志，走 `indices_1000_seed42.csv`）；攻击方法与替身/目标/超参与 exp9 完全一致。
- **潜在可迭代点**：① 跨数据集泛化验证（CIFAR-10 均衡子集，`--dataset cifar10`）；② 决定提交口径——`outputs/` 保留 4000-dev（低方差）或切换为 1000-submission（对齐要求），或报告中并列两者。
- **baseline 判定**：非方法改进，仅为 baseline3 在不同评估集上的一致性验证 → **不升级 baseline，作为 exp9/baseline3 的补充说明归档**。

---

## exp11 — baseline3 配方的跨数据集泛化验证（CIFAR-10，非新 baseline）

- **时间**：2026-06-19 13:3x | **样本**：**1000（CIFAR-10 均衡测试子集，100/类，`cifar10:balanced_test`）** | **设定**：transfer（4 目标 held-out），batch=256 | **耗时**：194.7s（≈3.2min）
- **替身/方法**：**与 baseline3(exp9) 同款配方**——鲁棒多架构集成 + 概率平均 + loss=CE + MI=1.0、DI=0、TI=0。**唯一差异 = 数据集与模型族换成 CIFAR-10**（经新增 `--dataset cifar10`）。
  - 替身：**Ensemble[Carmon2019Unlabeled（鲁棒 WRN-28-10）+ Andriushchenko2020Understanding（鲁棒 PreActResNet-18）]**
  - 目标（held-out）：Standard（非鲁棒）、Engstrom2019Robustness（鲁棒 RN50）、Wong2020Fast（鲁棒 PreActRN18）、Rice2020Overfitting（鲁棒 WRN-34-20）
- **目的**：验证攻击配方**是否为 ImageNet 专属**，即同一套黑盒迁移方法在完全不同的数据集/模型族上是否仍成立。

### 本次（exp11）数据表（同数据集内 pgd vs gaussian，可直接比）

| 目标 | clean | pgd_transfer AUC（↓更强） | gaussian AUC | δ=pgd−gauss | pgd@8/255 | gauss@8/255 |
|---|---|---|---|---|---|---|
| Standard（非鲁棒） | 0.949 | 0.026486 | 0.029373 | **−0.002887** | 0.673 | 0.916 |
| Engstrom2019（鲁棒RN50） | 0.880 | 0.024796 | 0.027578 | **−0.002782** | 0.672 | 0.880 |
| Wong2020Fast（鲁棒PreActRN18） | 0.847 | **0.023249** | 0.026610 | **−0.003361** | **0.600** | 0.848 |
| Rice2020Overfitting（鲁棒WRN-34-20） | 0.864 | 0.024478 | 0.027131 | **−0.002653** | 0.674 | 0.867 |

**4/4 目标 δ 均为负 → 迁移攻击在每个模型上都强于 gaussian 基线，跨数据集成立。** @8/255 处迁移攻击把鲁棒精度压到比 gaussian 低 19–25pp。

### 与当前最 SOTA baseline（baseline3 = exp9）对比

评估数据类型**不一致**（不同数据集 / 模型 / 标签空间 / 分辨率 / clean 水平 / AUC 绝对量纲），**不强行算 δ**，分别列表做定性对照。

**baseline3（exp9，ImageNet）数据表**

| 目标 | pgd_transfer AUC | gaussian AUC | δ=pgd−gauss |
|---|---|---|---|
| Standard_R50（非鲁棒） | 0.018044 | 0.023687 | −0.005643 |
| Engstrom2019 | 0.015757 | 0.019377 | −0.003620 |
| Singh ConvNeXt-T | 0.019743 | 0.022889 | −0.003146 |
| Singh ViT-S | 0.019076 | 0.022427 | −0.003351 |

（exp11 数据见上方"本次数据表"。）

| 对照维度 | ImageNet baseline3 | CIFAR-10 exp11 |
|---|---|---|
| pgd 全面强于 gaussian | ✅ 4/4 | ✅ 4/4 |
| 攻击−基线间隔（AUC 级） | ~0.0031–0.0056 | ~0.0027–0.0034（同量级） |
| 架构对齐 → 迁移更强 | ✅（RN50、ViT 对齐） | ✅（PreActRN18：Wong 最强） |

### 文字解析

- **泛化结论成立**：同一套"鲁棒集成替身 + PGD + MI + 黑盒迁移"配方迁到 CIFAR-10，4/4 目标仍击败 gaussian，攻击非 ImageNet 专属。
- **gaussian 在 CIFAR 上几乎全平**（@8/255 相对 clean 仅掉 ≤3.3pp，鲁棒三者≈0）→ pgd_transfer 的大幅下降全是真实攻击信号，与噪声干净分离。
- **架构对齐机制跨数据集复现**：攻得最狠的 **Wong2020Fast（PreActRN18）** 与替身成员 **Andriushchenko（PreActRN18）同架构** → AUC 最低、@8/255 掉到 0.600；与 ImageNet 上"同骨干族迁移更强"一致。
- **AUC 跨 CIFAR 模型受 clean 干扰**：非鲁棒 Standard 的 AUC 偏高仅因 clean=0.949 起点高；按**绝对降幅**看它 @8/255 掉 0.276（最大），"非鲁棒最易被实际打穿"的规律保持，故同时给出 @8/255。
- **局限（须写入报告）**：CIFAR 集成为 WRN-28-10 + PreActRN18，**均为 CNN**（RobustBench CIFAR/Linf 基本无鲁棒 Transformer），其"多架构"成色弱于 ImageNet 的 CNN+Transformer，不应表述为真正异构集成。

- **主要改动点**：仅数据集 ImageNet → CIFAR-10（新增 `--dataset cifar10`，配 CIFAR profile：替身/目标模型清单、image_size=32、均衡 100/类子集）；攻击方法/超参与 exp9 一致。
- **潜在可迭代点**：① 若找到鲁棒 CIFAR Transformer，可补真正异构集成；② 把 ImageNet(4000/1000)+CIFAR-10 三套结果在报告中拼成完整跨数据集泛化证据链。
- **baseline 判定**：跨数据集、不同模型族，不参与 baseline 的 AUC 排名 → **不升级 baseline，作为 exp9/baseline3 的跨数据集泛化补充说明归档**。
