# 展台 Wi-Fi 排行榜

## 先用手机测试

在展台电脑的 PowerShell 中用 `ipconfig` 找到展台 Wi-Fi 网卡的 IPv4 地址。电脑有线网口继续连接 PLC。选择与 PLC 网段不同的 Wi-Fi 网段，避免路由冲突。

停止现有 FunFair 服务，从更新后的仓库根目录运行：

```powershell
cd display
npm ci
$env:FUNFAIR_PHONE_HOST = "192.168.50.10" # 改成电脑的 Wi-Fi IPv4 地址
npm run demo -- --moving
```

大屏打开 `http://127.0.0.1:3000`。等待约 6 秒出现第一个认领码。让手机连接相同 Wi-Fi 后，用微信扫大屏二维码，输入昵称及六位认领码。手机显示成绩和当前排名，大屏侧栏约每秒更新一次。若手机打不开，先用手机浏览器打开启动日志里的地址，再检查 Windows 防火墙是否允许展台网段访问 TCP 3001，以及 Wi-Fi 是否启用了客户端隔离。可为电脑 Wi-Fi 固定 DHCP 租约，避免二维码因地址变化而失效。

试玩环境在内存保存成绩，重启后清空。每条成绩可在两分钟内认领一次，短时间生成多条成绩时，大屏显示最新一轮的码，之前的码在过期前仍可使用。

## 接入真实比赛

重新导入并编译 `plc/v20/FunFairDisplay.scl`，下载显示块及更新后的实例 DB。其 OB1 引脚和 26 字 Modbus 映射沿用现有配置。新版显示协议使用 `Registers[1]=3`，在判分时把实际难度锁存到 `Registers[25]`，从而支持玩家快速解锁并切换难度的场景。旧显示协议仍可投屏。实机模式只从启动后新出现的成绩序号生成码。

```powershell
$env:PLC_HOST = "192.168.0.150"
$env:PLC_POLL_MS = "10"
npm start
```

榜单保存在 `display/data/leaderboard.sqlite`。手机服务只在配置的 Wi-Fi IPv4 地址监听，默认端口为 3001，也可通过 `FUNFAIR_PHONE_PORT` 指定。大屏服务在电脑本机提供认领码和游戏状态，手机端只开放认领和查榜功能。
