import os
import pandas as pd
import streamlit as st

# ==========================================
# 1. 页面基础配置
# ==========================================
st.set_page_config(
    page_title="商家联盟转化与风控防查计算器",
    page_icon="🛡️",
    layout="wide"
)

st.title("🛡️ 商家联盟转化与风控防查计算器 (V3.1)")
st.caption("基于流量漏斗推算 + 商家 AM 人工审查防查阈值（Stealth Safety Cap）评估")
st.markdown("---")

# ==========================================
# 1. 联盟 Excel 动态读取函数 (全环境自适应版)
# ==========================================
@st.cache_data
def load_yp_mapping_table(affiliate_name):
    """
    极速读取本地/云端 YP 商家 ID 映射表 (自动识别 pages 子目录与根目录)
    """
    affiliate_clean = str(affiliate_name).strip()
    
    # 💡 自动智能寻找真实的 data/ 文件夹位置
    current_file_dir = os.path.dirname(os.path.abspath(__file__))
    possible_data_dirs = [
        os.path.join(current_file_dir, "data"),                      # 情况 1：在当前文件所在目录
        os.path.join(os.path.dirname(current_file_dir), "data"),     # 情况 2：在上一级目录（针对 pages/ 内的文件）
        os.path.join(os.getcwd(), "data")                            # 情况 3：在当前 Python 工作目录
    ]
    
    DATA_DIR = None
    for d_path in possible_data_dirs:
        if os.path.exists(d_path) and os.path.isdir(d_path):
            DATA_DIR = d_path
            break
            
    if not DATA_DIR:
        st.error(f"❌ 找不到 `data` 文件夹！尝试排查的路径列表：{possible_data_dirs}")
        return None

    # 字典统一管理文件名 (请核对你的文件真实文件名与大小写)
    file_path_map = {
        "Tradedoubler": os.path.join(DATA_DIR, "YP-TD.xlsx"),
        "Flexoffers": os.path.join(DATA_DIR, "YP-FO.xlsx"),
        "Impact": os.path.join(DATA_DIR, "YP-IMP.xlsx"),
        "Adpump": os.path.join(DATA_DIR, "YP-Adpump.xlsx"),
        "Ascend(partnerize)": os.path.join(DATA_DIR, "YP-Ascend(partnerize).xlsx"),
        "Linkbux": os.path.join(DATA_DIR, "YP-Linkbux.xlsx"),
        "Rakuten": os.path.join(DATA_DIR, "YP-Rakuten.xlsx"),
        "WebgainsY": os.path.join(DATA_DIR, "YP-WebgainsY.xlsx"),
        "Partnerize": os.path.join(DATA_DIR, "YP-Partnerize.xlsx"),
        "Linkhaitao": os.path.join(DATA_DIR, "YP-Linkhaitao.xlsx"),
        "Shopnomix": os.path.join(DATA_DIR, "YP-Shopnomix.xlsx"),
        "Partnermatic": os.path.join(DATA_DIR, "YP-Partnermatic.xlsx"),
        "InvolveAsia-Y": os.path.join(DATA_DIR, "YP-InvolveAsia-Y.xlsx")
    }
    
    target_path = file_path_map.get(affiliate_clean)

    if target_path and os.path.exists(target_path):
        try:
            # 读取前两列
            df_map = pd.read_excel(target_path, usecols=[0, 1])
            df_map.columns = ["商家ID", "商家名称"]
            
            # 转字符串并去空格
            df_map["商家ID"] = df_map["商家ID"].astype(str).str.strip()
            df_map["商家名称"] = df_map["商家名称"].astype(str).str.strip()
            
            return df_map.drop_duplicates(subset=["商家名称"])
        except Exception as e:
            st.error(f"⚠️ 找到表格但读取失败 [{os.path.basename(target_path)}]: {e}")
            return None
    else:
        # 如果文件不存在，输出明确的路径提示
        st.warning(f"⚠️ 在 `{DATA_DIR}` 目录下未找到目标文件：`{os.path.basename(target_path) if target_path else affiliate_clean}`")
        return None
