import datetime
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px

# 1. 提升 Pandas Styler 渲染上限，防止大表报错
pd.set_option("styler.render.max_elements", 2000000)

st.set_page_config(
    page_title="多周期联盟数据匹配与分析工具", page_icon="📊", layout="wide"
)

st.title("📊 多周期联盟数据匹配与分析工具")
st.caption(
    "支持自主添加多个对比周期（联盟表 + 后台表），实现多期数据平铺展示与差异诊断。"
)

# ----------------------------------------------------------------------
# Session State 初始化（用于管理动态增减的周期区块）
# ----------------------------------------------------------------------
if "period_count" not in st.session_state:
    st.session_state.period_count = 2  # 默认提供 2 个周期区块


def add_period():
    st.session_state.period_count += 1


def remove_period():
    if st.session_state.period_count > 1:
        st.session_state.period_count -= 1


@st.cache_data
def load_data(file):
    if file.name.endswith(".csv"):
        return pd.read_csv(file)
    else:
        return pd.read_excel(file)


# ----------------------------------------------------------------------
# 1. 动态多周期文件上传模块（已整合日历范围选择器）
# ----------------------------------------------------------------------
st.subheader("📁 1. 动态添加与上传数据周期")

# 控制按钮
btn_col1, btn_col2, _ = st.columns([1.5, 1.5, 7])
with btn_col1:
    st.button("➕ 添加对比周期", on_click=add_period, type="secondary")
with btn_col2:
    st.button("➖ 减少对比周期", on_click=remove_period)

periods_data = []
today = datetime.date.today()

# 循环渲染各个周期的上传组件
for i in range(st.session_state.period_count):
    st.markdown(f"##### 🗓️ 周期 {i+1} 配置")

    # 精简列结构：只有“别名”和“日历范围选择框”
    p_col1, p_col2, p_col3 = st.columns([2, 3, 3])

    with p_col1:
        p_alias = st.text_input(
            f"周期别名 (可选)",
            value=f"周期_{i+1}",
            key=f"p_alias_{i}",
            help="如：7月大促 / 本周 / Week31",
        )

    with p_col2:
        # 默认示例日期：周期1为本月至今，周期2为上个月
        if i == 0:
            default_start = today.replace(day=1)
            default_end = today
        else:
            first_day_this_month = today.replace(day=1)
            default_end = first_day_this_month - datetime.timedelta(days=1)
            default_start = default_end.replace(day=1)

        date_range = st.date_input(
            "📅 选择日期范围 (起始 ➡️ 结束)",
            value=(default_start, default_end),
            key=f"p_date_{i}",
        )

    # 提取日期范围信息并计算天数/年份
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
        p_days = (end_date - start_date).days + 1
        p_year = start_date.year
        p_name = f"{p_alias} ({start_date.strftime('%m/%d')}~{end_date.strftime('%m/%d')})"
    else:
        # 处理用户只选了一个日期还没选结束日期的中间状态
        start_date = (
            date_range[0] if isinstance(date_range, tuple) else date_range
        )
        p_days = 1
        p_year = start_date.year
        p_name = p_alias

    with p_col3:
        st.markdown("<br>", unsafe_allow_html=True)
        st.info(f"💡 **解析属性**：{p_year}年 | 共 **{p_days}** 天")

    f_col1, f_col2 = st.columns(2)
    with f_col1:
        net_file = st.file_uploader(
            f"【{p_alias}】上游联盟表 (CSV/Excel)",
            type=["csv", "xlsx"],
            key=f"net_file_{i}",
        )
    with f_col2:
        int_file = st.file_uploader(
            f"【{p_alias}】内部后台表 (CSV/Excel)",
            type=["csv", "xlsx"],
            key=f"int_file_{i}",
        )

    if net_file and int_file:
        periods_data.append({
            "index": i,
            "name": p_name,
            "alias": p_alias,
            "year": p_year,
            "days": p_days,
            "start_date": start_date,
            "end_date": end_date if "end_date" in locals() else start_date,
            "df_net": load_data(net_file),
            "df_int": load_data(int_file),
        })

    st.markdown("---")

# ----------------------------------------------------------------------
# 2. 全局字段映射配置（只需配置一次）
# ----------------------------------------------------------------------
if len(periods_data) == st.session_state.period_count:
    st.success(
        f"✅ 已成功加载所有 {len(periods_data)} 个周期的数据文件！"
    )

    st.subheader("⚙️ 2. 全局字段与匹配列映射（只需配置一次）")
    st.caption("提示：请确保各个周期的表格列名基本一致。")

    # 取第一个周期的 df 提取列名
    sample_net = periods_data[0]["df_net"]
    sample_int = periods_data[0]["df_int"]

    # 主键选择
    c_key1, c_key2 = st.columns(2)
    with c_key1:
        net_join_key = st.selectbox(
            "上游联盟表匹配主键 (如 MID / 商家名称)",
            sample_net.columns,
            key="g_net_key",
        )
    with c_key2:
        int_join_key = st.selectbox(
            "内部后台表匹配主键 (如 MID / 商家名称)",
            sample_int.columns,
            key="g_int_key",
        )

    # 字段选择
    c_map1, c_map2 = st.columns(2)
    with c_map1:
        st.markdown("**【上游联盟表】核心指标列：**")
        net_clicks = st.selectbox("点击量列 (Clicks)", sample_net.columns)
        net_sales = st.selectbox(
            "订单数列 (Sales/Orders)", sample_net.columns
        )
        net_gmv = st.selectbox("销售额列 (GMV/Revenue)", sample_net.columns)
        net_comm = st.selectbox(
            "预估佣金列 (Est. Commission)", sample_net.columns
        )

    with c_map2:
        st.markdown("**【内部后台表】媒体元数据列：**")
        int_pub_name = st.selectbox(
            "媒体 ID / 媒体名称列", sample_int.columns
        )
        int_pub_cat = st.selectbox(
            "媒体分类列 (Category, 可选)",
            [None] + list(sample_int.columns),
        )
        int_clicks = st.selectbox(
            "后台点击量列 (用于计算差异, 可选)",
            [None] + list(sample_int.columns),
        )
        # 🌟 优化加点：新增媒体后台佣金列选择 (ALL佣金)
        int_comm = st.selectbox(
            "单个媒体佣金列 (媒体后台支出/佣金, 可选)",
            [None] + list(sample_int.columns),
            key="g_int_comm",
        )

    # ----------------------------------------------------------------------
    # 3. 数据计算与合并处理
    # ----------------------------------------------------------------------
    if st.button("🚀 开始多周期匹配合并", type="primary"):
        processed_periods = []

        for p in periods_data:
            df_n = p["df_net"].copy()
            df_i = p["df_int"].copy()

            # 清洗 Join Key
            df_n[net_join_key] = df_n[net_join_key].astype(str).str.strip()
            df_i[int_join_key] = df_i[int_join_key].astype(str).str.strip()

            # 转数值
            num_cols = [net_clicks, net_sales, net_gmv, net_comm]
            for col in num_cols:
                df_n[col] = pd.to_numeric(df_n[col], errors="coerce").fillna(0)

            # 🌟 转数值：如果选择了后台媒体佣金列，将其转换为数值型
            if int_comm and int_comm in df_i.columns:
                df_i[int_comm] = pd.to_numeric(df_i[int_comm], errors="coerce").fillna(0)

            # 左匹配
            df_m = pd.merge(
                df_n,
                df_i,
                left_on=net_join_key,
                right_on=int_join_key,
                how="left",
                suffixes=("_联盟", "_后台"),
            )

            # 算指标
            df_m["CVR (%)"] = (
                df_m[net_sales] / df_m[net_clicks].replace(0, pd.NA) * 100
            ).fillna(0)
            df_m["AOV ($)"] = (
                df_m[net_gmv] / df_m[net_sales].replace(0, pd.NA)
            ).fillna(0)

            if int_clicks and int_clicks in df_m.columns:
                df_m[int_clicks] = pd.to_numeric(
                    df_m[int_clicks], errors="coerce"
                ).fillna(0)
                df_m["点击差异数"] = df_m[int_clicks] - df_m[net_clicks]
                df_m["点击差异率 (%)"] = (
                    df_m["点击差异数"]
                    / df_m[net_clicks].replace(0, pd.NA)
                    * 100
                ).fillna(0)

            p["merged_df"] = df_m
            processed_periods.append(p)

        # 保存到 Session State
        st.session_state.processed_periods = processed_periods
        st.session_state.data_ready = True

