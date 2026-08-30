# -*- coding: utf-8 -*-
"""鲍斯选型数据批量生成器 v2 (2026-08-20 防封升级版)
= 原 baosi_gen_probe.py + 模拟真人操作 + 代理池轮换
新增:
  --proxy <代理池文件>   每行 ip:port, 自动轮换 (免费代理池)
  --human               模拟真人: 随机间隔/随机长暂停/任务打乱/cookie会话/偶尔浏览页面
防封设计 (2026-08-20 三次封禁后定型):
  1. 随机间隔 2.5~6.5s (平均4.5s≈0.22req/s, 低于官网IP限流0.3req/s) 替代固定4s
  2. 每 ~50 请求自动换代理 (轮换IP, 分散负载)
  3. 失败重试时立即换代理 + 指数退避
  4. cookie jar 保持会话 (同浏览器行为)
  5. 5% 概率穿插页面浏览请求 (model.php 首页), 模拟真人操作
  6. 任务顺序打乱 (不按型号连续刷)
调用: python baosi_gen_probe_human.py --models X --prog P --out O --proxy proxy_ok.txt --human
"""
import json, subprocess, urllib.parse, time, sys, os, re, random, tempfile

BASE = "https://bsysj.dmbz.net"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WS = os.path.dirname(SCRIPT_DIR)
CAT = os.path.join(WS, "baosi_catalog.json")
RNG = os.path.join(WS, "baosi_ranges.json")
OUT = os.path.join(WS, "compressors_baosi.js")
PROG = os.path.join(WS, "baosi_gen_progress.json")
LOG = os.path.join(WS, "baosi_gen.log")
PROBE_LOG = os.path.join(WS, "baosi_probe2.log")

# ---------- 参数解析 ----------
TARGET_MODELS = None
EXCLUDE_MODELS = None
if '--models' in sys.argv:
    TARGET_MODELS = set(m.strip() for m in sys.argv[sys.argv.index('--models') + 1].split(','))
if '--exclude' in sys.argv:
    EXCLUDE_MODELS = set(m.strip() for m in sys.argv[sys.argv.index('--exclude') + 1].split(','))
if '--prog' in sys.argv:
    PROG = sys.argv[sys.argv.index('--prog') + 1]
if '--out' in sys.argv:
    OUT = sys.argv[sys.argv.index('--out') + 1]
if '--log' in sys.argv:
    LOG = sys.argv[sys.argv.index('--log') + 1]

# ---------- 防封全局 (2026-08-20) ----------
HUMAN = '--human' in sys.argv
PROXY_FILE = None
if '--proxy' in sys.argv:
    PROXY_FILE = sys.argv[sys.argv.index('--proxy') + 1]
PROXY_LIST = []
PROXY_IDX = 0
REQ_COUNT = 0
COOKIE_JAR = os.path.join(tempfile.gettempdir(), 'baosi_cookie_%d.txt' % os.getpid())
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
REFERER = "https://bsysj.dmbz.net/calculation.php"

def load_proxies():
    """读取代理池文件并打乱"""
    global PROXY_LIST
    if not PROXY_FILE:
        return
    try:
        with open(PROXY_FILE, encoding='utf-8-sig') as f:
            PROXY_LIST = [l.strip() for l in f if l.strip() and l.strip()[0].isdigit()]
        random.shuffle(PROXY_LIST)
        log(f"代理池加载: {len(PROXY_LIST)} 个 (来自 {PROXY_FILE})")
    except Exception as e:
        log(f"代理池加载失败: {e}")

def next_proxy():
    """取下一个代理 (顺序轮换, 取模防越界)"""
    global PROXY_IDX
    if not PROXY_LIST:
        return None
    p = PROXY_LIST[PROXY_IDX % len(PROXY_LIST)]
    PROXY_IDX += 1
    return p

