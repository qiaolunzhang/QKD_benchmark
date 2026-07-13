# QKD-Bench TODO

> 执行计划,与 `ARCHITECTURE.md`(架构决策)、上级 `PROGRESS.md`(会话日志)配套。
> 架构总纲:Experiment = Scenario + Problem + Algorithm + Evaluation;组合式问题模块只用于验证与指标,不自动生成 MILP。

## Phase 0 — 包骨架与最小闭环(进行中,今日完成)

- [x] `pyproject.toml`(qkdbench,deps: networkx/pyyaml/matplotlib;extra: ilp=pulp, dev=pytest)
- [x] `core/instance.py`(Request/Instance,JSON + fingerprint)
- [x] `core/solution.py`(Assignment/Solution)
- [x] `core/result.py`(Result → CSV 行)
- [x] `core/algorithm.py`(Algorithm ABC + @register_algorithm + registry)
- [x] `core/verifier.py`(独立可行性验证 v0.1:路径/波长/模块/deadline/密钥量)
- [x] `keyrate/finite_size.py`(FSE 1540-alone + 1310-coex 双表,RateTable)
- [x] `topology/builtin.py`(triangle/poliqi5/german7)
- [x] `instances/generators.py`(seeded uniform_requests + make_instance)
- [x] `algorithms/greedy_sp.py`(EDF+最短路 first-fit 基线)
- [x] `runner/benchmark.py`(evaluate + run_benchmark,CSV 增量追加)
- [x] `runner/config.py`(YAML ExperimentConfig)+ `cli.py`
- [x] 各包 `__init__.py`(公共 API 出口)
- [x] `configs/demo.yaml` + `examples/quickstart.py` + `examples/add_your_algorithm.py`
- [x] `tests/`(instance 序列化/fingerprint、verifier 抓违规、greedy_sp 冒烟、CLI 冒烟)
- [x] `README.md`(60 秒 quickstart)+ `.gitignore`
- [x] 跑通:`pip install -e . && pytest && qkdbench run -c configs/demo.yaml`
- [ ] git 提交 + push(开源先行,PFLlib 的 Impacts 教训)

## Phase 1 — core 重构(§3 数据模型)

- [x] `core/network.py`:Node/Link/Network(topology_id/version/checksum 必带;checksum 留空时构造即自动计算)
- [x] `core/demand.py`:Demand(静态字段 + 动态到达字段;`Request = Demand` 向后兼容别名)
- [x] Instance 改为引用 Network + demands + qkd_model(rate_table 名沿用;兼容 property:nodes/edges/requests/wavelengths/modules,算法零改动)
- [x] 统一 `core/registry.py`(多 kind Registry)+ `core/errors.py`(algorithm 注册已迁移到通用 registry,13 测试回归通过)
- [x] 回归:Phase 0 demo 迁移后结果不变(quickstart served 9/20、delivered 1050 kb 前后一致;fingerprint 值因 schema 变化更新,同参数生成仍确定;17 测试全绿,含新增 tests/test_network.py)

## Phase 2 — 拓扑一等模块(完成)

- [x] `scenario/topology/base.py`:TopologyProvider(capabilities, build(config, seed))+ `build_topology` 入口 + haversine 工具
- [x] 内置 6 拓扑 YAML 数据文件:nsfnet14 / usnet24 / cost239_11 / geant2 / german7 / germany50(source 引用 + version + checksum;另附 triangle/poliqi5;german7 与 usnet24 用 length_policy 按 seed 生成长度,与 Phase-0 / INFOCOM27 逐位一致,tests 锁定)
- [x] `synthetic.py`:waxman / grid / ring / random_geometric / barabasi_albert(随机型必收 seed,否则 ValueError;长度=坐标欧氏距离或 edge_km)
- [x] `loaders.py`:FileTopology("file"):GraphML / JSON / YAML / CSV(节点表+链路表)
- [x] `logical_graph(network, rate_table)` 推导函数(物理→逻辑 QKD 拓扑;超出 RateTable reach 的链路滤除;Phase 3 换成 KeyGenerationModel)
- [x] DynamicTopology 接口占位(snapshot/events,NotImplementedError,v1.5 启用)
- [x] 集成测试:换拓扑只改 YAML 一块,problem/algorithm 零改动(tests/test_topology.py,17 新测试;make_instance 增加 length_scale 参数 = INFOCOM27 fiber_factor 手法,让 nsfnet 等国家级长度进入 QKD reach 窗口)
- [x] 回归:34 测试全绿;quickstart 9/20、1050 kb 不变;demo.csv 9 实例指标与 Phase 0/1 完全一致

