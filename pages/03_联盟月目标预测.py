import re
import numpy as np
import openpyxl
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from sklearn.ensemble import RandomForestRegressor

# -----------------------------------------------------------------------------
# 页面配置
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="联盟业绩 ML 智能预测系统", page_icon="🤖", layout="wide"
)

st.title("🤖 电商/联盟业绩智能预测与运营控制台 (ML + Human-in-the-Loop)")
st.caption(
    "支持 YYYYMM 格式 | 深度挖掘动量/加速度/媒体变动特征 | 支持全局与商家级媒体精准剔除"
)
st.markdown("---")


# -----------------------------------------------------------------------------
# 核心机器学习预测引擎
# -----------------------------------------------------------------------------
def dynamic_ml_predict_enhanced(df_raw, selected_alliance="全部"):
    df = df_raw.copy()

    # 1. 字段兼容与格式标准化
    if "出单月份" in df.columns:
        df["出单月份"] = (
            df["出单月份"]
            .astype(str)
            .str.replace(r"\.0$", "", regex=True)
            .str.strip()
        )
    else:
        return None, None, None, None, None, "数据缺失必需列 ['出单月份']"

    if "月度总佣金" in df.columns:
        df["月度总佣金"] = pd.to_numeric(df["月度总佣金"], errors="coerce").fillna(0)
    else:
        return None, None, None, None, None, "数据缺失必需列 ['月度总佣金']"

    if "商家状态" in df.columns:
        df["商家状态"] = (
            pd.to_numeric(df["商家状态"], errors="coerce").fillna(0).astype(int)
        )
    else:
        df["商家状态"] = 1  # 默认按上架处理

    # 联盟过滤
    if "所属联盟" in df.columns and selected_alliance != "全部":
        alliance_str = df["所属联盟"].astype(str).str.strip().str.upper()
        target_str = selected_alliance.strip().upper()
        df = df[alliance_str.str.contains(target_str, na=False)].copy()

    if df.empty:
        return None, None, None, None, None, f"未找到联盟 '{selected_alliance}' 的数据。"

    # 计算全量历史月份的总佣金 (用于全量折线图展示)
    all_history_series = df.groupby("出单月份")["月度总佣金"].sum().sort_index()

    # 2. 按 [商家名称, 出单月份] 进行多维特征聚合
    def calc_hhi(series):
        total = series.sum()
        if total <= 0:
            return 0.0
        shares = series / total
        return (shares**2).sum()

    agg_list = []
    grouped = df.groupby(["商家名称", "出单月份"])

    for (merchant, month), group in grouped:
        total_comm = group["月度总佣金"].sum()
        status = group["商家状态"].iloc[0]

        if "媒体ID" in group.columns:
            pub_comm = group.groupby("媒体ID")["月度总佣金"].sum().sort_values(ascending=False)
            active_pub_count = (pub_comm > 0).sum()
            top1_comm = pub_comm.iloc[0] if len(pub_comm) > 0 else 0
            top3_comm = pub_comm.iloc[:3].sum() if len(pub_comm) > 0 else 0
            top1_pub_id = pub_comm.index[0] if len(pub_comm) > 0 else None
        else:
            active_pub_count = 1
            top1_comm = total_comm
            top3_comm = total_comm
            top1_pub_id = "Default"

        top1_share = (top1_comm / total_comm) if total_comm > 0 else 0
        top3_share = (top3_comm / total_comm) if total_comm > 0 else 0
        hhi = calc_hhi(pub_comm) if "媒体ID" in group.columns else 1.0

        agg_list.append(
            {
                "商家名称": merchant,
                "出单月份": month,
                "商家状态": status,
                "月度总佣金": total_comm,
                "出单媒体数": active_pub_count,
                "Top1占比": top1_share,
                "Top3占比": top3_share,
                "HHI指数": hhi,
                "Top1媒体ID": top1_pub_id,
            }
        )

    df_monthly = pd.DataFrame(agg_list)

    # 3. 提取所有历史月份 (按字典序排序)
    months = sorted(df_monthly["出单月份"].unique())
    if len(months) < 3:
        return (
            None,
            None,
            None,
            None,
            None,
            f"当前筛选下检测到的历史月份少于 3 个月({months})，无法构建特征工程。",
        )

    merchant_month_map = df_monthly.set_index(["商家名称", "出单月份"]).to_dict("index")
    all_merchants = df_monthly["商家名称"].unique()

    # 4. 高维特征提取函数
    def extract_advanced_features(target_merchants, m3, m2, m1, target_month_str):
        X_data = []
        target_month_num = (
            int(target_month_str[-2:]) if len(target_month_str) >= 6 else 1
        )

        for m in target_merchants:
            d1 = merchant_month_map.get((m, m1), {})
            d2 = merchant_month_map.get((m, m2), {})
            d3 = merchant_month_map.get((m, m3), {})

            v1 = d1.get("月度总佣金", 0.0)
            v2 = d2.get("月度总佣金", 0.0)
            v3 = d3.get("月度总佣金", 0.0)

            mean_3m = (v1 + v2 + v3) / 3.0
            std_3m = np.std([v1, v2, v3])
            cv_3m = std_3m / (mean_3m + 1e-5)

            mom_1_2 = (v1 - v2) / (v2 + 1.0)
            mom_2_3 = (v2 - v3) / (v3 + 1.0)
            acceleration = mom_1_2 - mom_2_3

            pub_c1 = d1.get("出单媒体数", 0)
            pub_c2 = d2.get("出单媒体数", 0)
            pub_mom = (pub_c1 - pub_c2) / (pub_c2 + 1.0)

            top1_s1 = d1.get("Top1占比", 0.0)
            top3_s1 = d1.get("Top3占比", 0.0)
            hhi1 = d1.get("HHI指数", 0.0)

            top1_changed = (
                1
                if (
                    d1.get("Top1媒体ID")
                    and d1.get("Top1媒体ID") != d2.get("Top1媒体ID")
                )
                else 0
            )

            s1 = d1.get("商家状态", 1)
            s2 = d2.get("商家状态", 1)
            s3 = d3.get("商家状态", 1)
            offline_cnt = sum([1 for s in [s1, s2, s3] if s != 1])

            X_data.append(
                [
                    v1,
                    v2,
                    v3,
                    mean_3m,
                    std_3m,
                    cv_3m,
                    mom_1_2,
                    mom_2_3,
                    acceleration,
                    pub_c1,
                    pub_mom,
                    top1_s1,
                    top3_s1,
                    hhi1,
                    top1_changed,
                    target_month_num,
                    offline_cnt,
                ]
            )

        feature_cols = [
            "v_last1",
            "v_last2",
            "v_last3",
            "mean_3m",
            "std_3m",
            "cv_3m",
            "mom_1_2",
            "mom_2_3",
            "acceleration",
            "pub_count_last1",
            "pub_mom",
            "top1_share",
            "top3_share",
            "hhi",
            "top1_changed",
            "target_month_num",
            "offline_cnt_3m",
        ]
        return pd.DataFrame(X_data, columns=feature_cols)

    # 5. 构建训练集
    if len(months) >= 4:
        m_train_3, m_train_2, m_train_1 = months[-4], months[-3], months[-2]
        m_train_target = months[-1]
    else:
        m_train_3, m_train_2, m_train_1 = months[-3], months[-2], months[-1]
        m_train_target = months[-1]

    X_train = extract_advanced_features(
        all_merchants, m_train_3, m_train_2, m_train_1, m_train_target
    )
    y_train = [
        merchant_month_map.get((m, m_train_target), {}).get("月度总佣金", 0.0)
        for m in all_merchants
    ]

    rf_model = RandomForestRegressor(n_estimators=100, max_depth=6, random_state=42)
    rf_model.fit(X_train, y_train)

    last_m_str = str(months[-1])
    match = re.search(r"\d{6}", last_m_str)
    if match:
        ym_int = int(match.group())
        yr, mo = ym_int // 100, ym_int % 100
        next_ym_str = f"{yr + 1}01" if mo == 12 else f"{yr}{mo + 1:02d}"
    else:
        next_ym_str = f"{last_m_str}_Predict"

    pred_col_name = f"{next_ym_str} 预测佣金"

    m_pred_3, m_pred_2, m_pred_1 = months[-3], months[-2], months[-1]
    X_pred = extract_advanced_features(
        all_merchants, m_pred_3, m_pred_2, m_pred_1, next_ym_str
    )
    raw_preds = rf_model.predict(X_pred)

    res_rows = []
    for idx, merchant in enumerate(all_merchants):
        d1 = merchant_month_map.get((merchant, m_pred_1), {})
        latest_status = d1.get("商家状态", 1)
        v1 = d1.get("月度总佣金", 0.0)
        v2 = merchant_month_map.get((merchant, m_pred_2), {}).get("月度总佣金", 0.0)
        v3 = merchant_month_map.get((merchant, m_pred_3), {}).get("月度总佣金", 0.0)

        if latest_status == 3:
            final_val = 0.0
            reason = "已被禁用 (状态为3)"
            status_desc = "禁用 (Banned)"
        elif latest_status != 1:
            final_val = 0.0
            reason = "已下架 (状态非1且非3)"
            status_desc = "下架 (Offline)"
        elif v1 == 0 and v2 == 0 and v3 == 0:
            final_val = 0.0
            reason = "连续3月无流水"
            status_desc = "正常上架 (无流水)"
        else:
            final_val = max(0.0, round(raw_preds[idx], 2))
            reason = "ML多维拟合 (包含动量与媒体生态)"
            status_desc = "正常上架"

        row_feat = X_pred.iloc[idx]

        res_rows.append(
            {
                "商家名称": merchant,
                "真实上下架状态": status_desc,
                f"{m_pred_3} 佣金": v3,
                f"{m_pred_2} 佣金": v2,
                f"{m_pred_1} 佣金": v1,
                "最新出单媒体数": d1.get("出单媒体数", 0),
                "Top1媒体占比": f"{d1.get('Top1占比', 0.0):.1%}",
                "近1月环比(MoM)": f"{row_feat['mom_1_2']:+.1%}",
                "业绩加速度": f"{row_feat['acceleration']:+.2f}",
                "历史波动率(CV)": f"{row_feat['cv_3m']:.2f}",
                "头部媒体变更Flag": "⚠️ 发生换血" if row_feat["top1_changed"] == 1 else "稳定",
                pred_col_name: final_val,
                "预测逻辑/状态": reason,
            }
        )

    df_result = pd.DataFrame(res_rows)
    recent_3_months = [f"{m_pred_3} 佣金", f"{m_pred_2} 佣金", f"{m_pred_1} 佣金"]

    feature_importances = pd.Series(
        rf_model.feature_importances_, index=X_pred.columns
    ).sort_values(ascending=False)

    return (
        df_result,
        recent_3_months,
        pred_col_name,
        feature_importances,
        all_history_series,
        "Success",
    )