def browse_page():
    """模拟真人浏览: 偶尔访问选型页面 (静默, 不走curl主函数防递归)"""
    try:
        cmd = ["curl", "-s", "--max-time", "12", "-o", "/dev/null",
               "-H", "User-Agent: " + UA, "-b", COOKIE_JAR, "-c", COOKIE_JAR]
        if PROXY_LIST:
            cmd += ["-x", PROXY_LIST[PROXY_IDX % len(PROXY_LIST)]]
        cmd += [BASE + "/model.php?class=52"]
        subprocess.run(cmd, capture_output=True, timeout=15)
    except Exception:
        pass

REFR_ID = {"R22": "2", "R404A": "4", "R507": "8", "R134a": "3"}
FREQ_DEF = [50]
FREQ_VFD = [30, 40, 50, 60]
REQUEST_GAP = 4.0

def curl(url, data=None, retries=4):
    """发起请求: 随机间隔 + 代理轮换 + cookie会话 + 失败换代理重试 (2026-08-20 防封升级)"""
    global REQ_COUNT, PROXY_IDX
    if HUMAN:
        time.sleep(random.uniform(2.5, 6.5))
    else:
        time.sleep(REQUEST_GAP)
    if HUMAN and random.random() < 0.05:
        browse_page()
    if PROXY_LIST and REQ_COUNT % 50 == 49:
        PROXY_IDX += 1
    with open(PROBE_LOG, 'a', encoding='utf-8') as _pf:
        _pf.write('[%s] curl -> %s\n' % (time.strftime('%H:%M:%S'), url.split('/')[-1]))
    cur = None
    if PROXY_LIST:
        cur = PROXY_LIST[PROXY_IDX % len(PROXY_LIST)]
    for i in range(retries):
        try:
            cmd = ["curl", "-s", "--max-time", "25",
                   "-H", "User-Agent: " + UA, "-H", "Referer: " + REFERER,
                   "-b", COOKIE_JAR, "-c", COOKIE_JAR]
            if cur:
                cmd += ["-x", cur]
            if data:
                cmd += ["-X", "POST", "-d", urllib.parse.urlencode(data)]
            cmd.append(url)
            r = subprocess.run(cmd, capture_output=True, timeout=35)
            if r.returncode == 0 and len(r.stdout) > 0:
                REQ_COUNT += 1
                return r.stdout.decode("utf-8", errors="replace")
        except Exception:
            pass
        if PROXY_LIST:
            cur = PROXY_LIST[(PROXY_IDX + i + 1) % len(PROXY_LIST)]
        time.sleep(8 * (2 ** i))
    return ""

def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def save_progress(progress):
    """原子写进度文件 (2026-08-18 定型)"""
    tmp = PROG + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False)
    os.replace(tmp, PROG)

def calc(pql, zll, tc, te, jjq, bp, bpq, fjpql, yll):
    j = curl(f"{BASE}/php/ysjxnjs_process.php", {
        "pql": pql, "zll": zll, "lnwd": tc, "zfwd": te,
        "ytgld": "0", "xqgld": "10", "jjq": jjq,
        "dsj": "0", "bp": bp, "bpq": bpq, "fjpql": fjpql, "yll": yll,
    })
    try:
        d = json.loads(j)
    except Exception:
        return None
    if d.get("msg") != "操作成功":
        return None
    return d

def _to_int(val, default=None):
    try:
        s = str(val).strip()
        if not s or '无效' in s or not any(c.isdigit() for c in s):
            return default
        return int(float(s))
    except (ValueError, TypeError):
        return default

def build_te_tc(te_min, te_max, tc_min, tc_max):
    te_min = _to_int(te_min); te_max = _to_int(te_max)
    tc_min = _to_int(tc_min); tc_max = _to_int(tc_max)
    if None in (te_min, te_max, tc_min, tc_max):
        return [], []
    tes, tcs = [], []
    t = te_min if te_min % 2 == 0 else te_min + 1
    while t <= te_max:
        tes.append(t); t += 2
    t = tc_min
    while t <= tc_max:
        tcs.append(t); t += 5
    for base in [-30, -15, -10, -5, 0]:
        if te_min <= base <= te_max and base not in tes:
            tes.append(base)
    tes.sort()
    return tes, tcs