# ==========================================
# 行业 CVR 数据库：[最低底线, 建议默认值, 行业上限]
# ==========================================
CATEGORY_CVR_INFO = {
    "旅游票务 / 景点体验": {"min": 1.0, "default": 1.0, "max": 2.5},
    "快消食品 / 饮料": {"min": 1.5, "default": 2.5, "max": 4.0},
    "美妆个护 / 护肤彩妆": {"min": 1.5, "default": 2.2, "max": 3.8},
    "服装鞋帽 / 时尚饰品": {"min": 1.2, "default": 1.8, "max": 3.0},
    "3C数码 / 家电配件": {"min": 0.8, "default": 1.2, "max": 2.2},
    "母婴用品 / 儿童玩具": {"min": 1.5, "default": 2.0, "max": 3.5},
    "家居百货 / 软装日用": {"min": 1.2, "default": 2.0, "max": 3.2},
    "健康保健 / 膳食营养": {"min": 1.8, "default": 2.5, "max": 4.5},
    "宠物用品 / 宠物食品": {"min": 2.0, "default": 2.8, "max": 4.5},
    "奢侈品 / 高端珠宝": {"min": 0.5, "default": 0.8, "max": 1.5},
    "综合平台 / 大型卖场": {"min": 2.0, "default": 3.5, "max": 5.0},
    "自定义品类": {"min": 0.5, "default": 1.5, "max": 3.0}
}

# ==========================================
# 2. 模块 1：商家与联盟选择 (对接动态映射函数)
# ==========================================
st.header("1. 商家与联盟选择（可选）")

col_a1, col_a2 = st.columns(2)

with col_a1:
    selected_alliance = st.selectbox("选择所属联盟：", options=["-- 跳过选择 --"] + ALLIANCE_LIST)

# 初始化变量
selected_merchant_name = ""
selected_merchant_id = ""

if selected_alliance != "-- 跳过选择 --":
    # 调用缓存函数加载表格
    df_alliance = load_yp_mapping_table(selected_alliance)
    
    if df_alliance is not None and not df_alliance.empty:
        with col_a2:
            search_kw = st.text_input("🔍 搜索商家名称或 ID：", placeholder="输入关键词筛选，例如: Capalus 或 1001...")
        
        if search_kw.strip():
            kw = search_kw.strip().lower()
            # 针对 商家名称 和 商家ID 同时进行不区分大小写的模糊匹配
            mask = (
                df_alliance["商家名称"].str.lower().str.contains(kw) | 
                df_alliance["商家ID"].str.lower().str.contains(kw)
            )
            filtered_df = df_alliance[mask]
            
            if not filtered_df.empty:
                # 构造下拉选项："名称 | ID: 编号"
                options_list = [
                    f"{row['商家名称']} | ID: {row['商家ID']}" 
                    for _, row in filtered_df.iterrows()
                ]
                
                chosen_option = st.selectbox(f"🎯 找到 {len(filtered_df)} 个匹配结果，请选择：", options=options_list)
                
                # 自动提取名称与 ID
                if chosen_option:
                    split_vals = chosen_option.split(" | ID: ")
                    selected_merchant_name = split_vals[0]
                    selected_merchant_id = split_vals[1] if len(split_vals) > 1 else ""
            else:
                st.warning("⚠️ 未找到匹配的商家，请检查关键字或手动输入。")
    else:
        with col_a2:
            st.info("💡 未能加载该联盟的表格，请确认表格文件已上传至 `data/` 目录。")

# 确认/手动修正商家信息
st.markdown("##### 📌 确认商家信息")
col_m1, col_m2 = st.columns(2)

merchant_name = col_m1.text_input(
    "商家名称 (Merchant Name)：", 
    value=selected_merchant_name, 
    placeholder="匹配后自动显示，也可直接手动填写"
)

merchant_id = col_m2.text_input(
    "商家 ID (Merchant ID)：", 
    value=selected_merchant_id, 
    placeholder="匹配后自动显示，也可直接手动填写"
)

st.markdown("---")


# ==========================================
# 3. 模块 2：基础数据与商业参数（优化布局版）
# ==========================================
st.header("2. 基础数据与商业参数")

# --- 子区块 1：商家流量大盘（核心） ---
st.subheader("📊 商家大盘流量")
col_f1, col_f2, col_f3 = st.columns(3)

with col_f1:
    visits_input = st.number_input(
        "Month Visits：",
        min_value=0,
        value=None,
        step=1000000,
        placeholder="输入SimilarWeb查到的Month Visits，如: 60000000",
        help= "访问量不等于点击量，不能直接用于计算"
    )
