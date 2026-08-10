import os
from datetime import datetime, date
import pandas as pd
import streamlit as st

# ==================== 页面基础设置 ====================
st.set_page_config(
    page_title="联盟流量风控自动筛查工具",
    page_icon="🛡️",
    layout="wide"
)

# 智能表头别名库（保持原业务逻辑）
COLUMN_MAPPING = {
    "商家名称": ["商家名称", "merchant", "program", "advertiser", "brand", "programname", "program_name", "merchant name","advertiser name"],
    "点击": ["点击", "click", "clicks","# of clicks"],
    "订单": ["订单", "order", "orders", "# of orders","sale", "sales", "conversions","actions","conversion","no. of orders"],
    "佣金": ["佣金", "commission", "commissions", "earning", "earnings", "est. commission","total earnings","total commission","payout","total comm"]
}

def match_and_clean_columns(df):
    cleaned_df = pd.DataFrame()
    actual_cols = [str(c).strip().lower() for c in df.columns]

    for standard_name, aliases in COLUMN_MAPPING.items():
        matched_actual_name = None
        for alias in aliases:
            if alias in actual_cols:
                idx = actual_cols.index(alias)
                matched_actual_name = df.columns[idx]
                break
        
        if matched_actual_name:
            cleaned_df[standard_name] = df[matched_actual_name]
        else:
            raise ValueError(f"未能自动识别到【{standard_name}】这一列。\n请确认表格中是否包含以下表头关键词：{aliases}")

    return cleaned_df

# ==================== YP 商家 ID 动态映射算法 (云端跨平台兼容版) ====================
@st.cache_data
def load_yp_mapping_table(affiliate_name):
    """
    极速读取本地/云端 YP 商家 ID 映射表 (支持动态相对路径)
    """
    affiliate_clean = str(affiliate_name).strip()
    
    # 1. 动态获取项目根目录与 data 文件夹路径（向上退一层走出 pages 文件夹）
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DATA_DIR = os.path.join(BASE_DIR, "data")

    # 2. 字典统一管理：联盟名称 与 动态文件路径的对应关系
    file_path_map = {
        "Tradedoubler": os.path.join(DATA_DIR, "YP-TD.xlsx"),
        "Flexoffers": os.path.join(DATA_DIR, "YP-FO.xlsx"),
        "Impact": os.path.join(DATA_DIR, "YP-IMP.xlsx"),
        "Adpump": os.path.join(DATA_DIR, "YP-Adpump.xlsx"),
        "Ascend(partnerize)": os.path.join(DATA_DIR, "YP-Ascend (partnerize).xlsx"),
        "Linkbux": os.path.join(DATA_DIR, "YP-Linkbux.xlsx"),
        "Rakuten": os.path.join(DATA_DIR, "YP-Rakuten.xlsx"),
        "WebgainsY": os.path.join(DATA_DIR, "YP-WebgainsY.xlsx"),
        "Partnerize": os.path.join(DATA_DIR, "YP-Partnerize.xlsx"),
        "Linkhaitao": os.path.join(DATA_DIR, "YP-Linkhaitao.xlsx"),
        "Shopnomix": os.path.join(DATA_DIR, "YP-Shopnomix.xlsx"),
        "Partnermatic": os.path.join(DATA_DIR, "YP-Partnermatic.xlsx"),
        "InvolveAsia-Y": os.path.join(DATA_DIR, "YP-InvolveAsia-Y.xlsx"),
        # 💡 以后如果接了新联盟，只需要将表格放入 data/ 目录并在此新增一行即可：
        # "CJ Affiliate": os.path.join(DATA_DIR, "YP-CJ.xlsx"),
    }
    
    # 3. 根据选中的联盟拿到对应路径
    target_path = file_path_map.get(affiliate_clean)

    # 4. 校验文件是否存在并快速读取
    if target_path and os.path.exists(target_path):
        try:
            # 只读取前两列 (A列: ID, B列: 商家/广告名)
            df_map = pd.read_excel(target_path, usecols=[0, 1])
            df_map.columns = ["商家ID", "商家名称"]
            
            # 转为字符串并去首尾空格
            df_map["商家ID"] = df_map["商家ID"].astype(str).str.strip()
            df_map["商家名称"] = df_map["商家名称"].astype(str).str.strip()
            
            # 精准去重并返回
            return df_map.drop_duplicates(subset=["商家名称"])
        except Exception as e:
            st.error(f"⚠️ 读取 YP 映射文件失败 [{target_path}]: {e}")
            return None
            
    return None

