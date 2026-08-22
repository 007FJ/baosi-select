# -*- coding: utf-8 -*-
"""椴嶆柉閫夊瀷鏁版嵁鎵归噺鐢熸垚鍣?v2 (2026-08-20 闃插皝鍗囩骇鐗?
= 鍘?baosi_gen_probe.py + 妯℃嫙鐪熶汉鎿嶄綔 + 浠ｇ悊姹犺疆鎹?鏂板:
  --proxy <浠ｇ悊姹犳枃浠?   姣忚 ip:port, 鑷姩杞崲 (鍏嶈垂浠ｇ悊姹?
  --human               妯℃嫙鐪熶汉: 闅忔満闂撮殧/闅忔満闀挎殏鍋?浠诲姟鎵撲贡/cookie浼氳瘽/鍋跺皵娴忚椤甸潰
闃插皝璁捐 (2026-08-20 涓夋灏佺鍚庡畾鍨?:
  1. 闅忔満闂撮殧 2.5~6.5s (骞冲潎4.5s鈮?.22req/s, 浣庝簬瀹樼綉IP闄愭祦0.3req/s) 鏇夸唬鍥哄畾4s
  2. 姣?~50 璇锋眰鑷姩鎹唬鐞?(杞崲IP, 鍒嗘暎璐熻浇)
  3. 澶辫触閲嶈瘯鏃剁珛鍗虫崲浠ｇ悊 + 鎸囨暟閫€閬?  4. cookie jar 淇濇寔浼氳瘽 (鍚屾祻瑙堝櫒琛屼负)
  5. 5% 姒傜巼绌挎彃椤甸潰娴忚璇锋眰 (model.php 棣栭〉), 妯℃嫙鐪熶汉鎿嶄綔
  6. 浠诲姟椤哄簭鎵撲贡 (涓嶆寜鍨嬪彿杩炵画鍒?
璋冪敤: python baosi_gen_probe_human.py --models X --prog P --out O --proxy proxy_ok.txt --human
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

# ---------- 鍙傛暟瑙ｆ瀽 ----------
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

# ---------- 闃插皝鍏ㄥ眬 (2026-08-20) ----------
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
    """璇诲彇浠ｇ悊姹犳枃浠跺苟鎵撲贡"""
    global PROXY_LIST
    if not PROXY_FILE:
        return
    try:
        with open(PROXY_FILE, encoding='utf-8-sig') as f:
            PROXY_LIST = [l.strip() for l in f if l.strip() and l.strip()[0].isdigit()]
        random.shuffle(PROXY_LIST)
        log(f"浠ｇ悊姹犲姞杞? {len(PROXY_LIST)} 涓?(鏉ヨ嚜 {PROXY_FILE})")
    except Exception as e:
        log(f"浠ｇ悊姹犲姞杞藉け璐? {e}")

def next_proxy():
    """鍙栦笅涓€涓唬鐞?(椤哄簭杞崲, 鍙栨ā闃茶秺鐣?"""
    global PROXY_IDX
    if not PROXY_LIST:
        return None
    p = PROXY_LIST[PROXY_IDX % len(PROXY_LIST)]
    PROXY_IDX += 1
    return p

def browse_page():
    """妯℃嫙鐪熶汉娴忚: 鍋跺皵璁块棶閫夊瀷椤甸潰 (闈欓粯, 涓嶈蛋curl涓诲嚱鏁伴槻閫掑綊)"""
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
    """鍙戣捣璇锋眰: 闅忔満闂撮殧 + 浠ｇ悊杞崲 + cookie浼氳瘽 + 澶辫触鎹唬鐞嗛噸璇?(2026-08-20 闃插皝鍗囩骇)"""
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
    """鍘熷瓙鍐欒繘搴︽枃浠?(2026-08-18 瀹氬瀷)"""
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
    if d.get("msg") != "鎿嶄綔鎴愬姛":
        return None
    return d

def build_te_tc(te_min, te_max, tc_min, tc_max):
    te_min = int(float(te_min)); te_max = int(float(te_max))
    tc_min = int(float(tc_min)); tc_max = int(float(tc_max))
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
    if rng.get("zfwd_min") in ("鏃犳晥", None, ""):
        return None
    return rng

def probe_range_via_xnjs(cpid, ysjxh, zll, pql, fjpql, yll):
    """鎬ц兘琛ㄦ帰娴嬫湁鏁?Te/Tc 鑼冨洿 (BDL 鍙岀骇鏈虹瓑 wd_check 鏃犳晥鏃剁敤)"""
    j = curl(f"{BASE}/xnjs.php?cpid={urllib.parse.quote(cpid)}", {
        "zlj": zll, "pql": pql, "cpid": cpid, "ysjxh": ysjxh,
        "gjdy": "380V-3-50Hz", "rdzt": "100", "ytgld": "0", "xqgld": "10",
        "bp": "0", "fjpql": fjpql, "yll": yll, "dsj": "0",
    })
    if not j or "鎬ц兘琛? not in j:
        return None
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", j, re.S)
    if len(rows) < 6:
        return None
    hdr = re.sub(r"<[^>]+>", " ", rows[4])
    tes = [int(x) for x in re.findall(r"(-?\d+)鈩?, hdr)]
    valid_tcs = []
    for r in rows[5:]:
        txt = re.sub(r"<[^>]+>", " ", r)
        m = re.search(r"鍐峰嚌娓╁害:(-?\d+)鈩?, txt)
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
    log(f"浠诲姟鎬绘暟(鍨嬪彿x鍒跺喎鍓?: {tasks_total} (human={HUMAN} proxy={len(PROXY_LIST)})")

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
                    log(f"SKIP {mname} {refr}: 鏃犺寖鍥存暟鎹?)
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
            log(f"{'OK' if model_rows > 0 else 'FAIL-绌?} {mname} {refr}: {model_rows}鏉?(杩涘害 {tasks_done}/{tasks_total})")
            save_progress(progress)
            dump_result(result)

    save_progress(progress)
    dump_result(result)
    log(f"ALL DONE std={counts['std']} eco={counts['eco']} skip={counts['skip']} fail={counts['fail']}")

def dump_result(result):
    """鍐欏嚭 JS 鏁版嵁鏂囦欢; 鍘熷瓙鍐?+ 璇绘棫鏂囦欢鍚堝苟 (2026-08-19/20 瀹氬瀷)"""
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
        f.write("// 椴嶆柉铻烘潌鍘嬬缉鏈虹绾块€夊瀷鏁版嵁 (BSC 瀹樼綉閫夊瀷绯荤粺瀹樻柟API鐢熸垚 2026-08)\n")
        f.write("// 瀛楁: eco=0鏍囧噯/1缁忔祹鍣ㄥ畼鏂? freq=棰戠巼Hz(瀹氶50), cond_kW=鍐峰嚌鎺掔儹, eco_heat/eco_p/eco_t=缁忔祹鍣ㄥ弬鏁癨n")
        f.write("window.COMP_BAOSI = {\n" + ",\n".join(parts) + "\n};\n")
    os.replace(tmp, OUT)
    log(f"宸插啓鍑?{OUT} ({os.path.getsize(OUT)//1024}KB)")

if __name__ == "__main__":
    main()