with col_f2:
    visit_discount_input = st.number_input(
        "到站折损系数：",
        min_value=0.1,
        max_value=1.0,
        value=0.8,
        step=0.05,
        help="将访问量转化为点击量，运营建议系数为 0.8"
    )
with col_f3:
    affiliate_share_input = st.number_input(
        "联盟流量占总体流量百分比 (%)：",
        min_value=0.0,
        max_value=100.0,
        value=None,
        step=0.5,
        placeholder="输入Traffic Sources中Affiliate部分占比，如: 26.0",
        help= "网站流量来源有很多，独立站只看联盟部分，若有需要可更换成其他类型"
    )

st.markdown(" ") # 增加小间距

# --- 子区块 2：品类与转化率基准（包含动态媒体提示） ---
st.subheader("🎯 行业与转化基准")
col_c1, col_c2 = st.columns(2)

with col_c1:
    selected_cat = st.selectbox("选择行业品类：", options=list(CATEGORY_CVR_INFO.keys()), index=0)

# 获取选中品类的区间信息
cat_data = CATEGORY_CVR_INFO[selected_cat]

with col_c2:
    cvr_input = st.number_input(
        "品类大盘 CVR (%)：",
        min_value=0.01,
        max_value=100.0,
        value=float(cat_data["default"]),
        step=0.1,
        help="系统已自动载入该行业底线 CVR，也可手动微调"
    )

# 简化品类名称（用于提示词中优雅展示）
clean_cat_name = selected_cat.split(" / ")[0]

# 动态生成的媒体提示词
st.caption(
    f"💡 **媒体复核提示**：【**{clean_cat_name}**】类商家大盘 CVR 通常在 **{cat_data['min']}% ~ {cat_data['max']}%** 之间。"
    f"为防止单数推算过高，建议优先参考**行业底线值 ({cat_data['min']}%)**；当前计算实际采用 CVR：**{cvr_input:.2f}%**。"
)

st.markdown(" ") # 增加小间距

# --- 子区块 3：我们渠道与商业收益 ---
st.subheader("💰 我们渠道与收益预估")
col_o1, col_o2, col_o3 = st.columns(3)

with col_o1:
    our_share_input = st.number_input(
        "设定我们计划占联盟的比例 (%)：",
        min_value=0.0,
        max_value=100.0,
        value=None,
        step=0.5,
        placeholder="输入计划占比，如: 1.0",
        help="查到的是总流量，需要估计我们YP渠道在其中的占比。\n运营端建议保守估计为5%，如果该商家做得特别好，最高不超过10%"
    )
with col_o2:
    aov_input = st.number_input(
        "预估平均客单价 AOV ($)：",
        min_value=0.0,
        value=None,
        step=10.0,
        placeholder="输入客单价，如: 80.0",
        help="根据聚合报表or数据明细可以进行预估。\n此项可不填，不填则只有预计单数，无预计佣金"
    )
with col_o3:
    commission_rate_input = st.number_input(
        "联盟平均佣金率 (%)：",
        min_value=0.0,
        value=None,
        step=0.5,
        placeholder="输入ALL佣金率，如: 6.0",
        help="由于同一商家不同产品佣金率可能不同，建议使用数据明细中的平均佣金率，而非前台展示all佣金率"
    )

st.markdown("---")

# ==========================================
# 4. 安全防护解析与核心计算
# ==========================================
# 转换输入，为空时安全降级为 0
visits = visits_input if visits_input is not None else 0
visit_discount = visit_discount_input if visit_discount_input is not None else 0.8
cvr = cvr_input if cvr_input is not None else 0.0
affiliate_share = affiliate_share_input if affiliate_share_input is not None else 0.0
our_share = our_share_input if our_share_input is not None else 0.0
aov = aov_input if aov_input is not None else 0.0
commission_rate = commission_rate_input if commission_rate_input is not None else 0.0