# -----------------------------------------------------------------------------
# 辅助函数：后处理与运营规则干预计算 Engine (支持全局+商家级双层剔除)
# -----------------------------------------------------------------------------
def apply_operator_adjustments(
    df_res, df_raw, target_pred_col, global_banned_media, adjustments_dict
):
    df_adj = df_res.copy()

    # 确定计算基准月份 (最新出单月)
    df_latest = pd.DataFrame()
    if "媒体ID" in df_raw.columns and "出单月份" in df_raw.columns:
        latest_month = (
            df_raw["出单月份"].astype(str).str.replace(r"\.0$", "", regex=True).max()
        )
        df_latest = df_raw[
            df_raw["出单月份"].astype(str).str.replace(r"\.0$", "", regex=True)
            == latest_month
        ]

    final_preds = []
    adj_reasons = []

    for _, row in df_adj.iterrows():
        m_name = row["商家名称"]
        base_val = row[target_pred_col]

        adj_config = adjustments_dict.get(
            m_name,
            {
                "mode": "普通",
                "custom_rate": 0.0,
                "is_offline": False,
                "banned_media": [],
            },
        )

        if adj_config.get("is_offline", False):
            val = 0.0
            reason = "🚫 模拟下架 (强制清零)"
        else:
            # 1. 模式系数计算
            mode = adj_config.get("mode", "普通")
            if mode == "保守":
                rate = -0.20
            elif mode == "激进":
                rate = 0.30
            elif mode == "自定义":
                rate = adj_config.get("custom_rate", 0.0)
            else:
                rate = 0.0

            val = base_val * (1.0 + rate)

            # 2. 违规媒体剔除计算（全局剔除 + 商家专属剔除 取并集）
            merchant_specific_banned = adj_config.get("banned_media", [])
            combined_banned = set(global_banned_media + merchant_specific_banned)

            loss_ratio = 0.0
            if combined_banned and not df_latest.empty:
                m_grp = df_latest[df_latest["商家名称"] == m_name]
                m_total = m_grp["月度总佣金"].sum()
                if m_total > 0:
                    banned_comm = m_grp[m_grp["媒体ID"].isin(combined_banned)][
                        "月度总佣金"
                    ].sum()
                    loss_ratio = min(1.0, banned_comm / m_total)

            if loss_ratio > 0:
                val = val * (1.0 - loss_ratio)
                banned_info = []
                if global_banned_media:
                    banned_info.append("全局")
                if merchant_specific_banned:
                    banned_info.append("专属")
                tag = "+".join(banned_info)
                reason = f"⚠️ 扣除[{tag}]违规媒体份额(-{loss_ratio:.1%}) | 模式:{mode}({rate:+.0%})"
            elif rate != 0:
                reason = f"✏️ 运营人工干预: {mode}({rate:+.0%})"
            else:
                reason = row["预测逻辑/状态"]

        final_preds.append(max(0.0, round(val, 2)))
        adj_reasons.append(reason)

    df_adj["运营干预后预测"] = final_preds
    df_adj["最终预测状态"] = adj_reasons
    return df_adj


