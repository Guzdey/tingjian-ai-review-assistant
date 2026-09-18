"""Drive the local UI against private rule-derived evidence via CDP."""

from __future__ import annotations

import argparse
import asyncio
import base64
from pathlib import Path

from browser_smoke import CdpClient, find_page, wait_for
from websockets.asyncio.client import connect


async def run(port: int, screenshot: Path) -> None:
    target = find_page(port)
    async with connect(target["webSocketDebuggerUrl"], max_size=8_000_000) as websocket:
        client = CdpClient(websocket)
        await client.command("Runtime.enable")
        await client.command("Page.enable")

        await client.command("Page.reload", {"ignoreCache": True})
        home = await wait_for(client, "AI帮我判断")
        assert "真实评论派生数据 · 本地规则" in home, home

        await client.evaluate("document.querySelector('.round').click()")
        await wait_for(client, "你准备怎么使用这副耳机")
        await client.evaluate("document.querySelector('button.cta').click()")
        confirm = await wait_for(client, "需求确认")
        assert "本地规则解析" in confirm and "通勤" in confirm

        await client.evaluate("document.querySelector('button.cta').click()")
        report = await wait_for(client, "总体判断")
        assert "真实评论派生证据 · 本地规则报告" in report, report
        assert "演示缓存结果" not in report

        await client.evaluate("document.querySelector('.evidence-button').click()")
        evidence = await wait_for(client, "证据详情")
        assert "派生数据" in evidence and "private-clean:" in evidence, evidence
        assert "Synthetic demo quote" not in evidence

        await client.evaluate("go('report')")
        await wait_for(client, "与另一款匿名样本比较")
        await client.evaluate(
            "Array.from(document.querySelectorAll('.metric-row.action'))"
            ".find(node=>node.textContent.includes('比较')).click()"
        )
        await wait_for(client, "选择对比商品")
        await client.evaluate("document.querySelector('.product-choice').click()")
        await client.evaluate("document.querySelector('button.cta').click()")
        comparison = await wait_for(client, "比较结论")
        assert "真实评论派生证据 · 本地规则报告" in comparison, comparison
        assert "演示缓存结果" not in comparison

        capture = await client.command("Page.captureScreenshot", {"format": "png"})
        screenshot.parent.mkdir(parents=True, exist_ok=True)
        screenshot.write_bytes(base64.b64decode(capture["data"]))
        print("Private-data browser smoke passed: product -> need -> report -> evidence -> compare")
        print(f"Screenshot: {screenshot}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=9222)
    parser.add_argument(
        "--screenshot",
        type=Path,
        default=Path(r"D:\CodexData\tingjian-ai\browser-smoke-private.png"),
    )
    args = parser.parse_args()
    asyncio.run(run(args.port, args.screenshot))


if __name__ == "__main__":
    main()