# ==================== YP 商家 ID 末端匹配函数 ====================
def attach_merchant_id(df_target, affiliate_name):
    """
    【末端精准匹配】：仅对经过风控筛选后的最终名单添加 商家ID 列
    """
    if df_target.empty:
        return df_target

    df_res = df_target.copy()
    df_map = load_yp_mapping_table(affiliate_name)
    
    if df_map is not None and not df_map.empty:
        df_res["商家名称_clean"] = df_res["商家名称"].astype(str).str.strip()
        
        # 左连接匹配
        df_merged = pd.merge(
            df_res, 
            df_map, 
            left_on="商家名称_clean", 
            right_on="商家名称", 
            how="left", 
            suffixes=("", "_yp")
        )
        
        # 未撞到的统一填入 未匹配到
        df_merged["商家ID"] = df_merged["商家ID"].fillna("未匹配到")
        
        # 清理临时列
        df_merged = df_merged.drop(columns=["商家名称_clean"])
        if "商家名称_yp" in df_merged.columns:
            df_merged = df_merged.drop(columns=["商家名称_yp"])
            
        # 把 商家ID 调整放置在第一列
        cols = ["商家ID"] + [c for c in df_merged.columns if c != "商家ID"]
        return df_merged[cols]
    else:
        # 如果找不到映射表文件，填充默认文字提示
        df_res.insert(0, "商家ID", "未匹配到")
        return df_res
    
# ==================== 界面 UI 构建 ====================
st.title("🛡️ 联盟流量风控自动筛查工具 V1.0")

# --- 侧边栏：参数配置与文件上传 ---
with st.sidebar:
    st.header("⚙️ 参数配置与文件导入")
    
    uploaded_file = st.file_uploader("1. 导入联盟原始报表 (Excel)", type=["xlsx", "xls"])
    
    # 联盟切换改为了选择框 (支持完整名称)
    network_name = st.selectbox(
        "2. 所属联盟名称",
        ["Tradedoubler", "Flexoffers","Linkbux","Rakuten","WebgainsY","Partnerize","Linkhaitao","Shopnomix","Partnermatic","CJ Affiliate", "Impact", "Awin", "Adpump","Ascend(partnerize)","InvolveAsia-Y","其他联盟"],
        index=0
    )
    
    st.subheader("📅 时间范围")
    current_year = datetime.now().year
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        start_date = st.date_input("开始日期", date(current_year, 6, 20))
    with col_d2:
        end_date = st.date_input("结束日期", date(current_year, 7, 10))
        
    st.subheader("🚩 核心风控红线设置")
    min_click_line = st.number_input("低转化起抓线 (日均点击 >)", value=10.0)
    vip_comm_line = st.number_input("大户日均佣金门槛 ($)", value=100.0)
    vip_days_line = st.number_input("大户天数门槛 (天)", value=15.0)
    eps_offset_percent = st.number_input("EPS 大盘偏离度风控线 (%)", value=10.0)
    eps_offset_line = eps_offset_percent / 100.0

