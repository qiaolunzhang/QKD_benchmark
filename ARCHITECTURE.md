# QKD-Bench 架构设计文档

> 状态:v0.2 设计定稿(2026-07-12)。本文档是唯一的架构决策来源;TODO.md 记录执行计划;上级 PROGRESS.md 记录会话日志。
> 输入:INFOCOM27(RCKTA-FSE)与 JSAC(LC-FCRP)项目调研、PFLlib(JMLR MLOSS)写作范式、用户提供的 25 节完整架构规格。
> 本文档对该规格做了**取舍**:每一处偏离都标注了理由(见 §12 反模式与 §13 明确推迟项)。

---

## 1. 核心抽象

一次完整实验:

```
Experiment = Scenario + Problem + Algorithm + Evaluation
```

- **Scenario**(客观世界):拓扑 + QKD 物理模型 + 设备画像 + 业务 + 环境/故障/攻击 + 时间模型 → 物化为 `Instance`(JSON,带 fingerprint)
- **Problem**(优化任务):决策模块 + 约束模块 + 目标模块 + 问题参数 → 决定 Solution schema、verifier 组合与指标集
- **Algorithm**(求解方法):离线/在线插件,输入 Instance,输出统一 `Solution`
- **Evaluation**(评判,只属于框架):独立 verifier 重查可行性、重算目标值、统一计算指标 → `Result`

十条铁律(全部采纳自规格 §一):拓扑/物理模型/问题/算法互相解耦;同一问题跑不同拓扑;同一拓扑配不同 QKD 模型;同一实例可被 MILP/启发式/RL 求解;Solution 统一;指标由框架算;问题组合式而非继承树;新增组件不改核心;配置驱动+可复现;v1 聚焦地面光纤 QKD 网络。

## 2. 分层架构与数据流

```
┌─────────────────────────────────────────────────────────┐
│ cli / examples                                          │
├─────────────────────────────────────────────────────────┤
│ runner(实验编排:config→验证→循环→聚合→落盘)          │
├───────────────┬──────────────────┬──────────────────────┤
│ scenario      │ problems         │ algorithms           │
│  topology     │  decisions/      │  baselines/          │
│  qkd_models   │  constraints/    │  heuristics/         │
│  traffic      │  objectives/     │  exact/ (optional)   │
│  events(v1.5) │  catalog.py      │  learning/ (v2)      │
├───────────────┴──────────────────┴──────────────────────┤
│ evaluation(verifier + metrics + aggregate + plots)     │
├─────────────────────────────────────────────────────────┤
│ core(Network/Node/Link/Demand/KeyPool/Instance/        │
│       Solution/Result/registry/errors)                  │
└─────────────────────────────────────────────────────────┘
```

运行前验证流水线(采纳规格 §十二):

```
加载 YAML → schema 校验 → 构建拓扑 → 应用设备画像 → QKD 可行性评估
→ 生成场景实例(物化+fingerprint) → 组装问题 → 模块依赖检查
→ 算法 capability 检查 → 执行 → 独立验证 → 指标 → 落盘
```

任何一步失败都给出可读错误,例如:
`Algorithm 'greedy_sp' does not support dynamic arrivals (problem declares decision 'admission_control' with time_model 'poisson').`

## 3. 核心数据模型(core/)

用 **dataclass,不用 Pydantic**。理由:少一个重依赖、入门者零学习成本;校验集中在 `validation/` 的显式函数里,报错信息反而更可控。若 v2 出现深层嵌套配置再评估切换。

