"""Drive the local demo through Chrome DevTools Protocol.

Prerequisites:
- API at http://127.0.0.1:8000
- static site at http://127.0.0.1:5500
- headless Chrome started with --remote-debugging-port=9222
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import urllib.request
from pathlib import Path
from typing import Any

from websockets.asyncio.client import connect


class CdpClient:
    def __init__(self, websocket: Any) -> None:
        self.websocket = websocket
        self.counter = 0

    async def command(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self.counter += 1
        message_id = self.counter
        await self.websocket.send(
            json.dumps({"id": message_id, "method": method, "params": params or {}})
        )
        while True:
            response = json.loads(await self.websocket.recv())
            if response.get("id") != message_id:
                continue
            if "error" in response:
                raise RuntimeError(f"CDP {method} failed: {response['error']}")
            return response.get("result", {})

    async def evaluate(self, expression: str) -> Any:
        result = await self.command(
            "Runtime.evaluate",
            {"expression": expression, "returnByValue": True, "awaitPromise": True},
        )
        remote = result.get("result", {})
        if "exceptionDetails" in result:
            raise RuntimeError(result["exceptionDetails"])
        return remote.get("value")


def find_page(port: int) -> dict[str, Any]:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=5) as response:
        targets = json.load(response)
    for target in targets:
        if target.get("type") == "page" and "127.0.0.1:5500" in target.get("url", ""):
            return target
    raise RuntimeError("No local Tingjian page target found")


async def wait_for(client: CdpClient, needle: str, timeout: float = 8.0) -> str:
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        snapshot = await client.evaluate("location.search + '\\n' + document.body.innerText")
        if needle in snapshot:
            return snapshot
        await asyncio.sleep(0.15)
    raise AssertionError(f"Timed out waiting for {needle!r}")


async def run(port: int, screenshot: Path) -> None:
    target = find_page(port)
    async with connect(target["webSocketDebuggerUrl"], max_size=8_000_000) as websocket:
        client = CdpClient(websocket)
        await client.command("Runtime.enable")
        await client.command("Page.enable")

        home = await wait_for(client, "AI帮我判断")
        assert "本地缓存模式" in home, home

        await client.evaluate("document.querySelector('.round').click()")
        await wait_for(client, "你准备怎么使用这副耳机")

        await client.evaluate("document.querySelector('button.cta').click()")
        confirm = await wait_for(client, "需求确认")
        assert "通勤" in confirm and "视频会议" in confirm

        await client.evaluate("document.querySelector('button.cta').click()")
        report = await wait_for(client, "总体判断")
        assert "演示缓存结果" in report
        assert "通话清晰" in report and "连接稳定" in report

        await client.evaluate("document.querySelector('.evidence-button').click()")
        evidence = await wait_for(client, "证据详情")
        assert "Synthetic demo quote" in evidence

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
        assert "演示缓存结果" in comparison

        capture = await client.command("Page.captureScreenshot", {"format": "png"})
        screenshot.parent.mkdir(parents=True, exist_ok=True)
        screenshot.write_bytes(base64.b64decode(capture["data"]))
        print("Browser smoke test passed: product -> need -> confirm -> report -> evidence -> compare")
        print(f"Screenshot: {screenshot}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=9222)
    parser.add_argument(
        "--screenshot", type=Path, default=Path(r"D:\CodexData\tingjian-ai\browser-smoke.png")
    )
    args = parser.parse_args()
    asyncio.run(run(args.port, args.screenshot))


if __name__ == "__main__":
    main()