# -----------------------------------------------------------------------------
# Streamlit 界面交互
# -----------------------------------------------------------------------------
st.sidebar.header("📥 数据导入")
uploaded_file = st.sidebar.file_uploader(
    "上传佣金数据 (支持 202507 格式)", type=["xlsx", "csv"]
)

if uploaded_file is not None:
    try:
        if uploaded_file.name.endswith(".csv"):
            df_raw = pd.read_csv(uploaded_file)
        else:
            df_raw = pd.read_excel(uploaded_file)

        alliances = ["全部"]
        if "所属联盟" in df_raw.columns:
            unique_all = df_raw["所属联盟"].dropna().unique().tolist()
            alliances += [str(a) for a in unique_all]

        selected_alliance = st.sidebar.selectbox("选择要分析的联盟", list(set(alliances)))

        (
            df_res,
            month_cols,
            target_pred_col,
            feat_imp,
            all_history_series,
            msg,
        ) = dynamic_ml_predict_enhanced(df_raw, selected_alliance)

        if df_res is None:
            st.error(msg)
        else:
            # 状态持久化初始化
            if "applied_state" not in st.session_state:
                st.session_state.applied_state = {}
            if "applied_global_banned_media" not in st.session_state:
                st.session_state.applied_global_banned_media = []

            # 获取全量媒体列表
            available_media = []
            if "媒体ID" in df_raw.columns:
                available_media = sorted(
                    df_raw["媒体ID"].dropna().astype(str).unique().tolist()
                )

            # 预先构建【商家 -> 近3个月有过流水媒体列表】字典
            merchant_recent_media_map = {}
            if "媒体ID" in df_raw.columns and "出单月份" in df_raw.columns:
                df_raw["clean_month"] = (
                    df_raw["出单月份"]
                    .astype(str)
                    .str.replace(r"\.0$", "", regex=True)
                    .str.strip()
                )
                all_months = sorted(df_raw["clean_month"].unique())
                recent_3_m = all_months[-3:] if len(all_months) >= 3 else all_months

                df_recent_3m = df_raw[
                    (df_raw["clean_month"].isin(recent_3_m))
                    & (df_raw["月度总佣金"] > 0)
                ]

                for m_name, grp in df_recent_3m.groupby("商家名称"):
                    m_pubs = sorted(grp["媒体ID"].dropna().astype(str).unique().tolist())
                    merchant_recent_media_map[m_name] = m_pubs

            # -----------------------------------------------------------------
            # 🎛️ 侧边栏：全局违规媒体剔除 (保留原全部剔除功能)
            # -----------------------------------------------------------------
            st.sidebar.markdown("---")
            st.sidebar.header("🌐 全局违规/风险剔除")

            global_banned_input = st.sidebar.multiselect(
                "全联盟通用封禁媒体 (影响所有商家)",
                options=available_media,
                default=st.session_state.applied_global_banned_media,
                help="此处选中的媒体将被认定为全网/全联盟封禁，对所有关联商家统一扣除份额。",
            )

            # 根据已确认应用的状态计算结果
            df_final = apply_operator_adjustments(
                df_res,
                df_raw,
                target_pred_col,
                st.session_state.applied_global_banned_media,
                st.session_state.applied_state,
            )

            # -----------------------------------------------------------------
            # 1. 动态双轨 KPI 概览
            # -----------------------------------------------------------------
            st.subheader(f"📊 联盟业绩预测与模拟概况 ({selected_alliance})")

            last_month_col = month_cols[-1]
            sum_last_m = df_res[last_month_col].sum()
            sum_ml_pred = df_res[target_pred_col].sum()
            sum_adj_pred = df_final["运营干预后预测"].sum()

            ml_mom_pct = ((sum_ml_pred - sum_last_m) / (sum_last_m + 1e-5)) * 100.0
            adj_diff = sum_adj_pred - sum_ml_pred

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("商家总数", f"{len(df_res)} 家")
            c2.metric(
                f"最新实际 ({last_month_col.replace(' 佣金', '')})",
                f"¥{sum_last_m:,.2f}",
            )
            c3.metric(
                f"ML 原始预测 ({target_pred_col.split()[0]})",
                f"¥{sum_ml_pred:,.2f}",
                f"{ml_mom_pct:+.2f}% 环比",
            )
            c4.metric(
                "🎛️ 运营干预后预测",
                f"¥{sum_adj_pred:,.2f}",
                f"{adj_diff:+,.2f} 元 (相对ML)",
                delta_color="normal",
            )

            st.markdown("---")

            # -----------------------------------------------------------------
            # 2. 预测趋势图与商家结构 (已更新为全量历史趋势)
            # -----------------------------------------------------------------
            col_chart1, col_chart2 = st.columns([2, 1])

            with col_chart1:
                st.subheader("📈 全局历史趋势与预测对比")
                
                # 获取全量历史月份与数据点
                x_hist = [str(m) for m in all_history_series.index]
                y_hist = all_history_series.values
                pred_label = target_pred_col.split()[0]

                fig = go.Figure()
                
                # 1. 全量历史数据实线
                fig.add_trace(
                    go.Scatter(
                        x=x_hist,
                        y=y_hist,
                        mode="lines+markers",
                        name="全局历史实际业绩",
                        line=dict(color="#2ca02c", width=3),
                    )
                )
                
                # 2. ML 原始预测虚线 (从最后一个历史月份延伸到预测月)
                fig.add_trace(
                    go.Scatter(
                        x=[x_hist[-1], pred_label],
                        y=[y_hist[-1], sum_ml_pred],
                        mode="lines+markers",
                        name="ML 原始预测",
                        line=dict(color="#1f77b4", width=2, dash="dash"),
                    )
                )
                
                # 3. 运营干预预测线 (从最后一个历史月份延伸到预测月)
                fig.add_trace(
                    go.Scatter(
                        x=[x_hist[-1], pred_label],
                        y=[y_hist[-1], sum_adj_pred],
                        mode="lines+markers",
                        name="运营干预预测",
                        line=dict(color="#d62728", width=3),
                    )
                )
                
                fig.update_layout(
                    xaxis_title="月份",
                    xaxis=dict(type="category"),
                    yaxis_title="总佣金 (元)",
                    hovermode="x unified",
                )
                st.plotly_chart(fig, use_container_width=True)

            with col_chart2:
                st.subheader("📌 商家状态结构")
                reason_df = df_res["真实上下架状态"].value_counts().reset_index()
                reason_df.columns = ["状态说明", "数量"]
                fig_pie = px.pie(reason_df, values="数量", names="状态说明", hole=0.4)
                st.plotly_chart(fig_pie, use_container_width=True)

            # -----------------------------------------------------------------
            # 3. 🛠️ 商家微调操控台 (支持精细化至商家的剔除)
            # -----------------------------------------------------------------
            st.markdown("---")
            st.subheader("🛠️ 商家微调控制台")
            st.caption(
                "可在下方选中指定商家，单独为其剔除【近3个月合作过】的违规媒体；也可以全局设置增长模式与模拟下架。"
            )

            # 3.1 单商家精准剔除媒体区 (卡片式微调器)
            with st.expander("🎯 点击展开：按商家单独剔除违规媒体 (细化到具体商家)", expanded=True):
                selected_merchant_for_media = st.selectbox(
                    "选择要针对性设置的商家:",
                    options=sorted(df_res["商家名称"].tolist()),
                    help="下拉列表仅显示该商家近3个月真正产生过佣金的媒体",
                )

                # 提取该商家近3个月产生过佣金的媒体
                m_recent_pubs = merchant_recent_media_map.get(
                    selected_merchant_for_media, []
                )

                # 读取该商家当前已保存的剔除设置
                current_m_config = st.session_state.applied_state.get(
                    selected_merchant_for_media, {}
                )
                current_banned_for_m = current_m_config.get("banned_media", [])

                if not m_recent_pubs:
                    st.info(f"ℹ️ 商家【{selected_merchant_for_media}】近3个月无出单媒体数据。")
                    selected_m_banned = []
                else:
                    selected_m_banned = st.multiselect(
                        f"剔除商家【{selected_merchant_for_media}】的特定媒体 (仅展示近3个月合作媒体):",
                        options=m_recent_pubs,
                        default=[p for p in current_banned_for_m if p in m_recent_pubs],
                        key=f"ms_media_{selected_merchant_for_media}",
                    )

                # 暂存商家级媒体选择到对应配置
                if selected_merchant_for_media not in st.session_state.applied_state:
                    st.session_state.applied_state[selected_merchant_for_media] = {
                        "mode": "普通",
                        "custom_rate": 0.0,
                        "is_offline": False,
                        "banned_media": selected_m_banned,
                    }
                else:
                    st.session_state.applied_state[selected_merchant_for_media][
                        "banned_media"
                    ] = selected_m_banned

            # 3.2 批量配置表格表单
            with st.form("operator_adjustment_form"):
                st.markdown("##### 📝 商家配置与模式调整表")
                editor_df = df_res[["商家名称", target_pred_col]].copy()

                # 读取状态
                modes, custom_rates, off_flags, m_banned_str_list = [], [], [], []
                for m in editor_df["商家名称"]:
                    cfg = st.session_state.applied_state.get(m, {})
                    modes.append(cfg.get("mode", "普通"))
                    custom_rates.append(cfg.get("custom_rate", 0.0))
                    off_flags.append(cfg.get("is_offline", False))
                    
                    # 汇总展示商家专属剔除的媒体
                    b_list = cfg.get("banned_media", [])
                    m_banned_str_list.append(", ".join(b_list) if b_list else "无")

                editor_df["预期模式"] = modes
                editor_df["自定义比例(如 0.5代表+50%)"] = custom_rates
                editor_df["模拟下架"] = off_flags
                editor_df["已单独剔除的媒体"] = m_banned_str_list

                edited_df = st.data_editor(
                    editor_df.sort_values(by=target_pred_col, ascending=False),
                    column_config={
                        "商家名称": st.column_config.Column(disabled=True),
                        target_pred_col: st.column_config.NumberColumn(
                            "ML预测基线", disabled=True, format="¥%.2f"
                        ),
                        "预期模式": st.column_config.SelectboxColumn(
                            "预估模式",
                            options=["普通", "保守", "激进", "自定义"],
                            required=True,
                        ),
                        "自定义比例(如 0.5代表+50%)": st.column_config.NumberColumn(
                            "自定义浮动",
                            format="%.2f",
                            min_value=-1.0,
                            max_value=5.0,
                        ),
                        "模拟下架": st.column_config.CheckboxColumn("模拟强制下架"),
                        "已单独剔除的媒体": st.column_config.Column(
                            "专属剔除媒体", disabled=True
                        ),
                    },
                    use_container_width=True,
                    height=350,
                    key="editor_table",
                )

                # 🚀 确认提交按钮
                submit_button = st.form_submit_button(
                    "🚀 确认应用修改 (统一刷新预测与图表)",
                    type="primary",
                    use_container_width=True,
                )

                if submit_button:
                    # 批量更新配置
                    for _, row in edited_df.iterrows():
                        m_name = row["商家名称"]
                        old_cfg = st.session_state.applied_state.get(m_name, {})
                        
                        st.session_state.applied_state[m_name] = {
                            "mode": row["预期模式"],
                            "custom_rate": float(row["自定义比例(如 0.5代表+50%)"]),
                            "is_offline": bool(row["模拟下架"]),
                            "banned_media": old_cfg.get("banned_media", []),
                        }

                    st.session_state.applied_global_banned_media = global_banned_input
                    st.success("✅ 包含【全局剔除】与【商家专属剔除】的修改已统一更新！")
                    st.rerun()

            # -----------------------------------------------------------------
            # 4. AI 特征归因与诊断可视化
            # -----------------------------------------------------------------
            st.markdown("---")
            st.subheader("🧠 AI 算法特征重要性归因 (模型靠什么做判断？)")

            feat_df = feat_imp.reset_index()
            feat_df.columns = ["特征指标名称", "重要性权重"]

            name_map = {
                "v_last1": "最近 1 月佣金流量",
                "v_last2": "最近 2 月佣金流量",
                "v_last3": "最近 3 月佣金流量",
                "mean_3m": "近 3 月均值",
                "std_3m": "业绩标准差",
                "cv_3m": "波动率 (CV)",
                "mom_1_2": "近 1 月环比增速",
                "mom_2_3": "上月环比增速",
                "acceleration": "业绩加速度",
                "pub_count_last1": "最新出单媒体数",
                "pub_mom": "媒体扩增率",
                "top1_share": "Top1 媒体集中度",
                "top3_share": "Top3 媒体集中度",
                "hhi": "赫芬达尔集中度指数",
                "top1_changed": "头部媒体更换 Flag",
                "target_month_num": "预测目标月份(季节性)",
                "offline_cnt_3m": "近 3 月下架频次",
            }
            feat_df["特征指标名称"] = feat_df["特征指标名称"].map(
                lambda x: name_map.get(x, x)
            )

            fig_bar = px.bar(
                feat_df.head(8),
                x="重要性权重",
                y="特征指标名称",
                orientation="h",
                title="Top 8 最核心影响因子权重分布",
                color="重要性权重",
                color_continuous_scale="Viridis",
            )
            fig_bar.update_layout(yaxis={"categoryorder": "total ascending"})
            st.plotly_chart(fig_bar, use_container_width=True)

            # -----------------------------------------------------------------
            # 5. 整合全量数据与干预明细表
            # -----------------------------------------------------------------
            st.subheader("🔍 商家明细预测、AI 诊断与干预结果表")

            show_cols = [
                "商家名称",
                "真实上下架状态",
                "最新出单媒体数",
                "Top1媒体占比",
                "近1月环比(MoM)",
                "业绩加速度",
                "历史波动率(CV)",
                "头部媒体变更Flag",
            ] + month_cols + [target_pred_col, "运营干预后预测", "最终预测状态"]

            valid_show_cols = [c for c in show_cols if c in df_final.columns]

            st.dataframe(
                df_final[valid_show_cols].sort_values(
                    by="运营干预后预测", ascending=False
                ),
                use_container_width=True,
                height=450,
            )

            # 导出 CSV
            csv_file = df_final.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                label="📥 导出干预后全量预测与特征诊断 CSV",
                data=csv_file,
                file_name=f"alliance_prediction_granular_{target_pred_col.split()[0]}.csv",
                mime="text/csv",
            )

    except Exception as e:
        st.error(f"计算或渲染失败: {str(e)}")
else:
    st.info(
        "👋 请在左侧上传 Excel/CSV 数据。系统已支持【全局媒体剔除】与【商家专属媒体剔除】的双层风险模拟。"
    )