## Phase 3 — QKD 物理模型层(完成)

- [x] `scenario/qkd_models/base.py`:KeyGenerationModel(name/version/evaluate→KeyGenResult;便捷 tp_keys_kb/feasible/max_reach_km)
- [x] constant.py / distance.py(指数损耗)/ finite_size.py(包装 keyrate/ 双表,单一数据源)/ decoy_bb84.py(简化渐近闭式)
- [x] memoize(base 按 (name, version, params, round(L,3), tau) LRU;预计算表物化到 `datasets/` 移至 Phase 7);model name+version 写入 Result.extras;Instance 增加 qkd_model_params
- [x] 接线:verifier/greedy_sp/runner/logical_graph 改走 get_qkd_model(fse_* 旧名兼容映射);回归逐位一致(47 测试全绿;quickstart 9/20、1050 kb;demo 9/9 指标不变)
- [x] 测试:同一实例换模型,算法零改动(tests/test_qkd_models.py,13 新测试);禁止算法 import 物理公式写入 docs/CONTRIBUTING.md(lint 自动化留待 CI)

## Phase 4a — P1 算法组(完成)

- [x] `algorithms/_common.py`:ResourceLedger + candidate_paths + min_slots_for + greedy_construct + extend_for_surplus(共享构造,避免重复资源记账)
- [x] `algorithms/key_aware_sp.py`(EDF + 密钥效率路径排序,server≥greedy)
- [x] `algorithms/fse_greedy.py`(EDF 最小 TP 保 served + TP 延长增 surplus,源自 DA-FSE)
- [x] `algorithms/local_search.py`(多起点 + LNS,seed 确定;server≥fse_greedy)
- [x] `algorithms/exact/milp_p1.py`(PuLP+CBC 紧凑集合打包 ILP;solver_status 记录;pulp 缺失给 extra 提示)
- [x] sanity 测试:全部启发式 served ≤ milp_p1;german7 3seed 均值 greedy/key_aware/fse=7.33 ≤ LS=8.0 ≤ MILP=8.33
- [x] `tests/test_algorithms_p1.py`(9 测试)+ `configs/compare_p1.yaml`;56 测试全绿;quickstart 9/20 1050kb 回归不变;pulp 弃用告警已过滤

## Phase 4b — P1 组合式问题定义(完成)

- [x] `problems/base.py`:DecisionModule/ConstraintModule/ObjectiveModule + Problem(compose 时做依赖闭包 + 冲突标签校验)+ get_problem/list_problems
- [x] `problems/constraints.py`:verifier 拆成 6 个约束模块(serve_once/route_validity/tp_window/wavelength_capacity/module_capacity/key_sufficiency),消息逐字保留
- [x] `problems/decisions.py`(path_selection/wavelength_assignment/tp_scheduling)+ `objectives.py`(max_accepted_demands/max_surplus_keys)+ `presets.py`(static_routing_rra)
- [x] `core/verifier.verify` 改为委托 preset;原逻辑冻结为 `_reference_verify`
- [x] **差分等价测试**:composed verify 与冻结版在 120 个随机 valid/corrupted 解上逐字一致(tests/test_problem_equiv.py,3 测试);59 测试全绿;quickstart 9/20 1050kb 回归不变
- [ ] 完整移植 INFOCOM27 DA-FSE(多路径流+QKP)作为 P1 扩展(当前 fse_greedy 是单 TP 投影)→ 挪到 Backlog

## Phase 5 — 动态问题 P2(admission + key pool)(完成)