# ----------------------------------------------------------------------
# 4. Tab 标签页展现模块 (大表格与后续分析彻底解耦)
# ----------------------------------------------------------------------
if st.session_state.get("data_ready", False):
    st.markdown("---")

    tab1, tab2, tab3 = st.tabs([
        "📋 Tab 1: 多周期横向对比大表",
        "📂 Tab 2: 分周期独立明细",
        "🧠 Tab 3: 智能数据分析与诊断 (预留)",
    ])

    processed_periods = st.session_state.processed_periods

    # ------------------------------------------------------------------
    # Tab 1: 多周期横向对比大表
    # ------------------------------------------------------------------
    with tab1:
        st.subheader("📋 多周期横向对比大表")
        st.caption(
            "将各个周期的 GMV、点击、联盟佣金以及媒体后台佣金平铺在同一张大表中，方便横向对比变化。"
        )

        # 构建全周期对比视图
        base_df = processed_periods[0]["merged_df"][
            [net_join_key, int_pub_name]
        ].drop_duplicates()

        for p in processed_periods:
            p_name = p["name"]
            p_df = p["merged_df"]

            # 选取该周期需要平铺的列
            cols_to_pull = [net_join_key, int_pub_name, net_clicks, net_gmv, net_comm]
            rename_dict = {
                net_clicks: f"【{p_name}】联盟点击",
                net_gmv: f"【{p_name}】联盟GMV",
                net_comm: f"【{p_name}】联盟佣金",
            }

            if int_clicks and int_clicks in p_df.columns:
                cols_to_pull.append(int_clicks)
                rename_dict[int_clicks] = f"【{p_name}】后台点击"

            # 🌟 新增：如果选择了媒体后台佣金列，将其平铺到对比表
            if int_comm and int_comm in p_df.columns:
                cols_to_pull.append(int_comm)
                rename_dict[int_comm] = f"【{p_name}】媒体后台佣金"

            sub_df = (
                p_df[cols_to_pull]
                .rename(columns=rename_dict)
                .drop_duplicates()
            )
            base_df = pd.merge(
                base_df,
                sub_df,
                on=[net_join_key, int_pub_name],
                how="outer",
            ).fillna(0)

        # 动态生成 Column Config
        wide_configs = {}
        for col in base_df.columns:
            if any(kw in col for kw in ["GMV", "佣金", "费用", "花费", "支出"]):
                wide_configs[col] = st.column_config.NumberColumn(
                    format="$%.2f"
                )
            elif "点击" in col:
                wide_configs[col] = st.column_config.NumberColumn(format="%d")

        st.dataframe(base_df, column_config=wide_configs, use_container_width=True)

        st.download_button(
            label="📥 下载多周期对比大表 CSV",
            data=base_df.to_csv(index=False).encode("utf-8-sig"),
            file_name="multi_period_comparison_large_table.csv",
            mime="text/csv",
        )

   # ------------------------------------------------------------------
    # Tab 2: 分周期独立明细
    # ------------------------------------------------------------------
    with tab2:
        st.subheader("📂 分周期独立对齐明细")

        # 子选项卡：选择具体的周期
        selected_p_name = st.selectbox(
            "选择查看的周期", [p["name"] for p in processed_periods]
        )
        target_p = next(
            p for p in processed_periods if p["name"] == selected_p_name
        )
        t_df = target_p["merged_df"].copy()

        # 获取原始后台表和联盟表
        df_int_raw = target_p["df_int"]
        df_net_raw = target_p["df_net"]

        # 校验后台佣金列是否存在于后台表中
        has_int_comm = bool(int_comm and int_comm in df_int_raw.columns)

        # --------------------------------------------------------------
        # 1. 大盘汇总卡片 (严格区分后台表 df_int 与联盟表 df_net)
        # --------------------------------------------------------------
        # 联盟全盘汇总数据（来自 df_net）
        total_period_clicks = pd.to_numeric(df_net_raw[net_clicks], errors="coerce").fillna(0).sum()
        total_period_sales = pd.to_numeric(df_net_raw[net_sales], errors="coerce").fillna(0).sum()
        total_period_gmv = pd.to_numeric(df_net_raw[net_gmv], errors="coerce").fillna(0).sum()
        total_period_comm = pd.to_numeric(df_net_raw[net_comm], errors="coerce").fillna(0).sum()

        if has_int_comm:
            m1, m2, m3, m4, m5 = st.columns(5)
            # 严格对原始后台表 df_int 的 int_comm 列进行加总
            total_int_comm = pd.to_numeric(df_int_raw[int_comm], errors="coerce").fillna(0).sum()
        else:
            m1, m2, m3, m4 = st.columns(4)

        m1.metric("总点击", f"{int(total_period_clicks):,}")
        m2.metric("总订单", f"{int(total_period_sales):,}")
        m3.metric("总 GMV", f"${total_period_gmv:,.2f}")
        m4.metric("商家联盟总佣金", f"${total_period_comm:,.2f}")

        if has_int_comm:
            m5.metric("媒体后台总佣金", f"${total_int_comm:,.2f}")

            # 🛠️ 简单安全校验：如果算出来的数字和联盟总佣金完全一样，在侧边栏或页面上方提示
            if total_int_comm == total_period_comm and total_int_comm > 0:
                st.warning(f"⚠️ 提示：当前测得【媒体后台总佣金】与【商家联盟总佣金】完全一致 (${total_int_comm:,.2f})，请检查侧边栏/设置中的『内部后台佣金列』映射配置是否误选成了联盟佣金列！")
        # --------------------------------------------------------------
        # 2. 计算占比指标（单个媒体 int_comm / 商家联盟总佣金 net_comm）
        # --------------------------------------------------------------
        if has_int_comm and int_comm in t_df.columns:
            # 保证参与计算的列为数值型
            t_df[int_comm] = pd.to_numeric(t_df[int_comm], errors="coerce").fillna(0)
            t_df[net_comm] = pd.to_numeric(t_df[net_comm], errors="coerce").fillna(0)

            # 算指标 1：占商家总佣金 (%) = 单个媒体后台佣金 / 该商家联盟总佣金
            t_df["占商家总佣金 (%)"] = (
                t_df[int_comm] / t_df[net_comm].replace(0, pd.NA) * 100
            ).fillna(0)

            # 算指标 2：占联盟该周期总佣金 (%) = 单个媒体后台佣金 / 联盟全盘总佣金
            t_df["占联盟该周期总佣金 (%)"] = (
                t_df[int_comm] / (total_period_comm if total_period_comm != 0 else pd.NA) * 100
            ).fillna(0)

        # --------------------------------------------------------------
        # 3. 构建展示列与格式化配置
        # --------------------------------------------------------------
        disp_cols = [
            net_join_key,
            int_pub_name,
            net_clicks,
            net_sales,
            net_gmv,
            net_comm,
        ]

        p_configs = {
            net_clicks: st.column_config.NumberColumn("联盟点击", format="%d"),
            net_sales: st.column_config.NumberColumn("联盟订单", format="%d"),
            net_gmv: st.column_config.NumberColumn("联盟 GMV", format="$%.2f"),
            net_comm: st.column_config.NumberColumn("商家联盟总佣金", format="$%.2f"),
            "CVR (%)": st.column_config.NumberColumn(format="%.2f%%"),
            "AOV ($)": st.column_config.NumberColumn(format="$%.2f"),
        }

        # 如果有后台媒体佣金，加入媒体佣金及占比列
        if has_int_comm and int_comm in t_df.columns:
            disp_cols.extend([int_comm, "占商家总佣金 (%)", "占联盟该周期总佣金 (%)"])
            p_configs[int_comm] = st.column_config.NumberColumn(
                "媒体后台佣金", format="$%.2f"
            )
            p_configs["占商家总佣金 (%)"] = st.column_config.NumberColumn(
                "占商家总佣金", format="%.2f%%"
            )
            p_configs["占联盟该周期总佣金 (%)"] = st.column_config.NumberColumn(
                "占联盟总佣金", format="%.2f%%"
            )

        disp_cols.extend(["CVR (%)", "AOV ($)"])

        # 如果有后台点击列，加入展示与差异数
        if int_clicks and int_clicks in t_df.columns:
            disp_cols.extend([int_clicks, "点击差异数", "点击差异率 (%)"])
            p_configs[int_clicks] = st.column_config.NumberColumn(
                "后台点击", format="%d"
            )
            p_configs["点击差异数"] = st.column_config.NumberColumn(
                format="%+d"
            )
            p_configs["点击差异率 (%)"] = st.column_config.NumberColumn(
                format="%+.2f%%"
            )

        # --------------------------------------------------------------
        # 4. 渲染数据表格与下载按钮
        # --------------------------------------------------------------
        final_disp_cols = [c for c in disp_cols if c in t_df.columns]

        st.dataframe(
            t_df[final_disp_cols],
            column_config=p_configs,
            use_container_width=True,
        )

        st.download_button(
            label=f"📥 下载【{selected_p_name}】对齐明细 CSV",
            data=t_df[final_disp_cols].to_csv(index=False).encode("utf-8-sig"),
            file_name=f"aligned_detail_{target_p['alias']}.csv",
            mime="text/csv",
        )
  # ------------------------------------------------------------------