| 对象 | 核心必需字段 | 说明 |
|---|---|---|
| `Node` | id, type(user/qkd/relay/optical/satellite/ground_station), trusted, coords?, device_slots | |
| `Link` | id, (a,b), type(fiber/fso), length_km, wavelengths, attenuation_db_km? | |
| `Network` | topology_id, topology_version, checksum, directed, nodes, links | 拓扑三元信息**必带**,同名拓扑不同长度版本靠 version+checksum 区分,绝不静默混用 |
| `Demand` | id, src, dst, volume_kb 或 rate_kbps, deadline/holding, priority?, arrival_t?(动态) | |
| `KeyPool` | id, endpoint(链路或节点对), capacity, init_inventory, min_reserve | v1.5 启用 |
| `Instance` | scenario 物化结果:network + demands + qkd_model 名与版本 + 时间模型参数 + metadata(generator, seed) | JSON 序列化 + SHA1 fingerprint |
| `Solution` | status + typed 可选组件:RoutingResult / PlacementResult / KeyPoolTrajectory / RecoveryLog + timing(solve/train/infer) + solver_meta(gap/status/seed) | 不适用组件=None,不放空 dict |
| `Result` | 全部由框架填写:feasible、objective(重算)、各指标、runtime、violations | 算法永远不自报成绩 |

**避免无类型大字典**:每个 dataclass 只留一个 `metadata: dict` 逃生舱,约定只放"注释性"信息,任何被算法/verifier 读取的字段必须提升为 typed 字段。

## 4. 拓扑:一等模块(scenario/topology/)

```python
class TopologyProvider(ABC):
    capabilities: set[str]   # {"geo_coords", "directed", ...}
    def build(self, config, seed=None) -> Network: ...
```

三类 provider,全部注册进 registry:

1. **BuiltinTopology**:数据文件(YAML)+ loader,**不硬编码在 .py 里**。v1 内置 6 个(选择理由:光网络优化文献使用率 + 已有 QKD 论文先例):
   - **NSFNET-14**(美,最经典 benchmark 拓扑)
   - **USNET-24**(美,RCKTA 系列已用)
   - **COST239-11**(欧,密集网状)
   - **GEANT2-30 精简版**(欧,大规模代表)
   - **German-7**(QKD 文献常用小拓扑,ILP 可解,来自 JSAC/INFOCOM 系列)
   - **Germany-50**(SNDlib,INFOCOM27 主力大拓扑,坐标齐全)
   每个 YAML 带:id、version、节点(含坐标)、链路长度、directed、**source 文献引用**、checksum。
2. **SyntheticTopology**:waxman / grid / ring / random_geometric / barabasi_albert,必须收 seed。
3. **FileTopology**:GraphML / JSON / YAML / CSV 表;loader 可注册扩展。

**拓扑层次**(采纳规格 §五,v1 落地两层):
- Physical topology = `Network`(唯一的存储形态)
- Logical QKD topology = **推导量**:`qkd_model.feasible(link)` 过滤后的子图,由框架函数 `logical_graph(network, qkd_model)` 现算,不单独存储 → 从根上避免"物理/逻辑/服务拓扑混用"
- Service topology(trusted-relay 路径、bypass 路径)= Solution 的一部分,不是输入
- `DynamicTopology(snapshot(t), events(t0,t1))` 接口**预留定义但 v1 不实现**(v1.5 随动态问题启用)

## 5. QKD 物理模型(scenario/qkd_models/)

```python
class KeyGenerationModel(ABC):
    name: str; version: str
    def evaluate(self, link, device_profile=None, time=None,
                 environment=None) -> KeyGenResult: ...
    # KeyGenResult: feasible, skr_kbps, qber?, loss_db?, reason?
```

v1 实现四个:
- `ConstantRate`(调试/对照用)
- `DistanceExponential`(skr = R0·10^(−αL/10),最简物理模型)
- `FiniteSizeTable`(**我们的差异化特色**:Yin2020 有限尺度表,rate 依赖 (距离, TP 时长),1540-alone 与 1310-coex 两个 regime;已实现)
- `SimplifiedDecoyBB84`(闭式渐近公式,参数可调)

工程约定:模型带 name+version 写进 Instance 与 Result;查表/闭式计算按 (version, 量化后的参数) memoize;昂贵模型离线预计算成表物化到 `datasets/`,运行时只查表——同时解决速度、跨算法一致性与浮点复现三个问题。**算法内部禁止出现任何密钥率公式**(verifier 同款规则)。

## 6. 组合式问题定义(problems/)——本设计最关键的取舍

