# 💡 Yeelight Pro for Home Assistant

[![GitHub Release](https://img.shields.io/github/v/release/nichwang88/yeelight-pro)](https://github.com/nichwang88/yeelight-pro/releases)
[![GitHub License](https://img.shields.io/github/license/nichwang88/yeelight-pro)](LICENSE)

Yeelight Pro 智能家居设备的 Home Assistant 集成。支持通过 Yeelight Pro 网关（Gateway Pro / 全面屏面板）控制照明、窗帘、浴霸、空调（VRF）、传感器等设备。

## 功能特性

### 支持的设备类型
- **灯光 (Light)** — 开关、亮度、色温、RGB 颜色
- **窗帘 (Cover)** — 开合控制、位置调节、叶片角度调节
- **浴霸 (Bath Heater)** — 多实体控制：
  - 🔌 电源总开关 (Switch)
  - 💡 灯光开关 + 亮度调节 (Light)
  - 🌀 换气风速 (Fan)
  - 🌬️ 凉风风速 (Fan)
  - 🔥 暖风风速 (Fan)
  - 🎯 目标环境温度 (Number)
  - ⚡ 快速模式选择 (Select) — 智能干燥 / 恒温除雾 / 快速除雾 / 极速加热
  - 🌡️ 环境温度传感器 (Sensor)
- **空调 / VRF (Climate)** — 温度、模式、风速
- **人体传感器 (Motion Sensor)** — 运动检测、光照度
- **接近传感器 (Presence Sensor, pt=138)** — 人体存在检测
- **开关 / 按钮 (Switch / Button)** — 面板按键事件
- **旋钮 (Knob)** — 旋转事件

### 网关支持
- Gateway Pro 网关 (pt=1)
- WiFi 全面屏面板 (pt=2)

## 更新日志

### v0.4.0 — 浴霸多实体重构
- **浴霸设备重构**：从 Climate 实体改为多实体方案（Fan + Select + Sensor + Number + Switch），提供更直观的控制体验
- 新增 `fan` 平台 — 支持换气、凉风、暖风的 4 档风速控制
- 新增 `select` 平台 — 支持浴霸快速模式选择
- 浴霸电源总开关、环境温度传感器、目标温度数值调节

### v0.3.0 — 重大改进
- **修复 pt=138 接近传感器** — 正确识别 PRESENCE_SENSOR 类型设备
- 拓扑发现改进：使用 `asyncio.gather` 并行处理节点
- 窗帘叶片角度(Tilt)支持
- 网关连接可靠性增强：TCP 连接清理、`wait_result=True`
- `send_command` 服务 bug 修复
- 集成卸载支持 (`async_unload_entry`)
- VRF 空调设备路由支持
- 动态 Converter 检测与实体创建优化
- 设备属性保留 (`pt` 字段)

### v0.2.0
- 初始浴霸 Climate 支持
- 基础设备类型支持

## 致谢

感谢以下贡献者的代码参考和灵感：

- **[@ethan-z11](https://github.com/ethan-z11/Yeelight_Pro)** — v0.3.0 的多项改进（并行拓扑发现、窗帘 Tilt 支持、连接可靠性、VRF 路由等）以及 v0.4.0 浴霸多实体方案均参考了其 fork 的实现
- **[@al-one](https://github.com/hasscc/yeelight-pro)** — 原始项目作者

<a name="installing"></a>
## 安装

#### 方法 1: [HACS (**点击安装**)](https://my.home-assistant.io/redirect/hacs_repository/?owner=nichwang88&repository=yeelight-pro&category=integration)

#### 方法 2: 手动安装 (Samba / SFTP)
> [下载](https://github.com/nichwang88/yeelight-pro/archive/main.zip) 并复制 `custom_components/yeelight_pro` 文件夹到 Home Assistant 配置目录的 `custom_components` 文件夹

#### 方法 3: SSH 一键安装
```shell
wget -O - https://hacs.vip/get | DOMAIN=yeelight_pro REPO_PATH=nichwang88/yeelight-pro bash -
```

## License

This project is licensed under the MIT License.
