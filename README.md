# BUPT Library Crawler

## 中文说明

这是一个面向北京邮电大学图书馆 OPAC（`http://opac.bupt.edu.cn:8080`）的馆藏信息爬取与 Excel 整理工具。程序会从“分类浏览”页读取中图法分类，按分类分页抓取书目记录，再进入详情页解析馆藏副本信息，最后导出为 Excel。

默认运行是安全的小规模试跑：每个分类只抓 1 页。全量抓取请确认已获得授权、遵守图书馆网站规则，并使用较大的请求间隔。

### 功能

- 自动读取 OPAC 分类列表。
- 按中图法分类抓取书名、作者、ISBN/ISSN、出版社、出版年、索书号、主题词、馆藏数、可借数等字段。
- 解析详情页馆藏表，保存馆藏部门、条码、流通/架位状态、架位导航链接等信息。
- 使用 SQLite 保存断点，支持 `--resume` 续跑。
- 导出 Excel：`Summary`、`All Books`、`Holdings` 和各大类分类 sheet。
- 内置限速、重试和 Referer 处理。

### 安装

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### 试跑

```powershell
python -m bupt_library_crawler.cli --codes B821 --max-pages 1 --delay 1.5
```

输出文件：

- SQLite 断点库：`data/bupt_library.sqlite3`
- Excel 文件：`output/bupt_library_holdings.xlsx`

### 全量抓取

```powershell
python -m bupt_library_crawler.cli --full --resume --delay 2.0
```

只抓指定分类：

```powershell
python -m bupt_library_crawler.cli --codes A11 B821 TP311 --full --resume --delay 2.0
```

仅从已有 SQLite 导出 Excel：

```powershell
python -m bupt_library_crawler.cli --export-only
```

### 发布到 GitHub

本机需要先登录 GitHub CLI：

```powershell
gh auth login
```

登录后运行：

```powershell
.\scripts\create_github_repo.ps1 -RepoName bupt-library-crawler -Visibility private
```

### 注意事项

- 不建议高并发抓取。该项目默认串行并限速。
- Excel 单个 sheet 有行数上限；如果馆藏数据极大，请优先保留 SQLite 数据库，或分批导出。
- 请勿抓取登录后才可见的个人信息或绕过访问控制。

## English

This project crawls public catalog and holding records from the Beijing University of Posts and Telecommunications Library OPAC (`http://opac.bupt.edu.cn:8080`) and exports the result to Excel.

The default command is a conservative smoke test: it crawls only one page per category. Before running a full crawl, make sure you have authorization, follow the library website rules, and use a respectful request delay.

### Features

- Reads CLC category codes from the OPAC category browsing page.
- Crawls bibliographic fields such as title, authors, ISBN/ISSN, publisher, publication date, call number, subject terms, holding count, and availability count.
- Parses item-level holding rows from detail pages, including department, barcode, status, and shelf-location URL.
- Stores crawl progress in SQLite and supports resumable runs with `--resume`.
- Exports Excel sheets: `Summary`, `All Books`, `Holdings`, and one sheet per top-level category.
- Handles Referer checks, retries, and polite throttling.

### Installation

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### Smoke Test

```powershell
python -m bupt_library_crawler.cli --codes B821 --max-pages 1 --delay 1.5
```

Outputs:

- SQLite checkpoint database: `data/bupt_library.sqlite3`
- Excel workbook: `output/bupt_library_holdings.xlsx`

### Full Crawl

```powershell
python -m bupt_library_crawler.cli --full --resume --delay 2.0
```

Crawl selected categories only:

```powershell
python -m bupt_library_crawler.cli --codes A11 B821 TP311 --full --resume --delay 2.0
```

Export from an existing SQLite database only:

```powershell
python -m bupt_library_crawler.cli --export-only
```

### Publish to GitHub

Sign in to GitHub CLI first:

```powershell
gh auth login
```

Then run:

```powershell
.\scripts\create_github_repo.ps1 -RepoName bupt-library-crawler -Visibility private
```

### Notes

- Avoid high-concurrency crawling. This project is intentionally serial and rate-limited.
- Excel sheets have row limits. For very large crawls, keep the SQLite database as the canonical dataset or export in batches.
- Do not crawl private, login-only, or access-controlled personal data.

