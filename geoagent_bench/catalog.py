"""Render the public catalog from the versioned task and rubric definitions."""

import html
import json
from pathlib import Path

from .common import ROOT, all_tasks, jsonl, read_json
from .protocol import prompt_for

ORIGIN = {"public_original": "公开原题", "adapted": "改编题", "new": "新增题"}
DIFFICULTY = {"single": "单任务", "composite": "复合任务"}
GRADING = {
    "review": "评分合同与证据复核",
    "reference_review": "冻结参考值与证据复核",
    "postgis_and_review": "PostGIS 终态检查与证据复核",
    "visual_review": "上游选项与视觉复核",
    "application_review": "应用保存和重开复核",
}


def source_link(source):
    url, rev = source.get("url"), source["revision"]
    if url:
        return f"{url.rstrip('/')}/tree/{rev}"
    return "../../geoagent_bench/fixtures.py"


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data.rstrip() + "\n", encoding="utf-8", newline="\n")


def markdown(tasks, domains, rubrics):
    folder = ROOT / "docs/tasks"
    header = [
        "# 题目目录", "",
        "选择领域查看提示词、输入、环境、代码交付、评分和来源。",
        "输入版本与获取方式见 [数据清单](../../assets/manifest.json)。",
        "浏览器筛选版见 [catalog.html](../catalog.html)。",
        "", "| 领域 | 单任务 | 复合任务 |", "|---|---:|---:|",
    ]
    for domain in domains:
        code = domain["code"]
        header.append(f"| [{code} · {domain['name']}]({code}.md) | {domain['single']} | {domain['composite']} |")
        rows = [f"# {code} · {domain['name']}", "", "[返回题目目录](README.md)", ""]
        for task in (t for t in tasks if t["domain"] == code):
            task_id = task["id"]
            rubric = rubrics[task_id]
            rows += [
                f"## {task_id}", "", f"**{task['title']}**", "",
                f"{DIFFICULTY[task['difficulty']]} · 梯度 {task['progression']} · {ORIGIN[task['origin']]} · "
                f"{', '.join(task['profiles'])} · {GRADING[task['grading']]}", "",
            ]
            if task["data_variant"] == "synthetic_replacement":
                rows += ["公开版合成输入。", ""]
            if task["noncommercial_data"]:
                rows += ["涉及 Earth-Bench-V2 数据，适用 CC BY-NC 4.0。", ""]
            rendered = prompt_for(task, task.get("original_prompt", ""), preview=True).split("\n", 2)[2]
            rows += ["<details>", "<summary>提示词与提交合同</summary>", "",
                     rendered.replace("\n## ", "\n#### "), "</details>", "", "<details>",
                     "<summary>评分、来源与版本</summary>", ""]
            rows += [f"- {c['points']} 分 · {c['requirement']}" for c in rubric["criteria"]]
            rows += [""]
            for src in task["source_records"]:
                rows.append(f"- [{src['name']}]({source_link(src)}) · {src['source_locator']} · {src['revision']}")
            if rubric.get("reference_path"):
                rows.append(f"- [参考值](../../{rubric['reference_path']})")
            rows += ["", "</details>", ""]
        write(folder / f"{code}.md", "\n".join(rows))
    write(folder / "README.md", "\n".join(header))


def browser_catalog(tasks, domains, rubrics):
    source_rows = [{
        "id": t["id"], "title": t["title"], "goal": t["goal"], "domain": t["domain"],
        "difficulty": t["difficulty"], "origin": t["origin"], "progression": t["progression"],
        "profiles": t["profiles"], "noncommercial": t["noncommercial_data"],
        "replacement": t["data_variant"] == "synthetic_replacement",
        "grading": GRADING[t["grading"]], "stages": t["stages"],
        "prompt": prompt_for(t, t.get("original_prompt", ""), preview=True),
        "sources": [
            {"name": s["name"], "locator": s["source_locator"], "url": source_link(s) if s.get("url") else "../geoagent_bench/fixtures.py",
             "revision": s["revision"]} for s in t["source_records"]
        ],
        "criteria": rubrics[t["id"]]["criteria"],
    } for t in tasks]
    options = "".join(f"<option value='{d['code']}'>{d['code']} · {html.escape(d['name'])}</option>" for d in domains)
    data = json.dumps(source_rows, ensure_ascii=False).replace("<", "\\u003c")
    write(ROOT / "docs/catalog.html", HTML.replace("__DOMAINS__", options).replace("__TASKS__", data))


HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GeoAgent-Bench · 200 道题</title>
<style>
:root{color-scheme:light;--ink:#132421;--muted:#507069;--line:#cbdad6;--brand:#155e50}
*{box-sizing:border-box}
body{margin:0;background:#f4f8f7;color:var(--ink);font:16px/1.6 system-ui,"Microsoft YaHei",sans-serif}
main{max-width:1080px;padding:40px 24px 64px;margin:auto}
h1{margin:.12em 0;font-size:clamp(30px,6vw,56px);line-height:1.15;letter-spacing:-.04em}
header{border-bottom:2px solid var(--brand);padding-bottom:22px;margin-bottom:24px}
nav{display:flex;gap:16px;flex-wrap:wrap}a{color:var(--brand)}
.bar{display:grid;gap:12px;grid-template-columns:2fr 1.4fr 1fr 1fr;margin-bottom:14px}
label{display:grid;gap:3px;font-size:.88em;color:var(--muted)}
input,select,button{background:#fff;border:1px solid var(--line);border-radius:6px;color:var(--ink);font:inherit;padding:8px}
button:not(:disabled),summary{cursor:pointer}button:disabled{opacity:.45}
.card{border:1px solid var(--line);border-radius:8px;background:#fff;margin:8px 0}
.card>summary{padding:13px 17px;font-weight:650}
.card div.content{padding:0 18px 18px;border-top:1px solid var(--line)}
small,.meta{color:var(--muted)}.product{letter-spacing:.12em;color:var(--brand);font-size:.8em;font-weight:750}
pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f4f8f7;border-radius:6px;padding:12px;font-size:.84em}
details details{margin-top:10px}ul{overflow-wrap:anywhere}
.pages{display:flex;gap:10px;align-items:center;margin-top:16px}
@media(max-width:720px){.bar{grid-template-columns:1fr 1fr}main{padding-left:14px;padding-right:14px}}
</style>
</head>
<body>
<main>
<header>
<div class="product">GIS &amp; MINERAL EXPLORATION AGENTS</div>
<h1>GeoAgent-Bench</h1>
<p>200 道题 · 170 道单任务 · 30 道复合任务 · 13 个地学领域</p>
<nav><a href="../README.md">仓库说明</a><a href="./ENVIRONMENT.md">环境</a><a href="./EVALUATION.md">评测</a><a href="../DATA_LICENSES.md">许可</a><a href="./tasks/README.md">Markdown 目录</a></nav>
</header>
<div class="bar">
<label>搜索<input id="query" type="search" placeholder="题号、任务或方法"></label>
<label>领域<select id="domain"><option value="">全部</option>__DOMAINS__</select></label>
<label>难度<select id="difficulty"><option value="">全部</option><option value="single">单任务</option><option value="composite">复合任务</option></select></label>
<label>题源<select id="origin"><option value="">全部</option><option value="public_original">公开原题</option><option value="adapted">改编题</option><option value="new">新增题</option></select></label>
</div>
<div id="count" class="meta" aria-live="polite"></div>
<section id="tasks" aria-label="题目"></section>
<div class="pages"><button id="prev">上一页</button><span id="page"></span><button id="next">下一页</button></div>
</main>
<script id="data" type="application/json">__TASKS__</script>
<script>
const $ = id => document.getElementById(id);
const tasks = JSON.parse($("data").textContent);
const labels = {public_original:"公开原题",adapted:"改编题",new:"新增题",single:"单任务",composite:"复合任务"};
const esc = s => String(s).replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;");
const size = 20;
let page=0;
function item(t) {
  const facts = [labels[t.difficulty], labels[t.origin], "梯度 "+t.progression, t.profiles.join(", "), t.grading];
  if(t.replacement) facts.push("合成输入");
  if(t.noncommercial) facts.push("CC BY-NC 数据");
  const sources = t.sources.map(s => '<li><a href="' + esc(s.url) + '">' + esc(s.name) + '</a> · ' + esc(s.locator) + ' · <code>' + esc(s.revision) + '</code></li>').join("");
  const criteria = t.criteria.map(c => "<li>"+c.points+" 分 · "+esc(c.requirement)+"</li>").join("");
  return "<details class='card'><summary>"+esc(t.id)+" · "+esc(t.title)+"</summary><div class='content'>"+
    "<p class='meta'>"+esc(facts.join(" · "))+"</p><p>"+esc(t.goal)+"</p>"+
    "<details><summary>提示词、输入和代码交付</summary><pre>"+esc(t.prompt)+"</pre></details>"+
    "<details><summary>评分标准</summary><ul>"+criteria+"</ul></details>"+
    "<details><summary>来源与版本</summary><ul>"+sources+"</ul></details></div></details>";
}
function render() {
  const query = $("query").value.toLowerCase().trim();
  const result = tasks.filter(t =>
    (!query || (t.id+" "+t.title+" "+t.goal).toLowerCase().includes(query)) &&
    ["domain","difficulty","origin"].every(k => !$(k).value || t[k] === $(k).value));
  const pages=Math.max(1,Math.ceil(result.length/size));
  page=Math.min(page,pages-1);
  $("count").textContent=result.length+" / "+tasks.length+" 道题";
  $("tasks").innerHTML=result.slice(page*size,(page+1)*size).map(item).join("") || "<p>没有匹配的题目。</p>";
  $("page").textContent=(page+1)+" / "+pages;
  $("prev").disabled=page===0;
  $("next").disabled=page+1===pages;
}
for(const id of ["query","domain","difficulty","origin"]) $(id).addEventListener("input",()=>{page=0;render();});
$("prev").onclick=()=>{page--;render();};
$("next").onclick=()=>{page++;render();};
render();
</script>
</body>
</html>"""


def main():
    tasks = all_tasks()
    domains = read_json(ROOT / "tasks/suite.json")["domains"]
    rubrics = {r["task_id"]: r for r in jsonl(ROOT / "evaluator/rubrics.jsonl")}
    markdown(tasks, domains, rubrics)
    browser_catalog(tasks, domains, rubrics)


if __name__ == "__main__":
    main()
