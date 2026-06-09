# astrbot_plugin_malody2osu

将 **Malody** 谱面文件（`.mc` / `.mcz` / `.zip`）转换为 **osu!mania** 谱面包（`.osz`）的 AstrBot 插件。

核心转换逻辑移植自独立命令行脚本 [malody2osu](https://github.com/ZHAO20060708/malody2osu)（original by Jakads，modified by Eric Zhao），时序点（TimingPoints）、变速效果（SV）与物件（HitObjects）的计算与原脚本保持一致。

## 使用方法

1. 在聊天中以**文件**形式发送一个 Malody 谱面（`.mc`、`.mcz` 或 `.zip`）。
2. **回复**该文件并发送命令 `/malody2osu`（或别名 `/mc2osu`、`/转osz`、`/马转o`）。
   - 也可以在同一条消息里同时附带文件与命令。
3. 机器人会转换并回传一个 `.osz` 谱面包，直接运行即可导入 osu!。

> 提示：单独的 `.mc` 文件不包含音频与背景；如需完整谱面包，请发送 `.mcz` 或 `.zip`。
> 仅会转换 **Key（mode 0）** 难度，其它模式的谱面会被跳过。

## 命令

| 命令 | 说明 |
| --- | --- |
| `/malody2osu` | 转换回复/附带的 Malody 谱面文件为 `.osz` |
| `/mc2osu`、`/转osz`、`/马转o` | 同上（别名） |

## 配置

`main.py` 顶部的 `_MAX_FILE_SIZE_MB` 控制允许的最大上传文件大小（MB，`0` 表示不限制），默认 `50`。

## 致谢

- 原始转换脚本：Jakads
- 修改与维护：Eric Zhao (ZHAO20060708)