# 只有当用户输入了核心数据才展示结果
if visits > 0 and affiliate_share > 0:
    # 1. 大盘基本面计算
    real_visits = visits * visit_discount
    total_affiliate_orders = real_visits * (affiliate_share / 100.0) * (cvr / 100.0)
    target_our_orders = total_affiliate_orders * (our_share / 100.0)
    target_payout = target_our_orders * aov * (commission_rate / 100.0)

    # 2. 风控安全线推算 (Stealth Safety Model)
    if visits >= 10000000:
        safe_share_cap = 0.3  # 千万级大商家隐身上限 0.3%
        max_safe_orders_hard = 250
    elif visits >= 1000000:
        safe_share_cap = 1.0
        max_safe_orders_hard = 150
    else:
        safe_share_cap = 3.0
        max_safe_orders_hard = 80

    stealth_safe_orders = min(total_affiliate_orders * (safe_share_cap / 100.0), max_safe_orders_hard)
    stealth_safe_payout = stealth_safe_orders * aov * (commission_rate / 100.0)

    # 3. 风险等级评估
    risk_score = 0
    risk_reasons = []

    if target_our_orders > stealth_safe_orders:
        risk_score += 2
        risk_reasons.append(f"<b>单数过高</b>：设定单数 ({target_our_orders:.0f}单) 超过防查安全线 ({stealth_safe_orders:.0f}单)，容易进入 AM 出单前排榜单。")

    if target_payout > 3000:
        risk_score += 1
        risk_reasons.append(f"<b>金额过高</b>：预估月佣金 (${target_payout:,.0f}) 超过平台 $3,000 财务人工审核触发线。")

    if our_share > 1.0 and visits >= 10000000:
        risk_score += 1
        risk_reasons.append(f"<b>大商家占比过高</b>：在千万级流量大厂占 1% 以上必触发 AM 重点排查。")

    # ==========================================
    # 5. 结果面板展示
    # ==========================================
    st.header("3. 风控评估与安全推算结果")

    res_col1, res_col2, res_col3, res_col4 = st.columns(4)

    res_col1.metric("联盟预估总单数", f"{total_affiliate_orders:,.0f} 单")
    res_col2.metric("设定占比预计单数", f"{target_our_orders:,.2f} 单", delta=f"佣金 ≈ ${target_payout:,.0f}" if aov > 0 else None)

    res_col3.metric(
        "🛡️ 建议防查安全上限", 
        f"{stealth_safe_orders:.0f} 单/月", 
        delta=f"安全预估佣金 ≈ ${stealth_safe_payout:,.0f}" if aov > 0 else None,
        delta_color="normal"
    )

    if risk_score >= 3:
        res_col4.error("🔴 极高风险 (高概率被封/查)")
    elif risk_score >= 1:
        res_col4.warning("🟡 中度风险 (建议缩减单量)")
    else:
        res_col4.success("🟢 低风险 (处于防查隐身区)")

    st.subheader("💡 商家 AM 审查风险诊断分析")

    if risk_reasons:
        for reason in risk_reasons:
            st.markdown(f"- ⚠️ {reason}", unsafe_allow_html=True)
    else:
        st.markdown("- ✅ 当前设定的单数和佣金处于安全隐身区间（Under the Radar），不易触发商家 AM 审查。")

    st.markdown(" ")

    st.subheader("📋 详细推算对比表")
    safe_share_pct = (stealth_safe_orders / total_affiliate_orders * 100) if total_affiliate_orders > 0 else 0
    df_summary = pd.DataFrame([
        {"指标维度": "1. 真实有效 Visits (×0.8)", "设定模式数值": f"{int(real_visits):,}", "防查隐身模式建议": f"{int(real_visits):,}"},
        {"指标维度": "2. 联盟预估总单数", "设定模式数值": f"{total_affiliate_orders:,.0f} 单", "防查隐身模式建议": f"{total_affiliate_orders:,.0f} 单"},
        {"指标维度": "3. 我们渠道所占比例", "设定模式数值": f"{our_share:.2f}%", "防查隐身模式建议": f"建议控制在 {safe_share_pct:.2f}% 以内"},
        {"指标维度": "4. 最终月度单数 (Orders)", "设定模式数值": f"{target_our_orders:,.1f} 单", "防查隐身模式建议": f"🎯 {stealth_safe_orders:.0f} 单 (隐身安全区)"},
        {"指标维度": "5. 月度预估佣金 (Payout)", "设定模式数值": f"${target_payout:,.2f}", "防查隐身模式建议": f"${stealth_safe_payout:,.2f}"}
    ])
    st.table(df_summary)

else:
    st.info("👈 请在上方输入框填入商家的 **Visits 点击量** 和 **联盟占比**，即可自动生成分析面板。")
