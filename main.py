"""AstrBot 插件：Malody → osu!mania 谱面转换器。

将用户发送（或回复）的 Malody 谱面文件（.mc / .mcz / .zip）转换为
osu!mania 的 .osz 谱面包并回传。核心转换逻辑移植自独立脚本 convert.py
（original by Jakads, modified by Eric Zhao）。
"""

from __future__ import annotations

import asyncio
import os
import shutil
import time
from pathlib import Path

from astrbot.api import logger
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api.message_components import File, Reply

from .converter import convert_to_osz, OszResult

# 支持的输入文件扩展名
_INPUT_EXTS = (".mc", ".mcz", ".zip")
# 单个文件大小上限（MB），0 表示不限制
_MAX_FILE_SIZE_MB = 50


@register(
    "astrbot_plugin_malody2osu",
    "ZHAO20060708",
    "将 Malody 谱面 (.mc/.mcz/.zip) 转换为 osu!mania 谱面包 (.osz)",
    "1.0.0",
    "https://github.com/ZHAO20060708/malody2osu",
)
class Malody2Osu(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.plugin_dir = Path(__file__).parent
        self.cache_dir = self.plugin_dir / "cache"
        self.cache_dir.mkdir(exist_ok=True)

    def _iter_components(self, event: AstrMessageEvent):
        """当前消息的组件，外加被引用（回复）消息中的组件。"""
        comps = list(event.message_obj.message)
        expanded = []
        for comp in comps:
            if isinstance(comp, Reply) and comp.chain:
                expanded.extend(comp.chain)
        # 命令通常是“回复某个文件”，故被引用消息优先。
        return expanded + comps

    async def _get_attached_file(self, event: AstrMessageEvent):
        """在消息或其引用中查找 .mc/.mcz/.zip 文件。

        返回 (本地路径, 文件名) 或 None；扩展名/大小不合法时抛出 ValueError。
        """
        max_bytes = _MAX_FILE_SIZE_MB * 1024 * 1024 if _MAX_FILE_SIZE_MB > 0 else 0
        for comp in self._iter_components(event):
            if not isinstance(comp, File):
                continue
            name = os.path.basename((comp.name or "file").replace("\\", "/"))
            if not name.lower().endswith(_INPUT_EXTS):
                raise ValueError(f"请回复 {'/'.join(_INPUT_EXTS)} 格式的文件。")
            local = await comp.get_file()
            if not local or not os.path.exists(local):
                return None
            if max_bytes and os.path.getsize(local) > max_bytes:
                raise ValueError(f"文件过大，超过 {_MAX_FILE_SIZE_MB} MB 限制。")
            return local, name
        return None

    @staticmethod
    def _format_report(result: OszResult) -> str:
        lines = [f"[O] 转换完成：{os.path.basename(result.osz_path)}"]
        if result.artist or result.title:
            lines.append(f"曲目：{result.artist} - {result.title}")
        lines.append(f"已转换谱面：{len(result.converted)} 个")
        if result.skipped:
            shown = result.skipped[:10]
            lines.append("已跳过：")
            lines.extend(f"  - {s}" for s in shown)
            if len(result.skipped) > len(shown):
                lines.append(f"  - ...等 {len(result.skipped) - len(shown)} 个")
        if result.missing_assets:
            lines.append(
                "[!] 以下资源未在文件内找到，未打包（请将音频/背景一并打包后重试）："
            )
            lines.append("  " + ", ".join(result.missing_assets[:10]))
        return "\n".join(lines)

    @filter.command("malody2osu", alias={"mc2osu", "转osz", "马转o"})
    async def malody2osu_cmd(self, event: AstrMessageEvent):
        '''Malody 转 osu!mania。回复（或附带）一个 .mc/.mcz/.zip 文件即可转换为 .osz 谱面包。'''
        try:
            found = await self._get_attached_file(event)
        except ValueError as e:
            yield event.plain_result(str(e))
            return

        if found is None:
            yield event.plain_result(
                "请回复或附带一个 Malody 谱面文件（.mc / .mcz / .zip），我会把它转换成 osu!mania 的 .osz 谱面包。\n"
                "提示：单个 .mc 不含音频/背景；如需完整谱面包请发送 .mcz 或 .zip。"
            )
            return

        local_path, file_name = found
        yield event.plain_result(f"已收到文件：{file_name}，正在转换，请稍候...")

        work_dir = self.cache_dir / f"m2o_{int(time.time() * 1000)}_{os.getpid()}"
        try:
            try:
                result = await asyncio.to_thread(
                    convert_to_osz, local_path, file_name, str(work_dir)
                )
            except ValueError as e:
                yield event.plain_result(f"转换失败：{e}")
                return
            except Exception as e:  # noqa: BLE001
                logger.exception("malody2osu 转换出错")
                yield event.plain_result(f"转换出错：{e}")
                return

            yield event.plain_result(self._format_report(result))
            osz_name = os.path.basename(result.osz_path)
            yield event.chain_result([File(name=osz_name, file=result.osz_path)])
        finally:
            # 延迟清理，给文件发送留出读取时间。
            asyncio.create_task(self._cleanup_later(work_dir))

    async def _cleanup_later(self, work_dir: Path, delay: float = 60.0):
        await asyncio.sleep(delay)
        shutil.rmtree(work_dir, ignore_errors=True)
