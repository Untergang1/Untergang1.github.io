# Untergang1 的个人主页

静态页面展示项目简介与最近提交。项目列表维护在 `index.html`，GitHub Actions 每天北京时间 **07:17**（UTC cron `17 23 * * *`）集中获取提交数据并部署 GitHub Pages。推送到 `main` 或手动运行也会获取数据并发布。

## 数据与发布

`scripts/build_site.py` 使用 Python 标准库读取 `ul.list` 内的 `a[data-repo]`，通过 Actions 内置的 `GITHUB_TOKEN` 查询各项目默认分支。`data-author` 存在时，最新提交和提交数都按该作者筛选。提交数由 `per_page=1` 的分页信息取得；日期优先采用提交作者时间，缺失时采用提交者时间，保留日期部分。

成功构建的 `_site/` 只包含页面和 `data/projects.json`。JSON 的 `generatedAt` 是 UTC 抓取完成时间，`projects` 按仓库名索引，各条目包含 `sha`（七位）、`date`（YYYY-MM-DD）、`msg`（提交消息首行）及 `count`（提交数）。生成数据只作为部署产物，不写入 Git 历史。

浏览器每次加载只请求一次本站 JSON，要求浏览器重新验证 HTTP 缓存；不调用 GitHub API、不使用 localStorage、不轮询。所有项目数据校验通过后才更新页面。请求超过 10 秒、网络失败或 JSON 无效时，保留 HTML 内预设内容；这些预设值是人工维护的展示兜底，不代表上次自动抓取结果。页面一直打开时需重新加载才会读取新数据。旧版 `gh-latest-v1` 浏览器缓存不再使用。

每个 API 请求超时为 20 秒。网络和 HTTP 5xx 错误最多尝试三次，间隔 2 秒、5 秒；权限错误、404 和限流不会密集重试。任一项目失败、没有符合条件的提交或数据不完整时，构建失败，不上传产物、不部署，线上保留上次成功发布的整站。构建和部署任务各有 10 分钟超时。

## 首次上线

1. 将本次修改推送到 `main`，确保仓库允许 GitHub Actions 运行。
2. 在仓库 **Settings → Pages → Build and deployment → Source** 选择 **GitHub Actions**。无需添加 PAT 或自定义 Secret。
3. 检查 `github-pages` environment 的部署分支规则，仅允许默认分支 `main`；需要无人值守每日发布时，不要配置必须人工批准的部署规则。
4. 在 **Actions → Update and deploy homepage → Run workflow** 选择 `main` 运行。若首次推送时 Pages 尚未配置好，完成设置后重跑。
5. 确认部署成功，访问主页与 `/data/projects.json`，检查 `generatedAt` 及项目显示。再核对次日定时运行记录。

workflow 只在 `Untergang1/Untergang1.github.io` 的 `main` 上构建和部署。构建权限为 `contents: read`；部署只授予 `pages: write` 和 `id-token: write`。统一并发组串行发布。其他项目仓库不需要添加文件或配置凭据。

## 维护与排查

- **添加、删除或改名项目**：修改 HTML 的项目链接和 `data-repo`；有作者筛选需求时设置 `data-author`，并更新预设提交信息、提交数。新增项目需有符合筛选条件的提交，否则会阻止整站发布。无需同步修改另一份项目清单。
- **新增静态资源**：当前页面的 CSS、JS 都内嵌在 HTML 中。若增加图片或独立脚本，需要同步调整构建脚本的发布文件清单。
- **更新失败**：查看失败运行中 `Fetch complete project snapshot` 的日志，定位仓库及错误；修复仓库名、作者或访问问题后重跑。网络或限流问题可稍后手动重跑；单纯重新部署旧产物不会重新获取数据。
- **数据时间没有变化**：先检查 Actions 是否执行及部署成功，再检查是否被 environment 审批或分支规则阻止。浏览器重新验证缓存仍受 Pages 缓存传播影响，不承诺瞬时更新。
- **长期无更新**：GitHub 可能在公开仓库连续 60 天无活动后停用定时任务。进入 Actions 对该 workflow 选择 **Enable workflow**，然后手动运行确认恢复；本项目不生成保活提交。
- **调度时间**：GitHub Actions 可能延迟或跳过繁忙时段的定时任务，07:17 是计划启动时间，不是发布完成保证。任务失败或停用时，数据可能超过一天未更新。

官方说明：[定时任务限制](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)、[Pages 自定义部署](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)。

## 本地验证

需要 Python 3.11+ 和 Node.js 22，测试不访问网络、不需要 Token，也没有第三方依赖。已有 conda 环境可直接使用：

```sh
conda run -n base python -m unittest discover -s tests -v
node --test tests/page.test.cjs
```

CI 使用 Python 3.12。若已有安全配置的 `GITHUB_TOKEN` 环境变量，可运行 `python scripts/build_site.py` 生成真实快照，再用 `python -m http.server 8000 --directory _site` 预览。不要把 Token 写进页面、脚本、命令行历史或仓库。直接预览源目录时没有生成 JSON，页面会使用预设信息。