采纳"Problem = Decisions + Constraints + Objectives",**但明确其用途边界**:

> 组合式模块负责三件事:(1) 声明 Solution 需要哪些组件;(2) 组装 verifier(每个 constraint 模块 = 一个针对 Solution 的检查函数);(3) 选择指标集与目标重算函数。
> **不做**第四件事:自动把模块组合编译成 MILP/RL 环境。MILP 模型仍由算法作者手写(可用框架提供的公共构件),但其解必须通过组合式 verifier。
> 理由:约束的"检查"是简单纯函数,容易做对做全;约束的"生成"需要通用代数建模层,是同类框架失控的头号原因(规格 §二十四"过度设计第一版"的最大风险点)。RL 环境同理:v2 按问题手写 Gym wrapper,复用 Scenario/verifier。

```python
@register("decision", "path_selection")
class PathSelection(DecisionModule):
    solution_component = "routing"        # 要求 Solution.routing 非空
    requires = {"demand.volume_kb"}       # 对实例字段的依赖声明

@register("constraint", "wavelength_capacity")
class WavelengthCapacity(ConstraintModule):
    requires = {"link.wavelengths", "solution.routing"}
    def check(self, instance, solution) -> list[Violation]: ...

@register("objective", "max_accepted_demands")
class MaxAccepted(ObjectiveModule):
    def value(self, instance, solution) -> float: ...   # 框架重算
```

组合与校验:`Problem.compose(decisions, constraints, objectives, params)` 时做——依赖闭包检查(模块 requires 的字段在实例/解中必须存在)、冲突检查(互斥标签,如 `single_path` vs `multipath`)、目标支持 weighted(v1)/ lexicographic(v1.5)/ Pareto(v2,只记录各目标值不做支配排序)。

**问题类别 × 场景属性正交表示**(采纳规格 §十):问题实例用两组标签描述(decision: routing/admission/placement/...;scenario: static/dynamic, offline/online, terrestrial/satellite, TR/OB, ...),不造 `DynamicOnlineTerrestrialTrustedRelay...Problem` 类。标签同时是 capability 匹配的词汇表。

v1 内置三个问题预设(preset = 模块组合的命名快捷方式):
- **P1 静态 routing + resource allocation**(含现有 v0.1 FSE 特例:decisions={path_selection, wavelength_assignment, tp_scheduling}, constraints={wavelength_capacity, module_capacity, deadline, key_sufficiency}, objective=max_accepted + max_surplus_keys)
- **P2 动态 admission + key-pool management**(v1.5,启用事件引擎与 OnlineAlgorithm)
- **P3 trusted-relay placement**(部署成本目标 + 覆盖约束)

## 7. 算法插件(algorithms/)

```python
class Algorithm(ABC):                    # 离线(已实现)
    name: str
    capabilities: set[str] = {"static", "offline"}
    def solve(self, instance) -> Solution: ...

class OnlineAlgorithm(Algorithm):        # v1.5,动态问题
    def reset(self, instance): ...
    def act(self, event, state) -> Decision: ...
    def finalize(self) -> Solution: ...
```

- 离线/在线共享 `Algorithm` 父接口(runner 只认 `solve`;OnlineAlgorithm 的 `solve` 由框架的事件循环驱动 act 后合成)——保证 Result 管道唯一。
- Solver 封装:`algorithms/exact/` 内做 PuLP 薄封装,统一记录 solver_status(optimal/limit/infeasible/unbounded)、gap、time_limit;Gurobi/CPLEX 走 PuLP 后端切换,**AMPL 不引入**。
- "实例不可行"与"算法没找到解"区分:MILP 证明不可行 → `Solution.status="proven_infeasible"`;启发式空解 → `"no_solution_found"`;Result 分开统计。
- 随机性一律从 `params["seed"]` 派生;训练/推理时间分字段记录(为 v2 学习型算法预留)。
- v1 算法:`greedy_sp`(已有)→ `key_aware_sp`(密钥感知代价)→ `greedy_admission`(P2)→ `milp_p1`(PuLP)→ `milp_placement`(P3);随后移植 INFOCOM27 的 DA-FSE 与 LS。