- [x] `core/key_pool.py`:KeyPool(per-link,gen_kbps/capacity/init);Demand 加 rate_kbps;Instance 加 key_pools/horizon_s(JSON 序列化)
- [x] `scenario/simulator.py`:离散事件引擎(到达/离开)+ SimState(committed rate)+ `simulate`(驱动 controller)+ `replay_violations`(独立回放校验,verifier 与算法共用同一模型)
- [x] `algorithms/online.py`:OnlineAlgorithm 接口(reset/act/finalize;solve 驱动 simulate 合成 Solution)+ `greedy_admission` 基线
- [x] `instances/generators.py`:`make_dynamic_instance`(Poisson 到达 + 指数 holding + 每链路 KeyPool,gen=QKD 模型速率)
- [x] `problems/dynamic.py`:P2 决策/约束(keypool_capacity 回放)/目标(acceptance_ratio/blocking/served_rate)+ preset `dynamic_admission_keypool`;runner evaluate 按 horizon_s 分流
- [x] tests/test_dynamic_p2.py(6 测试:形状/JSON/确定性/负载↑acceptance↓/**对抗越界被 verifier 抓**/目标一致);65 测试全绿;P1 回归 9/20 1050kb 不变
- [x] examples/dynamic_admission.py(负载 2/6/10 → acceptance 56%/38%/34% 单调下降)
- 注:故障事件(link/node failure)接口预留,v1 未实现(→ Backlog / Phase 6+)

## Phase 6 — P3 trusted-relay placement(完成)

- [x] `problems/placement.py`:relay_placement 决策 + placement_validity/demand_coverage 约束 + deployment_cost/num_relays 目标 + preset `trusted_relay_placement`;covered_demands 供 verifier 与算法共用
- [x] `algorithms/placement.py`:greedy_placement(反向贪心,总产出可行覆盖)+ milp_placement(节点激活多商品流 MILP,PuLP+CBC)
- [x] `instances/generators.py`:`make_placement_instance`(user_frac 用户节点 + 需经 relay 的多跳需求 + 安装成本)
- [x] `Solution.placement` 组件;runner `_evaluate_problem` 泛化(P2/P3 共用),按 metadata.problem_family 分流
- [x] tests/test_placement_p3.py(6 测试);usnet24 上 greedy 3 relays / MILP 最优 2;MILP cost ≤ greedy;越界节点被 verifier 抓;71 测试全绿
- [x] examples/relay_placement.py;三问题共用同一 runner/评测,无问题特判(evaluate 仅按 instance 特征分流)

## Phase 7 — 实验管理与论文实验(核心完成)

- [x] `runner/provenance.py`:meta.json(config_hash/instance fingerprints/code commit/python+依赖版本/OS);CLI run 自动写在 CSV 旁
- [x] `evaluation/aggregate.py`:多 seed mean±std + Student-t 95% CI(内置 t 表,无 scipy 依赖);aggregate_by 出算法曲线
- [x] `evaluation/plots.py`:plot_metric 统一画图(metric vs 扫描变量,带 CI 误差棒,存 PDF/PNG)
- [x] `validation/capability.py`:capability 检查(静态算法 vs 动态问题不兼容会报错)
- [x] `configs/paper_v1/p1_german7.yaml`:冻结论文实验(5 算法 × 5 负载 × 5 seed)
- [x] tests/test_evaluation.py(4 测试);75 测试全绿;run→meta→aggregate→plot 端到端验证
- [ ] 文档站(Sphinx/mkdocs)+ GitHub Actions CI → Backlog
- [ ] 跑 paper_v1 全量 + 生成论文图替换 .tex 占位 → 待办(需较长算力)

## 论文(overleaf_QKD_benchmark/,与代码并行)

- [x] JMLR/PFLlib 范式调研
- [x] 论文骨架完成:新建 `QKD_benchmark.tex`(TON-PSR.tex 保留未动),7 节 + P1 数学模型 + 12 条新参考文献,编译通过出 7 页 PDF;文内 12 处 % TODO 待作者定夺
- [ ] 算法分类学 Table 1(问题维度 × 方法类型)
- [ ] Related Work 两分法:量子网络模拟器(NetSquid/SeQUeNCe/SimQN)vs 单篇论文附带代码;单挑最近竞品
- [ ] 实验章:框架跑出的初版结果(P1 三拓扑 × 4 算法 × 5 seeds,带 CI)

## Backlog

- 卫星/混合拓扑、多域、攻击模型、DRL 管道、Pareto、PyPI 发布、leaderboard(见 ARCHITECTURE §13)