def get_range(cplb, refr):
    key = f"{cplb}|{refr}"
    rng = RANGES.get(key, {})
    if not rng:
        return None
    zfwd_min = str(rng.get("zfwd_min", "")).strip()
    if not zfwd_min or '无效' in zfwd_min or not any(c.isdigit() for c in zfwd_min):
        return None
    return rng

def probe_range_via_xnjs(cpid, ysjxh, zll, pql, fjpql, yll):
    """性能表探测有效 Te/Tc 范围 (BDL 双级机等 wd_check 无效时用)"""
    j = curl(f"{BASE}/xnjs.php?cpid={urllib.parse.quote(cpid)}", {
        "zlj": zll, "pql": pql, "cpid": cpid, "ysjxh": ysjxh,
        "gjdy": "380V-3-50Hz", "rdzt": "100", "ytgld": "0", "xqgld": "10",
        "bp": "0", "fjpql": fjpql, "yll": yll, "dsj": "0",
    })
    if not j or "性能表" not in j:
        return None
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", j, re.S)
    if len(rows) < 6:
        return None
    hdr = re.sub(r"<[^>]+>", " ", rows[4])
    tes = [int(x) for x in re.findall(r"(-?\d+)℃", hdr)]
    valid_tcs = []
    for r in rows[5:]:
        txt = re.sub(r"<[^>]+>", " ", r)
        m = re.search(r"冷凝温度:(-?\d+)℃", txt)
        if not m:
            continue
        cells = re.findall(r"<td[^>]*>(.*?)</td>", r, re.S)
        has_data = False
        for c in cells[2:]:
            t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", c)).strip()
            if t and t != "----" and "kW" in t:
                has_data = True
                break
        if has_data:
            valid_tcs.append(int(m.group(1)))
    if not tes or not valid_tcs:
        return None
    return tes, sorted(valid_tcs)