## 8. Capability 检查(validation/)

轻量实现:capability = 字符串集合,requirement = 字符串集合 + 字段依赖;`validate_experiment(scenario, problem, algorithm)` 在 runner 前置执行,输出全部不匹配项(不是遇错即停),错误信息模板:
`Problem module 'key_pool_balance' requires initialized key pools, but scenario has none (add scenario.key_pools).`

## 9. 参数三隔离与 YAML

YAML 顶层五块,scenario/problem/algorithm 参数**物理隔离**(采纳规格 §十六):

```yaml
experiment: {name: demo, seeds: [1,2,3], repetitions: 1}
scenario:
  topology: {name: nsfnet, version: "1.0"}      # 只改这一块即可换拓扑
  qkd_model: {name: finite_size_table, table: fse_1540_alone}
  traffic: {generator: uniform_pairs, n_requests: 30, mean_volume_kb: 100}
  time: {num_slots: 5, slot_seconds: 1.0}
problem:
  preset: static_routing_rra          # 或显式列 decisions/constraints/objectives
  parameters: {k_candidate_paths: 5}
algorithm:
  - {name: greedy_sp, parameters: {k_paths: 3}}
  - {name: milp_p1, parameters: {time_limit_s: 600}}
evaluation:
  metrics: [acceptance_ratio, served_key_rate, runtime]
  aggregate: {ci: 0.95}
output: {directory: results/demo, save_instance: true, save_solution: true}
```

换 COST239 / GraphML 文件 / Waxman:只改 `scenario.topology` 一行/一块,problem 与 algorithm 不动——这是集成测试的验收用例。

## 10. 评价指标与复现管理

- 指标 = 注册的 `MetricPlugin`(纯函数 instance×solution→值);按问题预设选默认集;单位入指标名(`*_kb`, `*_kbps`, `*_s`);时间平均 vs 请求平均在 docstring 与论文附录统一定义。
- 聚合:多 seed → mean ± std + t 分布 95% CI(补 PFLlib 短板,JSAC 拒稿教训);聚合脚本是框架代码,不是每人手搓。
- 每次 run 落盘 `results/<exp>/`:`config.yaml` 副本、`meta.json`(config hash、instance fingerprints、code commit、qkd model version、Python/依赖版本、OS、时间)、`results.csv`(增量追加,可断点续跑)、可选 `solutions/*.json`。
- 存储选型:配置=YAML,元数据/Solution=JSON,指标=CSV(v1);Parquet/SQLite 到数据量倒逼时再上,不预先引入。

## 11. 目录结构(v0.2 目标形态;→ 标注从现状的迁移)

```
qkdbench/
├─ core/            # network.py, demand.py, key_pool.py, instance.py,
│                   # solution.py, result.py, registry.py, errors.py
│                   #   → instance/solution/result 已有,拆出 network/demand
├─ scenario/
│  ├─ topology/     # base.py, builtin/(nsfnet.yaml, cost239.yaml, usnet24.yaml,
│  │                #   geant2.yaml, german7.yaml, germany50.yaml), synthetic.py,
│  │                #   loaders.py        → 现 topology/ 移入并数据文件化
│  ├─ qkd_models/   # base.py, constant.py, distance.py, finite_size.py,
│  │                #   decoy_bb84.py     → 现 keyrate/ 移入
│  └─ traffic.py    #                     → 现 instances/generators.py 移入
├─ problems/        # base.py, decisions.py, constraints.py, objectives.py,
│                   #   presets.py        → 现 core/verifier.py 拆成约束模块
├─ algorithms/      # baselines/, heuristics/, exact/, learning/(v2 占位)
├─ evaluation/      # verify.py, metrics.py, aggregate.py, plots.py
├─ validation/      # schema.py, capability.py
├─ runner/          # benchmark.py, config.py   (已有,升级 YAML schema)
└─ cli.py
configs/  datasets/  examples/  tests/  docs/
```

