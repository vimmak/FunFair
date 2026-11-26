# FunFair
FunFair for SCHUNK Intec China Christmas Event


## 当前版本 · 博途 V20，双 PNP 按钮

[集成入口 FB_FunFairEGU_V20](plc/v20/FB_FunFairEGU_V20.scl) 每扫描调用 [游戏块 FB_StopGameV20](plc/v20/FB_StopGameV20.scl) 和雄克原生周期块。依次导入厂家提供的原生 SCL、游戏块、集成入口。OB1 周期调用集成入口一次，使用非保持实例和有效首次扫描信号，避免其他块同时写夹爪。

StartDI 接点动开始，PauseDI 接自锁暂停，两路均取滤波后的 PNP 输入。开始上升沿启动往复。暂停锁入后发普通 STOP，收到停止确认且位置稳定后判分。暂停自锁期间屏蔽开始，解锁后须重新按开始。上电先释放两个按钮。

OB1 每扫描无条件调用入口。保留 MotionPermit（运行许可）、DataValid（实际 PN 数据有效）和 ResetButton（点动复位）。原有模式或调试许可如仍需使用，可在 OB1 合入 MotionPermit。原生块的 b_00_FAST_STOP 固定写 TRUE。该值仅描述 PLC 正常交换时的命令，掉线与 CPU STOP 时的设备行为由实际组态决定。

夹爪报错时先排除原因，解锁暂停并释放开始，按住复位发送 b_02_ACKNOLEDGE，直到设备错误消失或松开复位。设备恢复就绪后，再松开并重新按复位清游戏故障，另按开始才会运动。仅游戏故障时一次复位即可。

新版沿用无工件定位模式，夹持及 GPE 指令关闭，现场需按负载确认。定位确认未到时暂停仍先等该确认，再发受控停止；确认超时进入故障。暂停按钮仅用于游戏。扫描逻辑已测试，V20 编译、设备初始化以及实机停止时序尚待验证。

## 历史版本 · 精准停位小游戏（程序草稿 v0.2）

目标组合：TIA Portal V18、S7-1200 CPU 1211C DC/DC/DC、SCHUNK EGU 60-PN-M-B。

进入已准备好的游戏模式后自动往复；按钮完整按下再松开，用 `R_TRIG` 的松开上升沿交替触发停止判分与下一回合。按住期间不切换。

- [SCL 游戏功能块](plc/FB_FunFair_StopGame.scl)
- [接口映射、触发逻辑、恢复流程与验证清单](docs/PLC-V18.md)
- [扫描逻辑回归检查](tests/test_scan_logic.py)

**尚未通过 TIA V18 编译、PLCSIM 或实机验证。** 本仓库交付游戏控制层；设备初始化、故障恢复、PN 有效性及现场安全功能仍需在实际工程中集成。回归检查不替代 Siemens 工具链或现场验证。
