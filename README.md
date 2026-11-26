# FunFair
FunFair for SCHUNK Intec China Christmas Event


## V20：自动往复与暂停判分

导入厂家原生 FB、[游戏块](plc/v20/FB_StopGameV20.scl)、[集成入口](plc/v20/FB_FunFairEGU_V20.scl)。OB1 每扫描调用一次集成入口，使用非保持实例。FirstScan 接首扫位，MotionPermit 接运行许可，DataValid 接实际周期数据有效状态，InputHW、OutputHW 接对应的输入、输出子模块。入口内部调用 SCHUNK 原生块一次。

操作员输入 OpenPosition_um、ClosePosition_um、Velocity_um_s、TargetPosition_um 和 Tolerance_um。位置单位为 µm，速度为 µm/s。张开和夹紧使用绝对定位，两个位置可以任意排序，必须不同，速度和窗口半宽须为正。每一程发命令时读取位置和速度。应用层不校验设备行程和速度上下限，输入值须适用于现场夹爪。

设备就绪且获得总线控制权、运行许可、有效反馈后自动往复。PauseDI 自锁为高时请求普通 STOP，收到本次停止确认后，以位置在 20 µm 偏差内稳定 200 ms 且命令完成作为判分条件。实际位置减去本次暂停时的目标即为有符号偏差，绝对值严格小于窗口半宽时成功。解锁后继续向中断的端点运动。上电已锁住时等待解锁，不判分。ResetButton 接滤波后的点动输入，仅用于确认夹爪错误。故障排除后锁住暂停再解锁，恢复往复。快速停止位在周期命令中固定为 TRUE。

| 输出 | 含义 |
|---|---|
| ActualPosition_um、SignedError_um | 当前反馈位置和有符号偏差。运行时使用当前目标，暂停判分期间使用锁入瞬间的目标。 |
| ResultValid、Success | 停稳后结果有效，Success 表示本次是否成功。解锁恢复或故障后清除。 |
| State | 0 等反馈；10 等解锁；30 命令间隔；40 等定位确认；50 运动；55 等前一定位确认；60 等停止确认；70 等停稳；80 显示成绩；900 故障。 |
| FaultCode | 游戏诊断（十六进制）：0000 正常，0001 反馈或设备状态异常，0002 输入参数无效，0003 定位确认超时，0004 运动中连续 15 s 无位置变化且未到位，0005 停止超时，0008 未知状态，0009 运行许可撤销。 |
| GripperFaultCode | 原生块 i_DIAGNOSIS_ERROR 原值，与程序诊断分开输出。反馈无效时不能据此判断设备健康。 |

运行 `python -m unittest discover -s tests -v`。V20 单元测试执行入口及游戏块的 SCL 逻辑，在原生块接口注入反馈并检查发出的命令。需要在 TIA 和实机验证编译、PROFINET 时序及停止响应。


## 历史版本 · 精准停位小游戏（程序草稿 v0.2）

目标组合：TIA Portal V18、S7-1200 CPU 1211C DC/DC/DC、SCHUNK EGU 60-PN-M-B。

进入已准备好的游戏模式后自动往复；按钮完整按下再松开，用 `R_TRIG` 的松开上升沿交替触发停止判分与下一回合。按住期间不切换。

- [SCL 游戏功能块](plc/FB_FunFair_StopGame.scl)
- [接口映射、触发逻辑、恢复流程与验证清单](docs/PLC-V18.md)
- [扫描逻辑回归检查](tests/test_scan_logic.py)

**尚未通过 TIA V18 编译、PLCSIM 或实机验证。** 本仓库交付游戏控制层；设备初始化、故障恢复、PN 有效性及现场安全功能仍需在实际工程中集成。回归检查不替代 Siemens 工具链或现场验证。