# Tab 3: 智能数据分析与诊断看板 (核心模块)
# ------------------------------------------------------------------
    with tab3:
        st.subheader("🧠 联盟与商家智能诊断看板")

        # 取最新周期 (Curr) 与 上一周期 (Prev)
        curr_p = processed_periods[-1]
        prev_p = (
            processed_periods[-2]
            if len(processed_periods) >= 2
            else processed_periods[0]
        )

        # 1. 确保定义了清洗函数
        def _sanitize_df(df):
            if df is None or df.empty:
                return pd.DataFrame()
            df_clean = df.copy()
            for col in [net_join_key, int_pub_name]:
                if col and col in df_clean.columns:
                    df_clean[col] = (
                        df_clean[col].astype(str).str.replace(r"\.0$", "", regex=True)
                    )
            num_cols = [net_gmv, net_comm, net_clicks, net_sales]
            for col in num_cols:
                if col and col in df_clean.columns:
                    df_clean[col] = pd.to_numeric(
                        df_clean[col], errors="coerce"
                    ).fillna(0)
            return df_clean


        # 2. 确保在调用 curr_net 前完成了变量赋值（重点检查这几行）
        curr_df = _sanitize_df(curr_p.get("merged_df"))
        prev_df = _sanitize_df(prev_p.get("merged_df"))

        curr_net = _sanitize_df(curr_p.get("df_net"))  # <--- 必须有这一行！
        prev_net = _sanitize_df(prev_p.get("df_net"))  # <--- 必须有这一行！

        # --------------------------------------------------------------
        # 模块 1：联盟大盘、商家升降榜与媒体升降榜（环比/趋势）
        # --------------------------------------------------------------
        st.markdown("#### 1. 联盟收益大盘与商家/媒体升降榜")

        c_gmv_curr = curr_p["df_net"][net_gmv].fillna(0).sum()
        c_gmv_prev = prev_p["df_net"][net_gmv].fillna(0).sum()
        gmv_mom = (
            ((c_gmv_curr - c_gmv_prev) / c_gmv_prev * 100)
            if c_gmv_prev > 0
            else 0
        )

        c_comm_curr = curr_p["df_net"][net_comm].fillna(0).sum()
        c_comm_prev = prev_p["df_net"][net_comm].fillna(0).sum()
        comm_mom = (
            ((c_comm_curr - c_comm_prev) / c_comm_prev * 100)
            if c_comm_prev > 0
            else 0
        )

        curr_clicks = curr_p["df_net"][net_clicks].fillna(0).sum()
        prev_clicks = prev_p["df_net"][net_clicks].fillna(0).sum()
        curr_sales = curr_p["df_net"][net_sales].fillna(0).sum()

        c1, c2, c3, c4 = st.columns(4)
        c1.metric(
            f"最新周期 GMV ({curr_p['alias']})",
            f"${c_gmv_curr:,.2f}",
            f"{gmv_mom:+.1f}% 环比",
        )
        c2.metric(
            f"最新周期佣金 ({curr_p['alias']})",
            f"${c_comm_curr:,.2f}",
            f"{comm_mom:+.1f}% 环比",
        )
        c3.metric(
            "总点击量",
            f"{int(curr_clicks):,}",
            f"{int(curr_clicks - prev_clicks):+,}",
        )
        c4.metric(
            "整体 CVR",
            f"{curr_sales / max(1, curr_clicks) * 100:.2f}%",
        )

        # --------------------------------------------------------------
        # A. 商家升降榜计算 (基于 df_net)
        # --------------------------------------------------------------
        curr_net_df = curr_p["df_net"].copy()
        prev_net_df = prev_p["df_net"].copy()

        curr_m_comm = (
            curr_net_df.groupby(net_join_key)[net_comm]
            .sum()
            .reset_index()
            .fillna(0)
        )
        prev_m_comm = (
            prev_net_df.groupby(net_join_key)[net_comm]
            .sum()
            .reset_index()
            .fillna(0)
        )

        m_comp = pd.merge(
            curr_m_comm,
            prev_m_comm,
            on=net_join_key,
            how="outer",
            suffixes=("_本期", "_上期"),
        ).fillna(0)

        m_comp[f"{net_comm}_本期"] = pd.to_numeric(m_comp[f"{net_comm}_本期"], errors="coerce").fillna(0)
        m_comp[f"{net_comm}_上期"] = pd.to_numeric(m_comp[f"{net_comm}_上期"], errors="coerce").fillna(0)
        m_comp["COMM增量"] = (
            m_comp[f"{net_comm}_本期"] - m_comp[f"{net_comm}_上期"]
        ).fillna(0)

        # 渲染商家升降榜
        col_top, col_bot = st.columns(2)
        with col_top:
            st.markdown("**📈 商家 COMM 增长 Top 5 (主要拉动力量)**")
            top_5 = m_comp.sort_values(by="COMM增量", ascending=False).head(5)
            st.dataframe(
                top_5[
                    [
                        net_join_key,
                        f"{net_comm}_上期",
                        f"{net_comm}_本期",
                        "COMM增量",
                    ]
                ],
                column_config={
                    f"{net_comm}_上期": st.column_config.NumberColumn(
                        "上期 COMM", format="$%.2f"
                    ),
                    f"{net_comm}_本期": st.column_config.NumberColumn(
                        "本期 COMM", format="$%.2f"
                    ),
                    "COMM增量": st.column_config.NumberColumn(
                        "增量", format="+$%.2f"
                    ),
                },
                use_container_width=True,
            )

        with col_bot:
            st.markdown("**📉 商家 COMM 下滑 Top 5 (主要出血点)**")
            bot_5 = m_comp.sort_values(by="COMM增量", ascending=True).head(5)
            st.dataframe(
                bot_5[
                    [
                        net_join_key,
                        f"{net_comm}_上期",
                        f"{net_comm}_本期",
                        "COMM增量",
                    ]
                ],
                column_config={
                    f"{net_comm}_上期": st.column_config.NumberColumn(
                        "上期 COMM", format="$%.2f"
                    ),
                    f"{net_comm}_本期": st.column_config.NumberColumn(
                        "本期 COMM", format="$%.2f"
                    ),
                    "COMM增量": st.column_config.NumberColumn(
                        "跌幅", format="$%.2f"
                    ),
                },
                use_container_width=True,
            )

        # --------------------------------------------------------------
        # B. 新增：媒体升降榜计算 (基于内部后台表 df_int)
        # --------------------------------------------------------------
        has_int_comm = (
            int_comm
            and int_pub_name
            and int_comm in curr_p["df_int"].columns
            and int_pub_name in curr_p["df_int"].columns
        )

        if has_int_comm:
            st.markdown("---")
            curr_int_df = curr_p["df_int"].copy()
            prev_int_df = prev_p["df_int"].copy()

            # 按媒体名称分组聚合佣金
            curr_p_comm = (
                curr_int_df.groupby(int_pub_name)[int_comm]
                .sum()
                .reset_index()
                .fillna(0)
            )
            prev_p_comm = (
                prev_int_df.groupby(int_pub_name)[int_comm]
                .sum()
                .reset_index()
                .fillna(0)
            )

            p_comp = pd.merge(
                curr_p_comm,
                prev_p_comm,
                on=int_pub_name,
                how="outer",
                suffixes=("_本期", "_上期"),
            ).fillna(0)

            p_comp[f"{int_comm}_本期"] = pd.to_numeric(p_comp[f"{int_comm}_本期"], errors="coerce").fillna(0)
            p_comp[f"{int_comm}_上期"] = pd.to_numeric(p_comp[f"{int_comm}_上期"], errors="coerce").fillna(0)
            p_comp["COMM增量"] = (
                p_comp[f"{int_comm}_本期"] - p_comp[f"{int_comm}_上期"]
            ).fillna(0)

            # 渲染媒体升降榜
            col_pub_top, col_pub_bot = st.columns(2)
            with col_pub_top:
                st.markdown("**🚀 媒体 COMM 增长 Top 5 (核心增量渠道)**")
                pub_top_5 = p_comp.sort_values(by="COMM增量", ascending=False).head(5)
                st.dataframe(
                    pub_top_5[
                        [
                            int_pub_name,
                            f"{int_comm}_上期",
                            f"{int_comm}_本期",
                            "COMM增量",
                        ]
                    ],
                    column_config={
                        int_pub_name: st.column_config.TextColumn("媒体名称"),
                        f"{int_comm}_上期": st.column_config.NumberColumn(
                            "上期佣金", format="$%.2f"
                        ),
                        f"{int_comm}_本期": st.column_config.NumberColumn(
                            "本期佣金", format="$%.2f"
                        ),
                        "COMM增量": st.column_config.NumberColumn(
                            "增量", format="+$%.2f"
                        ),
                    },
                    use_container_width=True,
                )

            with col_pub_bot:
                st.markdown("**⚠️ 媒体 COMM 下滑 Top 5 (警惕流失/异常)**")
                pub_bot_5 = p_comp.sort_values(by="COMM增量", ascending=True).head(5)
                st.dataframe(
                    pub_bot_5[
                        [
                            int_pub_name,
                            f"{int_comm}_上期",
                            f"{int_comm}_本期",
                            "COMM增量",
                        ]
                    ],
                    column_config={
                        int_pub_name: st.column_config.TextColumn("媒体名称"),
                        f"{int_comm}_上期": st.column_config.NumberColumn(
                            "上期佣金", format="$%.2f"
                        ),
                        f"{int_comm}_本期": st.column_config.NumberColumn(
                            "本期佣金", format="$%.2f"
                        ),
                        "COMM增量": st.column_config.NumberColumn(
                            "跌幅", format="$%.2f"
                        ),
                    },
                    use_container_width=True,
                )

        st.markdown("---")
        # --------------------------------------------------------------
        # 模块 2：头部创收媒体动态漂移与替换 (Publisher Shift)
        # --------------------------------------------------------------
        st.markdown("#### 2. 头部创收媒体动态漂移与结构替换")

        # 1. 提取本期与上期的全量商家列表（结合 df_net 与 df_int 保证不遗漏）
        curr_m_net = (
            curr_p["df_net"][net_join_key].dropna().unique().tolist()
            if (not curr_p["df_net"].empty and net_join_key in curr_p["df_net"].columns)
            else []
        )
        prev_m_net = (
            prev_p["df_net"][net_join_key].dropna().unique().tolist()
            if (not prev_p["df_net"].empty and net_join_key in prev_p["df_net"].columns)
            else []
        )
        
        # 同时检查内部表是否有商家关联字段
        curr_m_int = (
            curr_p["df_int"][int_join_key].dropna().unique().tolist()
            if (not curr_p["df_int"].empty and int_join_key and int_join_key in curr_p["df_int"].columns)
            else []
        )
        prev_m_int = (
            prev_p["df_int"][int_join_key].dropna().unique().tolist()
            if (not prev_p["df_int"].empty and int_join_key and int_join_key in prev_p["df_int"].columns)
            else []
        )

        all_merchants = sorted(
            list(set([str(x) for x in (curr_m_net + prev_m_net + curr_m_int + prev_m_int)]))
        )

        selected_m = st.selectbox(
            "选择要深入调取的商家 (MID/Merchant)", ["全联盟大盘"] + all_merchants
        )

        # 2. 媒体分析必须严格基于内部后台表 (df_int) 及其专属字段 (int_pub_name & int_comm)
        curr_int_raw = curr_p["df_int"].copy()
        prev_int_raw = prev_p["df_int"].copy()

        # 根据用户选择的商家筛选 df_int
        if selected_m != "全联盟大盘":
            if int_join_key and int_join_key in curr_int_raw.columns:
                curr_int_sub = curr_int_raw[curr_int_raw[int_join_key].astype(str) == selected_m]
            else:
                curr_int_sub = pd.DataFrame()

            if int_join_key and int_join_key in prev_int_raw.columns:
                prev_int_sub = prev_int_raw[prev_int_raw[int_join_key].astype(str) == selected_m]
            else:
                prev_int_sub = pd.DataFrame()
        else:
            curr_int_sub = curr_int_raw
            prev_int_sub = prev_int_raw

        # 3. 媒体层面按 int_comm (内部媒体佣金) 进行聚合计算
        has_required_cols = (
            int_pub_name 
            and int_comm 
            and (int_pub_name in curr_int_raw.columns or int_pub_name in prev_int_raw.columns)
            and (int_comm in curr_int_raw.columns or int_comm in prev_int_raw.columns)
        )

        if has_required_cols:
            pub_c = (
                curr_int_sub.groupby(int_pub_name, as_index=False)[int_comm]
                .sum()
                .rename(columns={int_comm: "本期佣金"})
                if (not curr_int_sub.empty and int_pub_name in curr_int_sub.columns and int_comm in curr_int_sub.columns)
                else pd.DataFrame(columns=[int_pub_name, "本期佣金"])
            )
            pub_p = (
                prev_int_sub.groupby(int_pub_name, as_index=False)[int_comm]
                .sum()
                .rename(columns={int_comm: "上期佣金"})
                if (not prev_int_sub.empty and int_pub_name in prev_int_sub.columns and int_comm in prev_int_sub.columns)
                else pd.DataFrame(columns=[int_pub_name, "上期佣金"])
            )

            pub_m = pd.merge(pub_c, pub_p, on=int_pub_name, how="outer").fillna(0)
            pub_m[int_pub_name] = pub_m[int_pub_name].astype(str)

            # 数值类型强转防错
            pub_m["本期佣金"] = pd.to_numeric(pub_m["本期佣金"], errors="coerce").fillna(0)
            pub_m["上期佣金"] = pd.to_numeric(pub_m["上期佣金"], errors="coerce").fillna(0)

            # 计算佣金贡献占比 (%)
            total_c_comm = max(1.0, float(pub_m["本期佣金"].sum()))
            total_p_comm = max(1.0, float(pub_m["上期佣金"].sum()))

            pub_m["佣金占比_本期"] = (pub_m["本期佣金"] / total_c_comm) * 100
            pub_m["佣金占比_上期"] = (pub_m["上期佣金"] / total_p_comm) * 100

            # 评估主力创收媒体是否易主
            top_pub_c = (
                str(
                    pub_m.sort_values(by="本期佣金", ascending=False).iloc[0][
                        int_pub_name
                    ]
                )
                if (not pub_m.empty and pub_m["本期佣金"].sum() > 0)
                else "无"
            )
            top_pub_p = (
                str(
                    pub_m.sort_values(by="上期佣金", ascending=False).iloc[0][
                        int_pub_name
                    ]
                )
                if (not pub_m.empty and pub_m["上期佣金"].sum() > 0)
                else "无"
            )

            if top_pub_c != top_pub_p and top_pub_c != "无" and top_pub_p != "无":
                st.warning(
                    f"⚠️ **主力创收媒体发生易主**！【{selected_m}】的上期头号佣金贡献媒体为 **{top_pub_p}**，而本期已切换为 **{top_pub_c}**。"
                )
            else:
                st.success(
                    f"✅ 主力创收媒体保持稳定：【{selected_m}】的头号佣金贡献媒体均为 **{top_pub_c}**。"
                )

            # 4. 图表渲染：Top 8 媒体跨期对比
            plot_df = pub_m.sort_values(by="本期佣金", ascending=False).head(8).copy()

            fig_pub = px.bar(
                plot_df,
                x=int_pub_name,
                y=["上期佣金", "本期佣金"],
                barmode="group",
                title=f"【{selected_m}】Top 8 媒体佣金支出跨期对比",
                labels={int_pub_name: "媒体 ID / 名称", "value": "媒体佣金支出 ($)"},
            )
            fig_pub.update_xaxes(type="category")  # 强制 X 轴渲染为分类轴

            st.plotly_chart(fig_pub, use_container_width=True)
        else:
            st.info("💡 当前后台表中未配置媒体名称列 (`int_pub_name`) 或媒体佣金列 (`int_comm`)，无法进行媒体漂移分析。")
        # --------------------------------------------------------------
        # 模块 3：联盟健康度诊断与跑冒滴漏预警
        # --------------------------------------------------------------
        st.markdown("#### 3. 联盟健康度诊断与跑冒滴漏预警")

        if int_clicks and (not curr_df.empty) and (int_clicks in curr_df.columns):
            h_col1, h_col2 = st.columns(2)

            with h_col1:
                st.markdown("**🔴 异常预警：后台点击远高于上游 (跳转链路漏失/刷量)**")
                if "点击差异率 (%)" in curr_df.columns and "点击差异数" in curr_df.columns:
                    curr_df["点击差异率 (%)"] = pd.to_numeric(curr_df["点击差异率 (%)"], errors="coerce").fillna(0)
                    leak_df = curr_df[curr_df["点击差异率 (%)"] > 30].sort_values(
                        by="点击差异数", ascending=False
                    )
                else:
                    leak_df = pd.DataFrame()

                if not leak_df.empty:
                    st.dataframe(
                        leak_df[
                            [
                                net_join_key,
                                int_pub_name,
                                net_clicks,
                                int_clicks,
                                "点击差异率 (%)",
                            ]
                        ],
                        use_container_width=True,
                        hide_index=True,
                    )
                else:
                    st.success("🎉 当前周期未检测到点击差异率 > 30% 的严重跑冒滴漏现象！")

            with h_col2:
                st.markdown("**🟡 依赖度预警：商家佣金收益过度依赖单一媒体**")
                # 逻辑彻底重写：按商家 + 媒体统计佣金，再对商家求佣金总量算依赖占比
                high_dep = (
                    curr_df.groupby([net_join_key, int_pub_name], as_index=False)[net_comm]
                    .sum()
                )
                merchant_totals = (
                    high_dep.groupby(net_join_key, as_index=False)[net_comm]
                    .sum()
                    .rename(columns={net_comm: "商家总佣金"})
                )
                high_dep = pd.merge(high_dep, merchant_totals, on=net_join_key)
                
                high_dep[net_join_key] = high_dep[net_join_key].astype(str)
                high_dep[int_pub_name] = high_dep[int_pub_name].astype(str)
                
                high_dep["佣金占比 (%)"] = (
                    high_dep[net_comm]
                    / high_dep["商家总佣金"].replace(0, np.nan)
                    * 100
                ).fillna(0)

                # 条件：单一媒体带来该商家 70% 以上的佣金，且商家总佣金规模 > $50 (剔除微量无意义数据)
                risky_m = high_dep[
                    (high_dep["佣金占比 (%)"] > 70) & (high_dep["商家总佣金"] > 50)
                ].sort_values(by="商家总佣金", ascending=False)

                if not risky_m.empty:
                    st.dataframe(
                        risky_m[
                            [
                                net_join_key,
                                int_pub_name,
                                net_comm,
                                "商家总佣金",
                                "佣金占比 (%)",
                            ]
                        ],
                        column_config={
                            net_comm: st.column_config.NumberColumn("媒体贡献佣金", format="$%.2f"),
                            "商家总佣金": st.column_config.NumberColumn("商家总佣金", format="$%.2f"),
                            "佣金占比 (%)": st.column_config.NumberColumn("收益占比", format="%.1f%%")
                        },
                        use_container_width=True,
                        hide_index=True,
                    )
                else:
                    st.info("💡 商家佣金结构分布相对均匀，暂无极端依赖单一媒体的情况。")
        else:
            st.info(
                "💡 未配置内部后台点击列，跳转差异诊断已自动跳过。集中度健康诊断正常运行中。"
            )

        st.markdown("---")

        # --------------------------------------------------------------
        # 模块 4：月度目标进度与动态 Pacing 诊断 (佣金维度)
        # --------------------------------------------------------------
        st.markdown("#### 4. 月度目标进度与动态 Pacing 诊断")

        # 4.1 时间锚点、目标与佣金基准配置
        p_col_1, p_col_2, p_col_3, p_col_4 = st.columns(4)

        with p_col_1:
            target_comm = st.number_input(
                "🎯 设置本月目标佣金 ($)",
                min_value=1.0,
                value=10000.0,
                step=1000.0,
            )

        with p_col_2:
            days_in_month = st.number_input(
                "📅 本月自然总天数", min_value=28, max_value=31, value=31
            )

        with p_col_3:
            # 允许自定义当前数据集代表的天数长度（例如 8.4-8.11 即为 8 天）
            default_days = int(curr_p.get("days", 7))
            sample_days_count = st.number_input(
                "📊 当前数据包含天数 (天)",
                min_value=1,
                max_value=31,
                value=max(1, default_days),
                help="如上传的数据是 8.4~8.11，则此处填 8 天，系统将据此计算日均流水。",
            )

        with p_col_4:
            # 当前截至本月的第几天（用于计算时间消耗进度）
            data_end_day = st.number_input(
                "⏱️ 当前截至月内第几天",
                min_value=1,
                max_value=int(days_in_month),
                value=min(11, int(days_in_month)),
                help="如上传数据截至 8月11日，则此处填 11。",
            )

        # 允许手动调整/校准本期佣金基数
        actual_comm = st.number_input(
            "💰 本期实际校验佣金 ($)",
            min_value=0.0,
            value=float(c_comm_curr),
            step=100.0,
            help="默认自动读取大盘佣金，若数据切片有偏差，可在此手动修改为真实佣金金额。",
        )

        # 4.2 时间进度与完成度双标尺计算
        # 每日平均流水 = 当前数据总佣金 / 数据覆盖天数
        daily_comm = actual_comm / max(1, sample_days_count)

        # 全月预测 = 日均流水 * 本月总天数
        projected_comm = daily_comm * days_in_month

        # 进度指标
        time_progress = (data_end_day / days_in_month) * 100  # 时间已消耗 %
        realized_progress = (
            actual_comm / max(1.0, target_comm)
        ) * 100  # 业绩已完成 %
        projected_rate = (
            projected_comm / max(1.0, target_comm)
        ) * 100  # 预估月底完成 %
        comm_gap = target_comm - projected_comm

        # 展示双进度条与核心卡片
        st.markdown(
            f"**时间消耗进度**：`第 {data_end_day}/{days_in_month} 天 ({time_progress:.1f}%)` | "
            f"**当前核算佣金**：`${actual_comm:,.2f} / ${target_comm:,.2f} ({realized_progress:.1f}%)` | "
            f"**推算日均**：`${daily_comm:,.2f}/天`"
        )

        # 进度条对比
        st.progress(
            min(1.0, max(0.0, actual_comm / max(1.0, target_comm))),
            text=f"当前已完成目标: {realized_progress:.1f}% (时间基准线: {time_progress:.1f}%)",
        )

        # 4.3 Pacing 状态判定与预警输出
        if projected_comm >= target_comm:
            st.success(
                f"🚀 **Pacing 状态良好 (On Track)**：按当前样本推算的日均佣金（${daily_comm:,.2f}/天），"
                f"月底预计完成 **${projected_comm:,.2f}**，目标完成率 **{projected_rate:.1f}%**。"
            )
        else:
            st.error(
                f"🚨 **Pacing 滞后预警 (Behind Pace)**：按当前样本推算的日均佣金（${daily_comm:,.2f}/天），"
                f"预估月底完成 **${projected_comm:,.2f}**，预计缺口 **${comm_gap:,.2f}** (目标完成率 **{projected_rate:.1f}%**)。"
            )

            # ----------------------------------------------------------
            # 4.4 归因诊断树 (Attribution Tree) - 当 Pacing 滞后或降幅较大时触发
            # ----------------------------------------------------------
            with st.expander("🔍 **点击展开：佣金未达标四维归因诊断**", expanded=True):
                # =========================================================
                # 0. 基础过滤：根据当前选择的商家 selected_m 准备数据子集
                # =========================================================
                if selected_m == "全联盟大盘" or not selected_m:
                    sub_curr_net = curr_net
                    sub_prev_net = prev_net
                    sub_curr_df = curr_df
                    sub_prev_df = prev_df
                else:
                    # 强制转 string 匹配，防止 Int/Float 格式不一致导致的过滤失效
                    sub_curr_net = (
                        curr_net[curr_net[net_join_key].astype(str) == str(selected_m)]
                        if not curr_net.empty and net_join_key in curr_net.columns
                        else pd.DataFrame()
                    )
                    sub_prev_net = (
                        prev_net[prev_net[net_join_key].astype(str) == str(selected_m)]
                        if not prev_net.empty and net_join_key in prev_net.columns
                        else pd.DataFrame()
                    )

                    sub_curr_df = (
                        curr_df[curr_df[net_join_key].astype(str) == str(selected_m)]
                        if not curr_df.empty and net_join_key in curr_df.columns
                        else pd.DataFrame()
                    )
                    sub_prev_df = (
                        prev_df[prev_df[net_join_key].astype(str) == str(selected_m)]
                        if not prev_df.empty and net_join_key in prev_df.columns
                        else pd.DataFrame()
                    )


                # --- 维度 1: 漏斗因子拆解 (Clicks vs CVR vs eCPC) ---
                st.markdown("**1️⃣ 漏斗因子拆解（流量 vs 转化率 vs 佣金效率）**")

                # 统一提取【全联盟大盘表】中的数据，保证分子分母口径一致
                c_comm_curr = (
                    float(sub_curr_net[net_comm].sum())
                    if (not sub_curr_net.empty and net_comm in sub_curr_net.columns)
                    else 0.0
                )
                c_comm_prev = (
                    float(sub_prev_net[net_comm].sum())
                    if (not sub_prev_net.empty and net_comm in sub_prev_net.columns)
                    else 0.0
                )

                curr_clicks_val = (
                    float(sub_curr_net[net_clicks].sum())
                    if (not sub_curr_net.empty and net_clicks in sub_curr_net.columns)
                    else 0.0
                )
                prev_clicks_val = (
                    float(sub_prev_net[net_clicks].sum())
                    if (not sub_prev_net.empty and net_clicks in sub_prev_net.columns)
                    else 0.0
                )

                curr_sales_val = (
                    float(sub_curr_net[net_sales].sum())
                    if (not sub_curr_net.empty and net_sales in sub_curr_net.columns)
                    else 0.0
                )
                prev_sales_val = (
                    float(sub_prev_net[net_sales].sum())
                    if (not sub_prev_net.empty and net_sales in sub_prev_net.columns)
                    else 0.0
                )

                # 准确计算 eCPC 与 CVR
                prev_ecpc = c_comm_prev / max(1.0, prev_clicks_val)
                curr_ecpc = c_comm_curr / max(1.0, curr_clicks_val)

                click_delta_pct = (
                    (curr_clicks_val - prev_clicks_val) / max(1.0, prev_clicks_val)
                ) * 100
                ecpc_delta_pct = (
                    (curr_ecpc - prev_ecpc) / max(0.0001, prev_ecpc)
                ) * 100

                curr_cvr = (curr_sales_val / max(1.0, curr_clicks_val)) * 100
                prev_cvr = (prev_sales_val / max(1.0, prev_clicks_val)) * 100

                f_col1, f_col2, f_col3 = st.columns(3)
                f_col1.metric(
                    "点击量 (Clicks) 环比",
                    f"{int(curr_clicks_val):,}",
                    f"{click_delta_pct:+.1f}%",
                )
                f_col2.metric(
                    "单次点击收益 (eCPC)", f"${curr_ecpc:.3f}", f"{ecpc_delta_pct:+.1f}%"
                )
                f_col3.metric(
                    "全盘 CVR", f"{curr_cvr:.2f}%", f"{curr_cvr - prev_cvr:+.2f}%"
                )

                # 主因判定
                if click_delta_pct < -5 and ecpc_delta_pct >= -5:
                    st.warning(
                        "⚠️ **核心瓶颈：流量供给不足**。eCPC 单击收益稳定，但总点击量下滑明显，导致佣金基数收缩。"
                    )
                elif ecpc_delta_pct < -5 and click_delta_pct >= -5:
                    st.warning(
                        "⚠️ **核心瓶颈：佣金转化效率变差**。流量基础尚可，但 CVR 下滑或高佣金产品/商家占比降低拉低了 eCPC。"
                    )
                elif click_delta_pct < -5 and ecpc_delta_pct < -5:
                    st.error(
                        "🚨 **双重受挫：流量与变现效率同步下滑**。需同步排查拓量渠道与高变现商家。"
                    )
                else:
                    st.info(
                        "💡 环比指标波动平稳，缺口主要受月度目标基数设定影响。"
                    )

                st.markdown("---")

                # --- 维度 2: 商家侧佣金出血点分析 (Merchant Drag) ---
                st.markdown("**2️⃣ 商家侧佣金下滑 Top 3 (主要出血点)**")

                # 直接从全量大盘表 (curr_net / prev_net) 中按商家分组，避免明细缺失导致的加总错误
                c_m_comm = (
                    curr_net.groupby(net_join_key, as_index=False)[net_comm]
                    .sum()
                    .rename(columns={net_comm: "本期佣金"})
                    if (not curr_net.empty and net_join_key in curr_net.columns)
                    else pd.DataFrame()
                )
                p_m_comm = (
                    prev_net.groupby(net_join_key, as_index=False)[net_comm]
                    .sum()
                    .rename(columns={net_comm: "上期佣金"})
                    if (not prev_net.empty and net_join_key in prev_net.columns)
                    else pd.DataFrame()
                )

                drop_merchants = pd.DataFrame()
                if not c_m_comm.empty or not p_m_comm.empty:
                    m_comm_merge = pd.merge(
                        c_m_comm, p_m_comm, on=net_join_key, how="outer"
                    ).fillna(0)
                    m_comm_merge[net_join_key] = m_comm_merge[net_join_key].astype(str)
                    m_comm_merge["佣金变动"] = (
                        m_comm_merge["本期佣金"] - m_comm_merge["上期佣金"]
                    )

                    drop_merchants = m_comm_merge.sort_values(
                        by="佣金变动", ascending=True
                    ).head(3)

                    st.dataframe(
                        drop_merchants[
                            [net_join_key, "上期佣金", "本期佣金", "佣金变动"]
                        ],
                        column_config={
                            net_join_key: "商家 MID/名称",
                            "上期佣金": st.column_config.NumberColumn(format="$%.2f"),
                            "本期佣金": st.column_config.NumberColumn(format="$%.2f"),
                            "佣金变动": st.column_config.NumberColumn(
                                "佣金缺口", format="$%.2f"
                            ),
                        },
                        use_container_width=True,
                    )
                else:
                    st.write("暂无足够的商家跨期对比数据。")

                st.markdown("---")

                # --- 维度 3: 媒体侧流量与佣金断流排查 (基于原始后台总表汇总) ---
                # --- 维度 3: 媒体侧流量与佣金断流排查 (使用媒体级明细：ALL佣金) ---
                st.markdown("**3️⃣ 媒体侧流量与佣金断流排查**")

                if (
                    not curr_df.empty
                    and not prev_df.empty
                    and int_pub_name in curr_df.columns
                    and int_pub_name in prev_df.columns
                ):
                    c_raw = curr_df.copy()
                    p_raw = prev_df.copy()

                    # 1. 动态寻找真正的【媒体级佣金列】（优先锁定 "ALL佣金"）
                    def get_real_pub_comm_col(df):
                        # 严格排除商家汇总列如 estcommission
                        for col in df.columns:
                            col_str = str(col).strip()
                            if col_str == "ALL佣金" or "all佣金" in col_str.lower():
                                return col
                        # 次优寻找包含 'pub' 或 'media' 的佣金列
                        for col in df.columns:
                            col_str = str(col).strip().lower()
                            if "comm" in col_str and "est" not in col_str:
                                return col
                        return None

                    c_pub_comm_col = get_real_pub_comm_col(c_raw)
                    p_pub_comm_col = get_real_pub_comm_col(p_raw)

                    if not c_pub_comm_col or not p_pub_comm_col:
                        st.warning(
                            f"⚠️ 未在后台数据表中找到【ALL佣金】列（本期找到: {c_pub_comm_col}, 上期找到: {p_pub_comm_col}），请检查表头名称。"
                        )
                    else:
                        # 2. 清理媒体 ID 与数值类型
                        c_raw[int_pub_name] = (
                            c_raw[int_pub_name]
                            .astype(str)
                            .str.replace(r"\.0$", "", regex=True)
                            .str.strip()
                        )
                        p_raw[int_pub_name] = (
                            p_raw[int_pub_name]
                            .astype(str)
                            .str.replace(r"\.0$", "", regex=True)
                            .str.strip()
                        )

                        c_raw[c_pub_comm_col] = pd.to_numeric(
                            c_raw[c_pub_comm_col], errors="coerce"
                        ).fillna(0.0)
                        p_raw[p_pub_comm_col] = pd.to_numeric(
                            p_raw[p_pub_comm_col], errors="coerce"
                        ).fillna(0.0)

                        # 3. 本期：按媒体 ID 汇总【ALL佣金】并记录商家
                        c_comm = (
                            c_raw.groupby(int_pub_name, as_index=False)[c_pub_comm_col]
                            .sum()
                            .rename(columns={c_pub_comm_col: "本期佣金"})
                        )

                        if net_join_key in c_raw.columns:
                            c_merchants = (
                                c_raw.groupby(int_pub_name)[net_join_key]
                                .apply(
                                    lambda x: ", ".join(
                                        sorted(
                                            set(
                                                x.dropna()
                                                .astype(str)
                                                .str.replace(r"\.0$", "", regex=True)
                                                .str.strip()
                                            )
                                        )
                                    )
                                )
                                .reset_index()
                                .rename(columns={net_join_key: "本期商家"})
                            )
                            c_summary = pd.merge(
                                c_comm, c_merchants, on=int_pub_name, how="left"
                            )
                        else:
                            c_summary = c_comm
                            c_summary["本期商家"] = "-"

                        # 4. 上期：按媒体 ID 汇总【ALL佣金】并记录商家
                        p_comm = (
                            p_raw.groupby(int_pub_name, as_index=False)[p_pub_comm_col]
                            .sum()
                            .rename(columns={p_pub_comm_col: "上期佣金"})
                        )

                        if net_join_key in p_raw.columns:
                            p_merchants = (
                                p_raw.groupby(int_pub_name)[net_join_key]
                                .apply(
                                    lambda x: ", ".join(
                                        sorted(
                                            set(
                                                x.dropna()
                                                .astype(str)
                                                .str.replace(r"\.0$", "", regex=True)
                                                .str.strip()
                                            )
                                        )
                                    )
                                )
                                .reset_index()
                                .rename(columns={net_join_key: "上期商家"})
                            )
                            p_summary = pd.merge(
                                p_comm, p_merchants, on=int_pub_name, how="left"
                            )
                        else:
                            p_summary = p_comm
                            p_summary["上期商家"] = "-"

                        # 5. 合并并计算真正的媒体佣金差额
                        pub_merged = pd.merge(
                            c_summary, p_summary, on=int_pub_name, how="outer"
                        ).fillna(
                            {"本期佣金": 0.0, "上期佣金": 0.0, "本期商家": "-", "上期商家": "-"}
                        )

                        pub_merged["媒体佣金差额"] = (
                            pub_merged["本期佣金"] - pub_merged["上期佣金"]
                        )

                        def build_merchant_note(row):
                            p_m = str(row["上期商家"]) if row["上期商家"] != "-" else ""
                            c_m = str(row["本期商家"]) if row["本期商家"] != "-" else ""
                            if p_m and c_m:
                                return (
                                    f"商家: {p_m}"
                                    if p_m == c_m
                                    else f"上期: [{p_m}] ｜ 本期: [{c_m}]"
                                )
                            elif p_m:
                                return f"仅上期有产出: [{p_m}]"
                            elif c_m:
                                return f"本期新增: [{c_m}]"
                            return "-"

                        pub_merged["涉及商家备注"] = pub_merged.apply(
                            build_merchant_note, axis=1
                        )

                        # 6. 找出媒体真实下滑 Top 3
                        top_drop_pub = pub_merged.sort_values(
                            by="媒体佣金差额", ascending=True
                        ).head(3)

                        st.write("🔻 **基于媒体明细【ALL佣金】下滑最明显的 Top 媒体：**")
                        st.dataframe(
                            top_drop_pub[
                                [
                                    int_pub_name,
                                    "上期佣金",
                                    "本期佣金",
                                    "媒体佣金差额",
                                    "涉及商家备注",
                                ]
                            ],
                            column_config={
                                int_pub_name: "媒体 ID / 名称",
                                "上期佣金": st.column_config.NumberColumn(format="$%.2f"),
                                "本期佣金": st.column_config.NumberColumn(format="$%.2f"),
                                "媒体佣金差额": st.column_config.NumberColumn(
                                    format="$%.2f"
                                ),
                                "涉及商家备注": st.column_config.TextColumn(
                                    "涉及商家", width="large"
                                ),
                            },
                            use_container_width=True,
                        )

                # --- 维度 4: 自动化运营调优建议 ---
                st.markdown("**4️⃣ 💡 自动化运营调优行动建议**")
                recommendations = []

                if click_delta_pct < -5:
                    recommendations.append(
                        "针对下滑 Top 媒体，联系媒体确认是否有链接失效、活动过期或资源位下架情况。"
                    )
                if ecpc_delta_pct < -5:
                    recommendations.append(
                        "检查 CVR 下滑明显的商家，确认落地页（Landing Page）及优惠码（Coupon）是否正常。"
                    )
                if not drop_merchants.empty:
                    worst_m = drop_merchants.iloc[0][net_join_key]
                    recommendations.append(
                        f"重点跟进商家 `{worst_m}`，检查其佣金率（Commission Rate）是否近期被下调或高客单商品断货。"
                    )

                if not recommendations:
                    recommendations.append(
                        "当前表现符合预期，建议保持对头号商家的优质资源倾斜。"
                    )

                for idx, rec in enumerate(recommendations, 1):
                    st.write(f"{idx}. {rec}")
        # --------------------------------------------------------------
        # 模块 5：优质商家选品推荐引擎
        # --------------------------------------------------------------
        st.markdown("#### 5. 优质商家选品与媒体推送推荐")

        if not curr_df.empty and net_join_key in curr_df.columns:
            m_summary = (
                curr_df.groupby(net_join_key, as_index=False)
                .agg({
                    net_gmv: "sum",
                    net_clicks: "sum",
                    net_sales: "sum",
                    net_comm: "sum",
                })
            )
            m_summary[net_join_key] = m_summary[net_join_key].astype(str)

            m_summary["CVR (%)"] = (
                m_summary[net_sales]
                / m_summary[net_clicks].replace(0, np.nan)
                * 100
            ).fillna(0)
            m_summary["AOV ($)"] = (
                m_summary[net_gmv] / m_summary[net_sales].replace(0, np.nan)
            ).fillna(0)
            m_summary["eCPC ($)"] = (
                m_summary[net_comm] / m_summary[net_clicks].replace(0, np.nan)
            ).fillna(0)

            avg_cvr = float(m_summary["CVR (%)"].mean()) if not m_summary.empty else 0.0
            avg_aov = float(m_summary["AOV ($)"].mean()) if not m_summary.empty else 0.0

            recommended = m_summary[
                (m_summary["CVR (%)"] >= avg_cvr)
                & (m_summary["AOV ($)"] >= avg_aov)
                & (m_summary[net_gmv] > 1000)
            ].sort_values(by="eCPC ($)", ascending=False)

            if not recommended.empty:
                st.markdown(
                    f"根据算法筛选，为您精选出以下 **{len(recommended)}** 个高转化、高客单、高收益的优质商家，建议推给媒体进行重点拓量："
                )
                st.dataframe(
                    recommended[
                        [
                            net_join_key,
                            net_gmv,
                            "CVR (%)",
                            "AOV ($)",
                            "eCPC ($)",
                        ]
                    ],
                    column_config={
                        net_join_key: "商家标识",
                        net_gmv: st.column_config.NumberColumn("GMV", format="$%.2f"),
                        "CVR (%)": st.column_config.NumberColumn(format="%.2f%%"),
                        "AOV ($)": st.column_config.NumberColumn(format="$%.2f"),
                        "eCPC ($)": st.column_config.NumberColumn("单击收益 eCPC", format="$%.3f"),
                    },
                    use_container_width=True,
                )
            else:
                st.info("当前周期暂无各项指标显著超越大盘均值的优质商家。")
        else:
            st.info("当前周期暂无可用的商家分析数据。")

            # 打印该商家的行数和数据明细