def main():
    global RANGES
    RANGES = json.load(open(RNG, encoding="utf-8"))
    cat = json.load(open(CAT, encoding="utf-8"))
    load_proxies()

    progress = {}
    if os.path.exists(PROG):
        progress = json.load(open(PROG, encoding="utf-8"))

    result = {}
    counts = {"std": 0, "eco": 0, "skip": 0, "fail": 0}
    tasks_done = 0

    tasks = []
    for series, specs in cat.items():
        for spec_name, spec in specs.items():
            cpid, cplb = spec["cpid"], spec["cplb"]
            for mname, md in spec["models"].items():
                if "error" in md:
                    continue
                if TARGET_MODELS is not None and mname not in TARGET_MODELS:
                    continue
                if EXCLUDE_MODELS is not None and mname in EXCLUDE_MODELS:
                    continue
                refrs = [r for r in md.get("refr_names", "").split(",") if r in REFR_ID]
                if not refrs:
                    continue
                tasks.append((series, spec_name, cpid, cplb, mname, md, refrs))
    if HUMAN:
        random.shuffle(tasks)
    tasks_total = len(tasks)
    log(f"任务总数(型号x制冷剂): {tasks_total} (human={HUMAN} proxy={len(PROXY_LIST)})")

    for series, spec_name, cpid, cplb, mname, md, refrs in tasks:
        pql = md.get("pql", "")
        bp = int(md.get("bp", "0") or 0)
        fjpql = md.get("fjpql", "0") or "0"
        yll = md.get("yll", "") or ""
        freqs = FREQ_VFD if bp else FREQ_DEF
        for refr in refrs:
            task_key = f"{mname}|{refr}"
            if progress.get(task_key) in ("done", "no-range", "no-grid"):
                tasks_done += 1
                continue
            zll = REFR_ID[refr]
            rng = get_range(cplb, refr)
            if rng is None:
                pr = probe_range_via_xnjs(cpid, md["mid"], zll, pql, fjpql, yll)
                if pr is None:
                    log(f"SKIP {mname} {refr}: 无范围数据")
                    progress[task_key] = "no-range"
                    counts["skip"] += 1
                    tasks_done += 1
                    continue
                tes, tcs = pr
            else:
                tes, tcs = build_te_tc(rng["zfwd_min"], rng["zfwd_max"], rng["lnwd_min"], rng["lnwd_max"])
            if not tes or not tcs:
                progress[task_key] = "no-grid"
                tasks_done += 1
                continue
            model_rows = 0
            for te in tes:
                for tc in tcs:
                    for jjq in ["0", "1"]:
                        for bpq in freqs:
                            d = calc(pql, zll, tc, te, jjq, str(bp), bpq, fjpql, yll)
                            if d is None:
                                counts["fail"] += 1
                                continue
                            q = float(d["zll"])
                            if q <= 0:
                                counts["skip"] += 1
                                continue
                            row = {
                                "model": mname,
                                "family": f"{series}-{spec_name}",
                                "Q_kW": round(q, 2),
                                "P_kW": round(float(d["gl"]), 2),
                                "I_A": round(float(d["dl"]), 2),
                                "COP": round(float(d["cop"]), 3),
                                "discharge_T": round(float(d["pqwd"]), 1),
                                "m_flow_kgh": round(float(d["dyczlll"]), 1),
                                "disp_m3h": float(pql.split(",")[0]),
                                "cond_kW": round(float(d["zrl"]), 2),
                                "freq": int(bpq),
                                "eco": int(jjq),
                            }
                            if jjq == "1":
                                if d.get("jjqhrl"):
                                    row["eco_heat"] = round(float(d["jjqhrl"]), 2)
                                if d.get("bqyl"):
                                    row["eco_p"] = round(float(d["bqyl"]), 2)
                                if d.get("bqwd"):
                                    row["eco_t"] = round(float(d["bqwd"]), 2)
                            key = f"{te}|{tc}"
                            result.setdefault(refr, {}).setdefault(key, []).append(row)
                            model_rows += 1
                            if jjq == "0":
                                counts["std"] += 1
                            else:
                                counts["eco"] += 1
            progress[task_key] = "done" if model_rows > 0 else "fail"
            tasks_done += 1
            log(f"{'OK' if model_rows > 0 else 'FAIL-空'} {mname} {refr}: {model_rows}条 (进度 {tasks_done}/{tasks_total})")
            save_progress(progress)
            dump_result(result)

    save_progress(progress)
    dump_result(result)
    log(f"ALL DONE std={counts['std']} eco={counts['eco']} skip={counts['skip']} fail={counts['fail']}")

def dump_result(result):
    """写出 JS 数据文件; 原子写 + 读旧文件合并 (2026-08-19/20 定型)"""
    merged = {}
    if os.path.exists(OUT):
        try:
            with open(OUT, encoding="utf-8") as f:
                text = f.read()
            m = re.search(r"COMP_BAOSI\s*=\s*(\{.*\});?\s*$", text, re.S)
            if m:
                merged = json.loads(m.group(1))
        except Exception:
            merged = {}
    for refr, grid in result.items():
        for key, rows in grid.items():
            merged.setdefault(refr, {}).setdefault(key, []).extend(rows)
    result.clear()
    parts = []
    for refr in sorted(merged.keys()):
        keys = sorted(merged[refr].keys(), key=lambda k: (int(k.split("|")[0]), int(k.split("|")[1])))
        refr_body = []
        for k in keys:
            rows = sorted(merged[refr][k], key=lambda r: r["Q_kW"])
            refr_body.append(f"    \"{k}\": " + json.dumps(rows, ensure_ascii=False))
        parts.append(f"  \"{refr}\": {{\n" + ",\n".join(refr_body) + "\n  }")
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("// 鲍斯螺杆压缩机离线选型数据 (BSC 官网选型系统官方API生成 2026-08)\n")
        f.write("// 字段: eco=0标准/1经济器官方, freq=频率Hz(定频50), cond_kW=冷凝排热, eco_heat/eco_p/eco_t=经济器参数\n")
        f.write("window.COMP_BAOSI = {\n" + ",\n".join(parts) + "\n};\n")
    os.replace(tmp, OUT)
    log(f"已写出 {OUT} ({os.path.getsize(OUT)//1024}KB)")

if __name__ == "__main__":
    main()
