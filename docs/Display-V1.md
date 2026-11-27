# 现场投屏实施步骤

现场电脑用以太网连接 S7-1200，用 HDMI 连接电视。电脑上运行 Node.js、Vue 页面及浏览器，电视选中对应 HDMI 输入即可。现场运行无需 GitHub、CDN、WinCC 或威纶通软件。

## 1. 先在电脑预演

安装 Node.js 22 或更新的 LTS，下载仓库后在 PowerShell 运行以下命令。首次安装依赖需要联网；在展会电脑上提前安装、保留 display/node_modules 即可离线启动。使用本地 Vue 发行版，无需单独构建页面。

```powershell
cd display
npm ci
npm test
npm run demo
```

在浏览器打开 http://127.0.0.1:3000，点击“全屏”。在 Windows 显示设置中选“复制”，或将浏览器移至扩展屏后全屏。回放会交替展示未命中和命中。演示和实机使用同一页面，页眉标明数据来源。用 Ctrl+C 停止服务。

## 2. 在 TIA Portal V20 新增显示 DB 和发布块

将 plc/v20/FunFairDisplay.scl 加入“外部源文件”，生成 DB_FunFairDisplay 和 FB_FunFairDisplay。保留原游戏块的 OB1 调用。在其后无条件周期调用一次 FB_FunFairDisplay，创建非保持实例 DB。不要将显示 DB 的寄存器接到夹爪命令。

| 发布块输入 | 接到当前项目的信号 |
|---|---|
| FirstScan | 与游戏块相同的 CPU 首扫系统位 |
| State、ResultValid、Success、ActualPosition_um、SignedError_um、FaultCode、GripperFaultCode | FB_FunFairEGU_V20_DB 的同名输出 |
| OpenPosition_um、ClosePosition_um、TargetPosition_um、Tolerance_um | 与游戏块相同的设定值。截图中依次为 22000、1000、13000、1000 |

发布块每扫描刷新位置和显示参数。ResultValid 上升时，它将当次 Success 和偏差存为最近成绩并递增序号。浏览器即使错过一个扫描周期的 ResultValid，也能展示最近成绩。该设计只保留最新一轮，适用于单夹爪展台。

## 3. 在 OB1 加入 MB_SERVER

在显示块后从“通信 → 其他 → MODBUS TCP”插入 MB_SERVER，创建独立实例 DB，每扫描调用。MB_HOLD_REG 接标准全局 DB 的完整数组 `"DB_FunFairDisplay".Registers`，DISCONNECT 接 FALSE，监视 ERROR 和 STATUS。使用的指令版本若提供 CONNECT 引脚，创建其要求的 TCON_IP_v4 连接参数，InterfaceId 选择 CPU 本机 PN 接口的硬件标识，ID 选项目中未占用的连接 ID，ConnectionType 为 TCP（16#0B），ActiveEstablished 为 FALSE，LocalPort 为 502，采用被动监听。若指令直接提供 CONNECT_ID、IP_PORT，引脚分别接未使用的 ID 和监听端口。以项目实际 CPU、固件及指令帮助中支持的接口为准。

保持默认保持寄存器起始偏移 0。编译硬件和软件并下载。将电脑网卡设置为与 CPU 同子网的独立 IP。可用 `Test-NetConnection <PLC实际IP> -Port 502` 验证 TCP 连通；寄存器映射是否正确由下一步的签名和实时值确认。该 Node 服务只发 FC03，MB_SERVER 本身支持其他功能，显示 DB 单独分配在现场网段使用。

## 4. 启动实机显示

```powershell
cd display
$env:PLC_HOST = "192.168.0.10"   # 换成 CPU 的实际 IP
npm start
```

地址仍为 http://127.0.0.1:3000。若需更改默认值，通过 PLC_PORT（502）、PLC_UNIT（1）、PORT（网页端口，默认 3000）设置。电脑顺序读取一帧 24 个寄存器，每次读取完成后等待 50 ms；连接异常自动重连。浏览器通过同源 SSE 接收。断线或 PLC 心跳停止时页面保留最后位置并显示数据中断。

## 5. 对照博途验收

1. 按截图条件，暂停、State=80、ResultValid=TRUE、Success=FALSE 时，网页应显示未命中，当前位置 22.000 mm，目标 13.000 mm，偏差 +9.000 mm，窗口 ±1.000 mm，程序码和夹爪码均为 0x0000。首次导入发布块时若该轮成绩已经有效，也会捕获一次。
2. 解锁，观察橙色位置标记随夹爪往复，目标带为 12–14 mm。命中条件沿用 PLC 的严格小于窗口半宽；网页直接显示 PLC 结果。
3. 在目标附近按 Pause，等待停稳，核对新成绩。再按 Reset 恢复，最近成绩应保留到下一轮。调换开合坐标方向时，夹紧仍在轨道左端，张开仍在右端。
4. 断开电脑的以太网线，页面应提示连接中断。恢复后自动回到当前帧。若只显示等待数据，检查服务终端、MB_SERVER.STATUS 和下表签名；若显示游戏故障，核对游戏和夹爪两个诊断码。

## 寄存器布局

FC03 起址 0（常见人机界面记作 40001），共 24 个 16 位字。双字使用高字在前、二补码有符号整数。位置和偏差单位为 µm。

| 零基偏移 | 内容 |
|---|---|
| 0、1、2 | 签名 16#4646、版本 1、每扫描变化的心跳 |
| 3、4、5 | State、ResultValid、Success |
| 6、7 | FaultCode、GripperFaultCode |
| 8、9 | ResultSeq（0 表示本次启动尚无成绩）、LastSuccess |
| 10–11、12–13、14–15 | 实际位置、张开位置、夹紧位置 |
| 16–17、18–19 | 游戏目标、窗口半宽。暂停时锁定本轮值 |
| 20–21、22–23 | 当前有符号偏差、最近成绩有符号偏差 |
