# FunFair
FunFair for SCHUNK Intec China Christmas Event


## 精准停位小游戏（程序草稿 v0.2）

目标组合：TIA Portal V18、S7-1200 CPU 1211C DC/DC/DC、SCHUNK EGU 60-PN-M-B。

进入已准备好的游戏模式后自动往复；按钮完整按下再松开，用 `R_TRIG` 的松开上升沿交替触发停止判分与下一回合。按住期间不切换。

- [SCL 游戏功能块](plc/FB_FunFair_StopGame.scl)
- [接口映射、触发逻辑、恢复流程与验证清单](docs/PLC-V18.md)
- [扫描逻辑回归检查](tests/test_scan_logic.py)

**尚未通过 TIA V18 编译、PLCSIM 或实机验证。** 本仓库交付游戏控制层；设备初始化、故障恢复、PN 有效性及现场安全功能仍需在实际工程中集成。回归检查不替代 Siemens 工具链或现场验证。
