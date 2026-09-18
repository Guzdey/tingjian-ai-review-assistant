# 听荐 API

FastAPI 后端默认无需模型密钥即可运行。需求解析和报告文案使用可追溯的本地规则；配置百炼密钥后，会尝试用 `qwen-flash` 解析需求、用 `qwen-plus` 生成报告文案。任何超时、无效 JSON 或引用越界都会安全降级到本地规则。

模型来源与证据来源彼此独立：

- `local_rules` / `qwen` 表示需求和文案由什么处理；
- `demo_cache` / `derived_dataset` 表示证据来自合成演示缓存还是私有真实评论派生数据。

因此，“本地规则 + 真实评论派生证据”是合法运行状态，不能误标为演示缓存。

```powershell
python -m venv .venv
.venv\Scripts\pip install -r backend\requirements.txt
$env:TINGJIAN_AI_MODE = "local"
.venv\Scripts\python -m uvicorn backend.app.main:app --reload
```

加载不进入 Git 的私有派生证据：

```powershell
$env:TINGJIAN_DEMO_DATA_PATH = "D:\CodexData\tingjian-ai\processed\private_derived.json"
.venv\Scripts\python -m uvicorn backend.app.main:app --reload
```

也可以从仓库根目录运行 `scripts\run_api.ps1`；本机会自动检测上述 D 盘文件，其他机器没有该文件时回退到公开合成缓存。

打开 `http://127.0.0.1:8000/docs` 查看接口。运行测试：

```powershell
.venv\Scripts\python -m pytest backend\tests -q
```

核心接口：`GET /api/health`、`POST /api/needs/parse`、`POST /api/reports`、`GET /api/products/{id}/evidence`、`POST /api/compare`。仅支持 `demo-tws-a` 与 `demo-tws-b`。

未指定外部数据路径时优先加载仓库的 `data/demo_derived.json`。文件需包含 `products[]` 和 `evidence[]`；无法通过严格结构校验时自动回退到内置演示缓存。真实 API Key 只能放在服务端环境变量，不要提交 `.env`。