统一 registry(`core/registry.py`):一个 `Registry` 类按 kind 分命名空间(topology/qkd_model/traffic/decision/constraint/objective/algorithm/metric/exporter),decorator 注册。**方案对比结论**:decorator registry(选定:简单、可调试、import 即注册)> explicit registry(样板多)> entry points(跨包发布才需要,v2 面向第三方 pip 插件时加)> 动态 import/DI(调试地狱)。

## 12. 反模式清单(执行红线)

规格 §二十四全盘采纳,特别强调(结合两个旧项目的教训):
- ❌ 每种问题组合一个类 / 深继承树 → 组合式 + 标签
- ❌ 密钥率公式写进算法(JSAC 旧代码病灶)→ 只准调 KeyGenerationModel
- ❌ 拓扑硬编码在 .py(两个旧项目均有)→ YAML 数据文件 + version + checksum
- ❌ 算法自算指标 / 直接相信算法报告的 objective → verifier + 框架重算
- ❌ 各算法各自生成实例(不同实例/不同物理参数)→ 物化 + fingerprint 断言
- ❌ 巨型入口脚本 ×20(JSAC)/ 环境变量配置(INFOCOM27)→ 单 CLI + YAML
- ❌ 不记 seed / topology version / dataset version → meta.json 强制字段
- ❌ 为支持所有 20 类问题过度设计 v1 → 见 §13

## 13. 明确推迟项(接口预留,v1 不写实现)

卫星轨道与可见窗口、多域编排、光物理层详细仿真、量子/经典共存的在线计算(先用 coex 表)、复杂攻击模型、分布式执行、完整 DRL 训练管道、Pareto 前沿分析、Parquet/SQLite、entry-points 插件发布。每项在对应 base 类留 capability 词汇与 TODO 注释。

## 14. MVP 路线图(替代旧 TODO 里的 Milestone 2-4 细节)

| Phase | 内容 | 验收标准 |
|---|---|---|
| 0(已基本完成) | 包骨架、core v0.1、FSE 表、3 小拓扑、greedy_sp、runner、CLI | `pip install -e . && pytest` 绿;demo config 出 CSV |
| 1 | core 重构成 §3 数据模型;统一 Registry;errors.py | 旧 demo 迁移后结果不变(fingerprint 级回归) |
| 2 | 内置 6 拓扑 YAML 化(+ 校验、checksum、可视化脚本);synthetic;file loaders | 换拓扑=改一行 YAML 的集成测试通过 |
| 3 | qkd_models 四模型 + 预计算/缓存机制 | 同一实例换模型,算法代码零改动 |
| 4 | P1 组合式化(decisions/constraints/objectives 模块 + preset);milp_p1(PuLP);key_aware_sp;DA-FSE 移植 | sanity:启发式 ≤ MILP;DA-FSE 与原实现对拍一致 |
| 5 | 事件引擎 + OnlineAlgorithm + P2(admission + key pool)+ greedy_admission | 动态 demo 全链路 + key-pool 轨迹指标 |
| 6 | P3 placement + milp_placement + 部署成本指标 | 三问题共用同一套 runner/评测,无特判代码 |
| 7 | 实验管理完备:meta.json、多 seed CI 聚合、plots、复现文档 | 一条命令复现 README 中的全部图 |

每 Phase 交付:实现 + 单测 + 一个 examples/ 脚本 + TODO.md 勾选。

## 15. 后期失控风险点(自我警示)

1. 通用 MILP 自动组装(已明确不做,见 §6)
2. 约束模块粒度过细导致"配置比代码难懂"→ preset 优先,显式组合是高级用法
3. 动态问题的事件引擎演变成完整 DES 模拟器 → 只做请求到达/离开/故障三类事件,复杂动力学交给 SimQN 等外部模拟器(定位区隔:我们是 benchmark,不是 simulator)
4. 内置拓扑数据版本混乱 → 单一来源 SNDlib/文献,version+checksum,加载时校验
5. 论文实验与框架演示混在一个仓库 → configs/paper_v1/ 独立目录冻结
```
