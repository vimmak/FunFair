# FunFair
FunFair for SCHUNK Intec China Christmas Event


## 电脑投屏

[第一版安装、TIA 接线与现场验收](docs/Display-V1.md) · [V2 移动目标和全屏投放](docs/Display-V2.md) · [网页和本地通信服务](display)

## V20：自动往复与暂停判分

导入厂家原生 FB、[游戏块](plc/v20/FB_StopGameV20.scl)、[集成入口](plc/v20/FB_FunFairEGU_V20.scl)。OB1 每扫描调用一次集成入口，使用非保持实例。FirstScan 接首扫位，MotionPermit 接运行许可，DataValid 接实际周期数据有效状态，InputHW、OutputHW 接对应的输入、输出子模块。入口内部调用 SCHUNK 原生块一次。

操作员输入 OpenPosition_um、ClosePosition_um、Velocity_um_s、TargetPosition_um 和 Tolerance_um。位置单位为 µm，速度为 µm/s。张开和夹紧使用绝对定位，两个位置可以任意排序，必须不同，速度和窗口半宽须为正。每一程发命令时读取位置和速度。应用层不校验设备行程和速度上下限，输入值须适用于现场夹爪。

PauseDI 和 ResetButton 均接经过输入滤波的 **PNP 点动按钮**，以 DI 从 OFF 变为 ON 的上升沿触发。在 OB1 将实体 `ResetDI` 接到 `ResetButton`。更新入口实例 DB 后，将 `LampDO0`、`LampDO1`、`LampDO2` 分别接到实际输出点（例如 `%Q0.0`、`%Q0.1`、`%Q0.2`），并确认其他网络未写这些输出。V2 目标块的 OB1 接线见 [V2 移动目标](docs/Display-V2.md#2-更新-tia-portal-工程)。

1. 上电或 CPU 重新进入 RUN 后，等待有效反馈，再按一下 Reset。夹爪已就绪时开始往复。有设备故障时，通过 SCHUNK 原生块的 `b_02_ACKNOLEDGE` 确认，待报错消失、设备就绪且取得总线控制权后开始。运行许可或数据有效性丢失后，恢复条件并重新按 Reset。
2. 往复时按一下 Pause 请求普通 STOP，同一扫描锁定目标与窗口。松开按钮后仍保持暂停。收到本次 STOP 确认后，命令完成且位置在 20 µm 偏差内稳定 200 ms 才判分。成功条件是绝对偏差严格小于窗口半宽。
3. 停稳并出成绩后按一下 Reset，清除当前成绩并继续向暂停前的端点运动。停稳前的 Reset 不排队，两键同时按下时 Pause 优先。正常暂停后的 Reset 不发送设备 ACK。原生快速停止位固定 TRUE。

| 输出 | 含义 |
|---|---|
| LampDO0、LampDO1、LampDO2 | 往复时按 DO0 → DO1 → DO2 单灯轮转，每步约 250 ms。停稳暂停时仅 DO0 闪烁，约 2 Hz（亮、灭各 250 ms，加扫描误差）。待启动、待停稳、故障及故障确认期间全灭。 |
| ActualPosition_um、SignedError_um | 当前反馈位置和有符号偏差。运行时使用当前目标，暂停判分期间使用按下瞬间的目标。 |
| ResultValid、Success | 停稳后结果有效，Success 表示本次是否成功。按 Reset 恢复或发生故障后清除。 |
| State | 0 等反馈，10 等 Reset 启动，30 命令间隔，40 等定位确认，50 运动，55 等前一定位确认，60 等停止确认，70 等停稳，80 暂停并显示成绩，900 故障，905 等故障确认及就绪。 |
| FaultCode | 十六进制游戏诊断。0000 正常，0001 反馈或设备状态异常，0002 输入参数无效，0003 定位确认超时，0004 运动中连续 15 s 无位置变化且未到位，0005 停止超时，0008 未知状态，0009 运行许可撤销，000A 确认故障后 3 s 内仍未就绪。 |
| GripperFaultCode | SCHUNK 原生块 `i_DIAGNOSIS_ERROR` 原值。反馈无效时先检查通讯有效性。 |

运行 `python -m unittest discover -s tests -v`。V20 单元测试执行入口及游戏块的 SCL 逻辑，在原生块接口注入反馈并检查发出的命令。需要在 TIA 和实机验证编译、PROFINET 时序及停止响应。

## 历史版本

当前 TIA Portal V20 工程使用 `plc/v20/FB_StopGameV20.scl`。旧版 V18 草稿及其测试可从历史提交查看。[V18 历史说明](docs/PLC-V18.md)
