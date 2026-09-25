# Untergang1 的主页

静态主页使用 HTML 片段组织内容，通过 Python 标准库构建，由 GitHub Actions 发布到 GitHub Pages。无需安装前端依赖；本地需要 Python 3.12 或更新版本，运行交互测试还需要 Node.js 22。

## 日常编辑

| 想修改的内容 | 文件 |
| --- | --- |
| 名字、词条解释、简介 | `content/header.html` |
| 栏目标题、日期、项目名称和说明 | `content/sections/*.html` |
| 页脚说明和导航链接 | `content/footer.html` |
| 浏览器标题、搜索摘要、字体和页面骨架 | `templates/page.html` |
| 配色、字号、间距、响应式布局 | `assets/style.css` |
| 提交信息展示、悬停效果和太阳动画 | `assets/main.js` |

直接编辑 HTML 标签里的文字即可。正文中的 `&` 和 `<` 应写成 `&amp;` 和 `&lt;`，属性值中的双引号写成 `&quot;`。保留现有 `class` 和 `id`，以便样式和交互继续工作。

### 栏目和项目

构建会按文件名顺序读取 `content/sections/` 下的所有 `.html` 文件。重命名数字前缀即可调整栏目顺序；复制一个文件并更换内容即可添加栏目。栏目内项目的顺序就是 `<li>` 的排列顺序，复制或删除整个 `<li>…</li>` 可添加或删除项目。

每个项目链接需要保留以下信息：

- `href`：点击后打开的地址。
- `data-repo`：Untergang1 账户下的 GitHub 仓库名，同一页面不得重复；构建用它获取提交信息。
- `data-author`：可选，按作者筛选提交，当前主要用于 fork。保留实际的作者名，例如 OSWorld 使用 `untergang404`。
- `data-sha`、`data-date`、`data-msg`：提交短 SHA（7 位小写十六进制）、日期（`YYYY-MM-DD`）和单行说明，用于离线预览及快照读取失败时的默认显示。
- `<span class="n">`：默认提交数，填写正整数。

项目名称、技术标签和 `.desc` 中的说明均可直接修改。新增项目时请同步填写上述默认值。正式部署每日获取最新提交信息，不会把结果写回内容文件。

## 本地预览

在仓库根目录运行：

```sh
python3 scripts/build_site.py --preview
python3 -m http.server 8000 --directory _site
```

打开 `http://localhost:8000`。预览构建不需要 token，也不会请求 GitHub API；提交信息来自 HTML 中的默认值。字体仍使用页面引用的 Google Fonts，离线时使用系统备用字体。

修改源文件后，重新运行第一条命令并刷新浏览器。不要直接编辑 `_site/`：它是被 Git 忽略的构建产物，每次构建都会重新生成。

## 构建与部署

`templates/page.html` 必须各包含一个 `<!-- include:header -->`、`<!-- include:sections -->` 和 `<!-- include:footer -->` 插槽。构建先装配完整 HTML，再读取项目列表，最后输出 `_site/index.html`、`_site/assets/` 和 `_site/data/projects.json`。正文在构建时已写入页面，无需 JavaScript 才能阅读。

正式构建使用 `python3 scripts/build_site.py`，要求环境变量 `GITHUB_TOKEN`。所有项目快照必须获取成功；失败时不保留本次可部署产物。浏览器只请求同源的 `data/projects.json`，读取失败时保留 HTML 默认值。

推送到 `main`、手动触发 workflow 或每日北京时间 07:17 的定时任务都会执行测试、构建和部署。发布文件仅取自 `_site/`，源内容和测试不在发布目录内。

## 验证

```sh
python3 -m unittest discover -s tests -v
node --test tests/page.test.cjs
```

Node 测试会调用 `python3` 装配页面；如需指定 Python 解释器，可设置 `PYTHON` 环境变量。测试不访问 GitHub。提交布局修改前，另行检查桌面和移动端、深浅色模式、悬停及滚动效果。