# --- 主界面逻辑 ---
if uploaded_file is not None:
    try:
        # 日期计算
        days = (end_date - start_date).days + 1
        if days <= 0:
            st.error("❌ 结束日期不能早于或等于开始日期！")
            st.stop()

        # 读取并清洗数据
        df_origin = pd.read_excel(uploaded_file)
        df = match_and_clean_columns(df_origin)
        df["所属联盟"] = network_name

        df["点击"] = pd.to_numeric(df["点击"], errors="coerce").fillna(0)
        df["订单"] = pd.to_numeric(df["订单"], errors="coerce").fillna(0)
        df["佣金"] = pd.to_numeric(df["佣金"], errors="coerce").fillna(0)

        # 计算大盘平均 EPS
        total_global_commission = df["佣金"].sum()
        total_global_orders = df["订单"].sum()
        global_avg_eps = total_global_commission / total_global_orders if total_global_orders > 0 else 0.0

        df["日均点击"] = df["点击"] / days
        df["日均佣金"] = df["佣金"] / days
        df["单店单笔均佣"] = df.apply(lambda r: r["佣金"] / r["订单"] if r["订单"] > 0 else 0.0, axis=1)
        df["CR_Raw"] = df.apply(lambda r: r["订单"] / r["点击"] if r["点击"] > 0 else (999 if r["订单"] > 0 else 0), axis=1)

        # 1. 流量风控判定 (Tab 1 专属)
        def evaluate_traffic_risk(row):
            reasons = []
            # 🚨 异常情况：点击小于订单
            if row["点击"] < row["订单"]:
                reasons.append("🚨 严重：点击数小于订单数")

            # 🔍 新增：判定媒体是否在测试商家（点击≥订单，且差值≤10，且订单不为0）
            if row["点击"] >= row["订单"] and (row["点击"] - row["订单"]) <= 10 and row["订单"] > 0:
                reasons.append(f"🔍 疑似测试：媒体可能正在测试该商家（点击:{int(row['点击'])}, 订单:{int(row['订单'])}）")
            # ⚠️ 灌水/洗账逻辑
            if row["日均点击"] > min_click_line:
                if row["日均点击"] >= 1000 and row["CR_Raw"] < 0.01:
                    reasons.append(f"⚠️ 爆量洗账：日均点击≥1000且CR({row['CR_Raw']*100:.2f}%)<1%")
                elif row["日均点击"] < 1000 and row["日均点击"] > 500 and row["CR_Raw"] < 0.003:
                    reasons.append(f"⚠️ 低效灌水：500<日均点击<1000且CR({row['CR_Raw']*100:.2f}%)<0.3%")
            # 💥 劫持嫌疑逻辑    
            if row["佣金"] <= 600 and row["佣金"] >= 100 and (0.10 <= row["CR_Raw"] < 999):
                reasons.append(f"💥 劫持嫌疑：100≤佣金≤600且CR({row['CR_Raw']*100:.1f}%)>10%")
            elif row["佣金"] > 600 and row["佣金"] >= 100 and (0.05 <= row["CR_Raw"] < 999):
                reasons.append(f"💥 劫持嫌疑：佣金>600且CR({row['CR_Raw']*100:.1f}%)>5%")
            # 🚨 极端情况
            if row["CR_Raw"] == 999:
                reasons.append("🚨 极端：0点击直接出单")
            return " | ".join(reasons) if reasons else "正常"

        # 2. 商家供应链与核心大户判定 (Tab 2 专属)
        def evaluate_merchant_focus(row):
            labels = []
            if row["日均佣金"] >= vip_comm_line and days >= vip_days_line:
                labels.append(f"⭐ 高产大户(日均佣金${row['日均佣金']:.2f})")
            if row["订单"] >= 5 and row["佣金"] == 0:
                labels.append(f"📉 商家赖账：订单达标({int(row['订单'])}笔)但返回总佣金为$0.00")
            if row["订单"] >= 5 and global_avg_eps > 0:
                cutoff_line = global_avg_eps * (1.0 - eps_offset_line)
                if row["单店单笔均佣"] <= cutoff_line:
                    labels.append(f"⚠️ EPS异常：均佣(${row['单店单笔均佣']:.2f}) 低于大盘风控线(${cutoff_line:.2f})")
            return " | ".join(labels) if labels else "普通"

        df["风控结论"] = df.apply(evaluate_traffic_risk, axis=1)
        df["商家标签"] = df.apply(evaluate_merchant_focus, axis=1)

        # 数据分流
        risky_df = df[df["风控结论"] != "正常"].copy()
        vip_df = df[df["商家标签"] != "普通"].copy()

        # --- 顶部大盘 Metric 卡片看板 ---
        m1, m2, m3 = st.columns(3)
        m1.metric("大盘平均 EPS", f"${global_avg_eps:.2f}")
        m2.metric("违规嫌疑流量商家数", f"{len(risky_df)} 家", delta_color="inverse")
        m3.metric("重点关注商家数", f"{len(vip_df)} 家")

        st.divider()

        # 展示统一的数据表列格式化函数
        def format_display_df(target_df, label_col):
            # 1. 执行末端匹配关联 YP 商家 ID
            matched_df = attach_merchant_id(target_df, network_name)
            
            # 2. 组织展示字段（确保 商家ID 放在第一个）
            display_df = pd.DataFrame()
            display_df["商家ID"] = matched_df["商家ID"]
            display_df["商家名称"] = matched_df["商家名称"]
            display_df["所属联盟"] = matched_df["所属联盟"]
            display_df["总点击"] = matched_df["点击"].astype(int)
            display_df["日均点击"] = matched_df["日均点击"].round(1)
            display_df["总订单"] = matched_df["订单"].astype(int)
            display_df["总佣金 ($)"] = matched_df["佣金"].map(lambda x: f"${x:.2f}")
            display_df["转化率 (CR)"] = matched_df["CR_Raw"].map(lambda x: "0点击出单" if x == 999 else f"{x*100:.2f}%")
            display_df["判定说明"] = matched_df[label_col]
            
            return display_df

        # --- 分页标签显示 ---
        tab1, tab2 = st.tabs(["🚨 违规风控嫌疑名单", "🌟 中长期重点关注商家"])

        with tab1:
            if not risky_df.empty:
                show_risky = format_display_df(risky_df, "风控结论")
                st.dataframe(show_risky, use_container_width=True, hide_index=True)
                
                # Excel 导出
                export_risky = attach_merchant_id(risky_df, network_name).drop(
                    columns=["CR_Raw", "商家标签", "单店单笔均佣", "日均佣金"], errors="ignore"
                )
                st.download_button(
                    label="📥 导出违规风控嫌疑报告 (.xlsx)",
                    data=export_risky.to_csv(index=False).encode('utf-8-sig'),
                    file_name="风控高危拦截报告.csv",
                    mime="text/csv",
                )
            else:
                st.success("🎉 未检测到符合条件的违规流量商家！")

        with tab2:
            if not vip_df.empty:
                show_vip = format_display_df(vip_df, "商家标签")
                st.dataframe(show_vip, use_container_width=True, hide_index=True)
                
                # Excel 导出
                export_vip = attach_merchant_id(vip_df, network_name).drop(
                    columns=["CR_Raw", "风控结论", "单店单笔均佣", "日均佣金"], errors="ignore"
                )
                st.download_button(
                    label="📥 导出重点关注商家报告 (.xlsx)",
                    data=export_vip.to_csv(index=False).encode('utf-8-sig'),
                    file_name="重点关注商家观察报告.csv",
                    mime="text/csv",
                )
            else:
                st.info("ℹ️ 未筛选出符合条件的大户或异常 EPS 商家。")

    except Exception as e:
        st.error(f"❌ 运行分析时出错：{str(e)}")
else:
    st.info("👈 请在左侧边栏上传联盟原始数据 Excel 文件以启动分析。")
