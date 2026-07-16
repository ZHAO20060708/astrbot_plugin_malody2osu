# Malody to osu!mania 转换插件

`astrbot_plugin_malody2osu` 是一个 AstrBot 插件，用于将 Malody Key 模式谱面转换为 osu!mania 谱面包。插件支持 `.mc`、`.mcz` 和 `.zip` 输入，并返回可直接导入 osu! 的 `.osz` 文件。

转换逻辑移植自 [malody2osu](https://github.com/ZHAO20060708/malody2osu)，保留了 TimingPoints、SV 与 HitObjects 的主要转换行为。

## 功能

- 将单个 `.mc` 文件转换为 `.osz`。
- 批量转换 `.mcz` 或 `.zip` 中的多个 Key 模式难度。
- 自动打包压缩包内可用的音频与背景资源。
- 列出未转换的谱面和缺失资源。
- 对上传大小、解压后总大小和临时文件保留时间提供 WebUI 配置。
- 拒绝路径穿越、符号链接和异常膨胀的压缩包。

## 环境要求

- AstrBot `>=4.9.2,<5`
- 无额外第三方 Python 依赖

## 安装

在 AstrBot WebUI 中使用以下 GitHub 地址安装：

```text
https://github.com/ZHAO20060708/astrbot_plugin_malody2osu
```

也可以手动克隆到 AstrBot 插件目录：

```bash
cd AstrBot/data/plugins
git clone https://github.com/ZHAO20060708/astrbot_plugin_malody2osu.git
```

安装完成后重载插件或重启 AstrBot。

## 使用

发送或回复一个 `.mc`、`.mcz` 或 `.zip` 文件，然后使用以下任一命令：

```text
/malody2osu
/mc2osu
/转osz
/马转o
```

插件完成转换后会先返回处理报告，再发送生成的 `.osz` 文件。

## 输入说明

- `.mc`：通常只包含单个谱面描述，不一定包含音频和背景。
- `.mcz` / `.zip`：可包含多个难度及相关资源，适合生成完整谱面包。
- 仅转换 Malody Key 模式（`mode = 0`）；其他模式会被跳过。

## 配置

| 配置项 | 默认值 | 说明 |
| --- | ---: | --- |
| `max_file_size_mb` | `50` | 单个上传文件大小上限；`0` 表示不限制 |
| `max_extracted_size_mb` | `500` | 压缩包解压后的总大小上限 |
| `cleanup_delay_seconds` | `120` | 发送完成后延迟清理临时文件的秒数 |

配置可在 AstrBot WebUI 中修改。临时数据存放于：

```text
data/plugin_data/astrbot_plugin_malody2osu/cache/
```

## 已知限制

- 转换结果取决于 Malody 文件内保存的信息，缺失的音频或背景无法自动补全。
- 不同客户端对特殊 SV、采样和元数据的解释可能存在差异。
- 转换后的谱面应在 osu! 编辑器中检查后再发布。

## 许可证与致谢

- 原始转换逻辑：Jakads
- AstrBot 适配与维护：[ZHAO20060708](https://github.com/ZHAO20060708)

使用、修改和分发时请遵守本仓库的 [`LICENSE`](LICENSE)。
