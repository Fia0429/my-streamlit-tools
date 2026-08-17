import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
import html
import time
import os
import subprocess
import platform
from io import BytesIO
from playwright.sync_api import sync_playwright

# -----------------------------------------------------------------------------
# 1. 页面基本配置
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="商家官网数据抓取与三阶梯解析工具",
    page_icon="🔍",
    layout="wide"
)

st.title("🛡️ 商家官网数据抓取与三阶梯降级解析工具 (含 CDP 真实浏览器接管)")
st.markdown("""
**工作流说明**：优先使用【传统 HTTP 爬虫】 -> 失败则自动切为【Playwright / CDP 接管浏览器】（实时监听 API 响应与动态 DOM） -> 再失败则使用【搜索引擎/转码服务】兜底。
""")

# -----------------------------------------------------------------------------
# 2. CDP Chrome 浏览器后台启动探测函数
# -----------------------------------------------------------------------------
def launch_chrome_debug(port=9222):
    """智能寻找本地 Chrome (优先桌面快捷方式 .lnk，次选标准安装路径 .exe) 并启动 CDP 调试模式"""
    system = platform.system()
    
    if system == "Windows":
        user_desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        public_desktop = r"C:\Users\Public\Desktop"
        
        # 按成功率从高到低排列候选路径
        candidate_paths = [
            # 1. 优先桌面快捷方式 (成功率最高，绕过 PATH 问题)
            os.path.join(user_desktop, "Google Chrome.lnk"),
            os.path.join(public_desktop, "Google Chrome.lnk"),
            # 2. Windows 常见标准安装路径
            os.path.expandvars(r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%PROGRAMFILES(X86)%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        ]
        
        for path in candidate_paths:
            if os.path.exists(path):
                try:
                    if path.endswith(".lnk"):
                        cmd = f'cmd.exe /c start "" "{path}" --remote-debugging-port={port} --user-data-dir="C:\\chrome_dev"'
                        subprocess.Popen(cmd, shell=True)
                    else:
                        cmd = [path, f"--remote-debugging-port={port}", r'--user-data-dir=C:\chrome_dev']
                        subprocess.Popen(cmd)
                    return True, path
                except Exception:
                    continue

    elif system == "Darwin":  # macOS
        mac_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        if os.path.exists(mac_path):
            try:
                cmd = [mac_path, f"--remote-debugging-port={port}", "--user-data-dir=/tmp/chrome_dev"]
                subprocess.Popen(cmd)
                return True, mac_path
            except Exception:
                pass

    return False, None

# -----------------------------------------------------------------------------
# 3. 数据清洗与特征提取工具函数
# -----------------------------------------------------------------------------
def clean_text(text, max_len=300):
    """清洗抓取到的网页文本（去乱码、多余换行、通用无用前缀，限制长度）"""
    if not text:
        return ""
    text = html.unescape(text)
    text = re.sub(r'[\r\n\t]+', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'^(首页|欢迎光临|官网|home)[_\-—\|]*', '', text, flags=re.IGNORECASE)
    
    if len(text) > max_len:
        text = text[:max_len] + "..."
    return text

def is_invalid_page(title, body_text):
    """检测页面是否属于 404/阻断/域名失效/安全验证页"""
    error_keywords = [
        "404 not found", "502 bad gateway", "500 internal",
        "access denied", "cloudflare", "403 forbidden", "just a moment...",
        "网站正在建设", "页面不存在", "just another wordpress site",
        "domain for sale", "域名出售", "buy this domain"
    ]
    combined = (str(title) + " " + str(body_text)).lower()
    return any(kw in combined for kw in error_keywords)

def extract_promo_info(text):
    """独立促销折扣扫描器：提取打折/优惠特征短句"""
    if not text:
        return "未检测到显性促销"
    
    patterns = [
        r'\b(?:\d{1,2}%|up to \d{1,2}%)\s*off\b',          # 20% OFF, Up to 50% OFF
        r'\bsave\s+(?:\$\d+|\d+%)\b',                     # Save $10, Save 20%
        r'\bbuy\s+\d+\s+get\s+\d+\b',                      # Buy 1 Get 1
        r'\bpromo\s*code[:\s]*[a-zA-Z0-9_-]+\b',           # Promo Code: XXX
        r'\b[1-9](?:\.[0-9])?\s*折\b',                     # 8折, 7.5折
        r'满\s*\d+\s*减\s*\d+',                            # 满100减20
        r'立减\s*\d+元?',                                  # 立减50元
        r'限时(?:特惠|折扣|优惠|促销)',                       # 限时特惠
    ]
    
    found = []
    for pat in patterns:
        matches = re.findall(pat, text, flags=re.IGNORECASE)
        for m in matches:
            item = m.strip() if isinstance(m, str) else m[0].strip()
            if item and item not in found:
                found.append(item)
    
    if not found:
        text_lower = text.lower()
        general_keywords = ['promotion', 'promo', 'discount', 'coupon', 'black friday', 'clearance', '大促', '领券', '特价']
        for kw in general_keywords:
            if kw in text_lower:
                found.append(f"包含促销词 '{kw}'")
                break
                
    if found:
        return " | ".join(found[:3])
    return "未检测到显性促销"

# -----------------------------------------------------------------------------
# 4. 三阶梯抓取核心函数 (Tier 1 -> Tier 2 [CDP/Headless] -> Tier 3)
# -----------------------------------------------------------------------------

def fetch_tier1_http(url_str):
    """【阶段 1】传统 HTTP 爬虫 (Requests)"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url_str, headers=headers, timeout=6, allow_redirects=True)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or "utf-8"
        
        soup = BeautifulSoup(response.text, "html.parser")
        title_raw = soup.title.string.strip() if soup.title and soup.title.string else ""
        body_text = soup.get_text(separator=' ')
        
        if title_raw and not is_invalid_page(title_raw, body_text):
            kw_tag = soup.find("meta", attrs={"name": lambda x: x and x.lower() == "keywords"})
            keywords_raw = kw_tag.get("content", "").strip() if kw_tag and kw_tag.get("content") else ""
            desc_tag = soup.find("meta", attrs={"name": lambda x: x and x.lower() == "description"})
            desc_raw = desc_tag.get("content", "").strip() if desc_tag and desc_tag.get("content") else ""
            
            return {
                "success": True,
                "title": clean_text(title_raw, 100),
                "keywords": clean_text(keywords_raw, 150),
                "description": clean_text(desc_raw, 200),
                "body_text": body_text
            }
    except Exception:
        pass
    return {"success": False}


def fetch_tier2_playwright(url_str, use_cdp=False, cdp_port=9222):
    """【阶段 2】Playwright 无头浏览器 / CDP 接管模式（含 API 响应监听）"""
    api_captured_texts = []

    # 网络响应监听器：捕捉异步 API 返回的数据
    def handle_response(response):
        try:
            if any(k in response.url.lower() for k in ["api", "json", "data", "get", "product"]):
                if response.status == 200:
                    text_data = response.text()
                    if len(text_data) > 30 and "{" in text_data:
                        api_captured_texts.append(text_data[:500])
        except Exception:
            pass

    try:
        with sync_playwright() as p:
            if use_cdp:
                # --- [新增模式 A]: 连接已启动调试端口的真实 Chrome 浏览器 ---
                browser = p.chromium.connect_over_cdp(f"http://localhost:{cdp_port}")
                context = browser.contexts[0]
                page = context.pages[0] if context.pages else context.new_page()
            else:
                # --- [原有模式 B]: 独立启动无头 Chrome ---
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
                page = context.new_page()

            # 注册监听器：必须在页面跳转前（goto）生效
            page.on("response", handle_response)

            # 页面访问与等待
            page.goto(url_str, timeout=12000, wait_until="domcontentloaded")
            time.sleep(1.5)  # 留给 JS 渲染和异步网络请求足够的时间

            content = page.content()
            title_raw = page.title()
            body_text = page.inner_text("body")

            # 额外合并通过网络监听捕获到的 API 异步文本
            if api_captured_texts:
                body_text += " " + " ".join(api_captured_texts)

            if not use_cdp:
                browser.close()

            if title_raw and not is_invalid_page(title_raw, body_text):
                soup = BeautifulSoup(content, "html.parser")
                kw_tag = soup.find("meta", attrs={"name": lambda x: x and x.lower() == "keywords"})
                keywords_raw = kw_tag.get("content", "").strip() if kw_tag and kw_tag.get("content") else ""
                desc_tag = soup.find("meta", attrs={"name": lambda x: x and x.lower() == "description"})
                desc_raw = desc_tag.get("content", "").strip() if desc_tag and desc_tag.get("content") else ""

                return {
                    "success": True,
                    "title": clean_text(title_raw, 100),
                    "keywords": clean_text(keywords_raw, 150),
                    "description": clean_text(desc_raw, 200),
                    "body_text": body_text
                }
    except Exception:
        pass
    return {"success": False}


def fetch_tier3_jina_reader(url_str):
    """【阶段 3】搜索引擎/Jina Reader 兜底（几乎不受本地防火墙限制）"""
    jina_url = f"https://r.jina.ai/{url_str}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"
    }
    try:
        response = requests.get(jina_url, headers=headers, timeout=10)
        if response.status_code == 200 and len(response.text) > 50:
            text = response.text
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            title = ""
            for l in lines[:5]:
                if l.startswith("Title:") or l.startswith("#"):
                    title = l.replace("Title:", "").replace("#", "").strip()
                    break
            if not title and lines:
                title = lines[0][:50]
                
            body_text = text[:3000]
            if not is_invalid_page(title, body_text):
                return {
                    "success": True,
                    "title": clean_text(title, 100),
                    "keywords": "",
                    "description": clean_text(body_text[:200], 200),
                    "body_text": body_text
                }
    except Exception:
        pass
    return {"success": False}


def fetch_with_three_tiers(url, use_cdp=False, cdp_port=9222):
    """调度入口：三阶梯降级调度函数"""
    if not url or pd.isna(url) or str(url).strip() == "":
        return {
            "source": "链接已失效",
            "crawled_summary": "网页链接失效/为空，需要人工校准",
            "promo_info": "网页链接失效"
        }

    url_str = str(url).strip()
    if not url_str.startswith(("http://", "https://")):
        url_str = "http://" + url_str

    # 1. 尝试 Tier 1: 传统 HTTP
    res_t1 = fetch_tier1_http(url_str)
    if res_t1["success"]:
        return format_result(res_t1, "网页爬虫得到")

    # 2. 尝试 Tier 2: Playwright 无头浏览器 / CDP 接管
    res_t2 = fetch_tier2_playwright(url_str, use_cdp=use_cdp, cdp_port=cdp_port)
    if res_t2["success"]:
        tag_name = "真实浏览器(CDP)得到" if use_cdp else "无头浏览器得到"
        return format_result(res_t2, tag_name)

    # 3. 尝试 Tier 3: 搜索引擎 / Jina 转换服务
    res_t3 = fetch_tier3_jina_reader(url_str)
    if res_t3["success"]:
        return format_result(res_t3, "搜索引擎/转码服务得到")

    # 全绝绝招失效后，归类为链接失效
    return {
        "source": "链接已失效",
        "crawled_summary": "网页链接失效/高强阻断，需要人工校准",
        "promo_info": "网页链接失效"
    }

def format_result(res_data, source_tag):
    """组装返回结果"""
    parts = []
    if res_data["title"]:
        parts.append(f"【标题】: {res_data['title']}")
    if res_data["keywords"]:
        parts.append(f"【关键词】: {res_data['keywords']}")
    if res_data["description"]:
        parts.append(f"【描述】: {res_data['description']}")

    crawled_summary = " | ".join(parts) if parts else "抓取成功，但未设置 Title/Meta 标签"
    promo_info = extract_promo_info(res_data["body_text"][:3000])

    return {
        "source": source_tag,
        "crawled_summary": crawled_summary,
        "promo_info": promo_info
    }

# -----------------------------------------------------------------------------
# 5. Streamlit 界面交互
# -----------------------------------------------------------------------------
st.sidebar.header("⚙️ 参数配置与列映射")

# --- 新增高级模式：CDP 调试开启与自动化管理 ---
st.sidebar.markdown("---")
use_cdp = st.sidebar.checkbox("开启真实 Chrome 接管模式 (CDP)", value=False)
cdp_port = 9222

if use_cdp:
    cdp_port = st.sidebar.number_input("CDP 调试端口", value=9222, step=1)
    
    # 智能自动化呼起按钮
    if st.sidebar.button("🌐 一键自动打开 Chrome", type="secondary"):
        success, launched_path = launch_chrome_debug(cdp_port)
        if success:
            st.sidebar.success(f"已成功呼起 Chrome！\n对应文件路径：\n`{launched_path}`")
        else:
            st.sidebar.warning("未能自动找到 Chrome 安装位置，请参考下方手工指令启动。")

    # 手工 fallback 启动说明
    desktop_lnk_path = os.path.join(os.path.expanduser("~"), "Desktop", "Google Chrome.lnk")
    with st.sidebar.expander("📖 手工启动说明（若未自动打开）", expanded=False):
        st.markdown(f"""
        **Windows 手工启动步骤：**
        1. 按 `Win + R` 键打开“运行”窗口（或打开 CMD 命令行）。
        2.找到chrome浏览器桌面快捷方式图标，右键复制文件地址
        2. 粘贴以下命令并按回车：
        ```cmd
        start "" "粘贴文件地址" --remote-debugging-port={cdp_port} --user-data-dir="C:\\chrome_dev"
        ```
        *(注：若图标名称不同，请将 `Google Chrome.lnk` 替换为你桌面上的快捷方式名称)*
        """)

st.sidebar.markdown("---")

uploaded_file = st.sidebar.file_uploader("上传商家数据表 (.xlsx / .csv)", type=["xlsx", "xls", "csv"])

if uploaded_file:
    try:
        df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith(".csv") else pd.read_excel(uploaded_file)
    except Exception as e:
        st.error(f"无法读取文件，错误信息: {e}")
        st.stop()

    st.subheader("📋 原始数据预览")
    st.dataframe(df.head(5), use_container_width=True)

    columns = df.columns.tolist()

    def get_default_idx(keywords, cols):
        for i, col in enumerate(cols):
            if any(k in str(col).lower() for k in keywords):
                return i
        return 0

    st.sidebar.subheader("设置绑定列")
    id_col = st.sidebar.selectbox("商家 ID 列", options=columns, index=get_default_idx(["id", "编号"], columns))
    name_col = st.sidebar.selectbox("商家名称列", options=columns, index=get_default_idx(["名称", "name", "商家"], columns))
    url_col = st.sidebar.selectbox("商家官网网址列", options=columns, index=get_default_idx(["网址", "url", "官网", "link"], columns))

    st.info(f"📍 当前映射：[ID -> **{id_col}**] | [名称 -> **{name_col}**] | [网址 -> **{url_col}**]")

    if st.button("🚀 开始执行三阶梯降级抓取", type="primary"):
        st.markdown("---")
        st.subheader("⚙️ 数据抓取执行中...")

        progress_bar = st.progress(0)
        status_text = st.empty()
        
        results = []
        total_rows = len(df)
        urls = df[url_col].tolist()
        
        start_time = time.time()
        
        for idx, url in enumerate(urls):
            status_text.text(f"正在处理第 [{idx+1}/{total_rows}] 条: {df.iloc[idx][name_col]} ({url}) ...")
            
            res = fetch_with_three_tiers(url, use_cdp=use_cdp, cdp_port=cdp_port)
            
            results.append({
                "商家ID": df.iloc[idx][id_col],
                "商家名称": df.iloc[idx][name_col],
                "商家官网网址": df.iloc[idx][url_col],
                "信息来源": res["source"],
                "爬虫特征摘要 (给大模型)": res["crawled_summary"],
                "促销/折扣信息 (业务列)": res["promo_info"]
            })
            
            progress_bar.progress((idx + 1) / total_rows)

        results_df = pd.DataFrame(results)
        end_time = time.time()

        st.success(f"🎉 全部商家数据处理完毕！总耗时: {round(end_time - start_time, 2)} 秒。")

        # 统计分析各阶梯命中情况
        source_counts = results_df["信息来源"].value_counts()
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Tier1 (普通爬虫)", source_counts.get("网页爬虫得到", 0))
        c2.metric("Tier2 (Playwright/CDP)", source_counts.get("无头浏览器得到", 0) + source_counts.get("真实浏览器(CDP)得到", 0))
        c3.metric("Tier3 (搜索引擎/转码)", source_counts.get("搜索引擎/转码服务得到", 0))
        c4.metric("失效/不可访问", source_counts.get("链接已失效", 0))

        st.subheader("📊 抓取与清洗结果展示")
        st.dataframe(
            results_df[["商家ID", "商家名称", "信息来源", "促销/折扣信息 (业务列)", "爬虫特征摘要 (给大模型)"]],
            use_container_width=True
        )

        # 导出 Excel Byte 流
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            results_df.to_excel(writer, index=False, sheet_name='三阶梯抓取结果')
        excel_data = output.getvalue()

        st.download_button(
            label="📥 下载处理结果表格 (.xlsx)",
            data=excel_data,
            file_name="商家官网三阶梯抓取清洗结果.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary"
        )
else:
    st.info("👈 请在左侧边栏上传你的商家 Excel / CSV 表格开始。")
