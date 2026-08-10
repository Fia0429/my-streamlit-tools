import pandas as pd
import numpy as np
import plotly.graph_objects as io
from plotly.subplots import make_subplots
import streamlit as st

# 1. 页面基本设置
st.set_page_config(
    page_title="联盟与商家结算数据分析工具",
    page_icon="📊",
    layout="wide"
)

# ============================================================
# 核心指标计算逻辑（基础表）
# ============================================================
def calculate_metrics_dict(sub_df, comm_col_name):
    total_orders = len(sub_df)
    
    approved_statuses = ['approved', 'approve', 'paid', 'confirmed', 'accept', 'accepted','paid','awaiting payment','1 (paid)','a']
    pending_statuses = ['pending', 'hold', 'unapproved', 'open', 'processing', 'under review','under evaluation','awaiting approval','2 (processing)','1 (on hold)','delayed','ps']
    rejected_statuses = ['rejected', 'reject', 'canceled', 'cancelled', 'declined', 'invalid', 'trash', 'disapproved','n/a', 'reversed', 'reverse','3 (rejected)','d']
    
    # 填充 None / NaN 为字符串 'none'，防止 Pandas 比对失效
    status_series = sub_df['status'].fillna('none').astype(str).str.strip().str.lower()
    
    approved_mask = status_series.isin(approved_statuses)
    pending_mask = status_series.isin(pending_statuses)
    rejected_mask = status_series.isin(rejected_statuses)
    
    approved_orders = int(approved_mask.sum())
    pending_orders = int(pending_mask.sum())
    rejected_orders = int(rejected_mask.sum())
    
    # 特别统计 reversed 单数（便于排查验证）
    reversed_orders = int(status_series.isin(['reversed', 'reverse']).sum())
    
    # 带 Settlement ID 且状态为 Approved 的订单
    settled_approved_mask = sub_df['has_settlement'] & approved_mask
    settled_orders = int(settled_approved_mask.sum())
    
    closed_orders = approved_orders + rejected_orders
    
    # --- 指标计算 ---
    # 1. 当前总体结算率 = Approved单数 / 总订单数
    overall_realized_rate = (approved_orders / total_orders) if total_orders > 0 else 0
    
    # 2. 概率加权预期结算率（基于已完结订单中的转化比例来折算 Pending 订单）
    closed_conversion_rate = (approved_orders / closed_orders) if closed_orders > 0 else 0
    weighted_expected_rate = (approved_orders + (pending_orders * closed_conversion_rate)) / total_orders if total_orders > 0 else 0
    
    # 3. 订单取消率 = Rejected单数 / 总订单数
    cancellation_rate = (rejected_orders / total_orders) if total_orders > 0 else 0
    
    # 4. 商家打款履约率 = 已结算单数 / Approved单数
    settlement_fulfillment_rate = (settled_orders / approved_orders) if approved_orders > 0 else 0

    # 5. 佣金有效率 = Approved总佣金(带Settlement ID) / 原始产生总佣金
    # 清洗佣金列（转数值，剔除货币符号与千分位逗号）
    comm_series = pd.to_numeric(
        sub_df[comm_col_name].astype(str).str.replace(r'[^\d.-]', '', regex=True), 
        errors='coerce'
    ).fillna(0)
    
    total_raw_commission = comm_series.sum()
    settled_approved_commission = comm_series[settled_approved_mask].sum()
    commission_effective_rate = (settled_approved_commission / total_raw_commission) if total_raw_commission > 0 else 0

    # 6. 结算周期计算
    settled_days = sub_df.loc[sub_df['has_settlement'], 'settlement_days'].dropna()
    if len(settled_days) > 0:
        avg_days = round(float(settled_days.mean()), 1)
        median_days = round(float(settled_days.median()), 1)
        cycle_str = f"平均 {avg_days} 天 / 中位数 {median_days} 天"
    else:
        cycle_str = "没打过款"
        
    return {
        '商家名称': '',
        '总订单数': total_orders,
        'Approved单数': approved_orders,
        'Pending单数': pending_orders,
        'Rejected单数': rejected_orders,
        '其中Reversed单数': reversed_orders,
        '已结算单数(带ID)': settled_orders,
        '1. 当前总体结算率': round(overall_realized_rate * 100, 2),
        '2. 概率加权预期结算率': round(weighted_expected_rate * 100, 2),
        '3. 商家订单取消率': round(cancellation_rate * 100, 2),
        '4. 商家打款履约率': round(settlement_fulfillment_rate * 100, 2),
        '5. 佣金有效率': round(commission_effective_rate * 100, 2),
        '6. 平均结算周期': cycle_str
    }

# ============================================================
# 看板辅助算法：水位线计算
# ============================================================
def calculate_waterline_df(df, tx_time_col, selected_merchants=None):
    """计算各商家全量打款截止日"""
    if tx_time_col == "-- 不设置 / 无该字段 --" or 'tx_dt' not in df.columns:
        return None
        
    approved_statuses = ['approved', 'approve', 'paid', 'confirmed', 'accept', 'accepted','paid','awaiting payment','1 (paid)','a']
    waterlines = []
    
    # 支持商家筛选
    target_df = df if not selected_merchants else df[df['merchant_clean'].isin(selected_merchants)]
    
    for merchant, group in target_df.groupby('merchant_clean'):
        app_df = group[group['status'].isin(approved_statuses) & group['tx_dt'].notna()].sort_values('tx_dt')
        
        if len(app_df) == 0:
            waterlines.append({'商家名称': merchant, '全量结算截止日': '无 Approved 订单', '账期延时': '-', '水位线状态': '⚪ 尚无待结算单'})
            continue
            
        unsettled = app_df[~app_df['has_settlement']]
        
        # 在开头获取当前的 Timestamp（保证和 Pandas Timestamp 类型一致，且均无时区）
        now = pd.Timestamp.now().tz_localize(None)

        if len(unsettled) == 0:
            last_dt = app_df['tx_dt'].max()
            delay = (now - last_dt.tz_localize(None) if hasattr(last_dt, 'tz_localize') and last_dt.tz else now - last_dt).days
            waterlines.append({
                '商家名称': merchant, 
                '全量结算截止日': last_dt.strftime('%Y-%m-%d'), 
                '账期延时': f"{delay} 天", 
                '水位线状态': '🟢 100% 已全量结清'
            })
        else:
            first_unsettled_dt = unsettled['tx_dt'].min()
            settled_before = app_df[app_df['tx_dt'] < first_unsettled_dt]
            
            if len(settled_before) == 0:
                waterlines.append({
                    '商家名称': merchant, 
                    '全量结算截止日': '尚未开始打款', 
                    '账期延时': '-', 
                    '水位线状态': f"🔴 首笔未结单位于 {first_unsettled_dt.strftime('%Y-%m-%d')}"
                })
            else:
                cutoff_dt = settled_before['tx_dt'].max()
                clean_cutoff = cutoff_dt.tz_localize(None) if hasattr(cutoff_dt, 'tz_localize') and cutoff_dt.tz else cutoff_dt
                delay = (now - clean_cutoff).days
                waterlines.append({
                    '商家名称': merchant, 
                    '全量结算截止日': cutoff_dt.strftime('%Y-%m-%d'), 
                    '账期延时': f"{delay} 天", 
                    '水位线状态': f"🟡 停滞于 {first_unsettled_dt.strftime('%Y-%m-%d')} 未结订单"
                })
    return pd.DataFrame(waterlines)

@st.cache_data(show_spinner="正在极速精算全量数据中...")
def process_and_summarize(file_bytes, file_name, merchant_col, status_col, settlement_col, comm_col, tx_time_col, val_time_col):
    # --- 1. 容错读取文件 ---
    if file_name.endswith('.csv'):
        try:
            df = pd.read_csv(file_bytes, engine='pyarrow')
        except Exception:
            if hasattr(file_bytes, 'seek'):
                file_bytes.seek(0)
            try:
                df = pd.read_csv(file_bytes, engine='c', on_bad_lines='skip')
            except Exception:
                if hasattr(file_bytes, 'seek'):
                    file_bytes.seek(0)
                df = pd.read_csv(file_bytes, engine='python', on_bad_lines='skip')
    else:
        df = pd.read_excel(file_bytes)

    # 1. 商家名称标准化
    df['merchant_clean'] = df[merchant_col].fillna('未知商家').astype(str)
    
    # 2. 状态全方位清洗（统一小写、去前后空格/引号/换行）
    df['status'] = df[status_col].fillna('none').astype(str).str.lower().str.strip(" \"'\t\n\r")
    
    # 3. 结算单据 ID 深度清洗（剔除 0, 0.0, none, null 等伪 ID）
    s_raw = df[settlement_col].fillna('').astype(str).str.strip().str.lower()
    s_clean = s_raw.str.replace(r'\.0$', '', regex=True)
    invalid_settlement = {'', '0', 'none', 'nan', 'null', 'false', 'undefined'}
    df['has_settlement'] = ~s_clean.isin(invalid_settlement)
    
    # 4. 时间列解析（安全解析，绝不 dropna 丢行）
    if tx_time_col != "-- 不设置 / 无该字段 --":
        s_tx = df[tx_time_col].astype(str).str.replace(r'\[.*?\]', '', regex=True)
        parsed_tx = pd.to_datetime(s_tx, errors='coerce', format='mixed', utc=True)
        df['tx_dt'] = parsed_tx.dt.tz_convert(None)
    else:
        df['tx_dt'] = pd.NaT

    if val_time_col != "-- 不设置 / 无该字段 --":
        s_val = df[val_time_col].astype(str).str.replace(r'\[.*?\]', '', regex=True)
        parsed_val = pd.to_datetime(s_val, errors='coerce', format='mixed', utc=True)
        df['val_dt'] = parsed_val.dt.tz_convert(None)
    else:
        df['val_dt'] = pd.NaT
        
    if tx_time_col != "-- 不设置 / 无该字段 --" and val_time_col != "-- 不设置 / 无该字段 --":
        df['settlement_days'] = (df['val_dt'] - df['tx_dt']).dt.total_seconds() / 86400.0
    else:
        df['settlement_days'] = np.nan

    # 5. 汇总指标计算
    rows = []
    total_metrics = calculate_metrics_dict(df, comm_col)
    total_metrics['商家名称'] = '🏆 联盟整体 (Network Total)'
    rows.append(total_metrics)
    
    for merchant_name, group in df.groupby('merchant_clean', dropna=False):
        m_metrics = calculate_metrics_dict(group, comm_col)
        m_metrics['商家名称'] = merchant_name
        rows.append(m_metrics)
        
    summary_df = pd.DataFrame(rows)
    
    # 6. 统一列名
    cols = ['商家名称', '总订单数', 'Approved单数', 'Pending单数', 'Rejected单数', '其中Reversed单数', '已结算单数(带ID)', 
            '1. 当前总体结算率', '2. 概率加权预期结算率', '3. 商家订单取消率', '4. 商家打款履约率', '5. 佣金有效率', '6. 平均结算周期']
            
    return summary_df[cols], df, len(df)

# ============================================================
# 高级可视化绘图（支持商家联动筛选）
# ============================================================
def render_advanced_dashboard(df, tx_time_col, selected_merchants=None):
    if tx_time_col == "-- 不设置 / 无该字段 --" or 'tx_dt' not in df.columns or df['tx_dt'].isna().all():
        st.warning("⚠️ 未配置【订单产生时间】列，无法渲染月度趋势与账龄分析看板。请在上方设置中选中对应列。")
        return

    target_df = df if not selected_merchants else df[df['merchant_clean'].isin(selected_merchants)]
    
    if len(target_df) == 0:
        st.info("💡 请在上方至少选择一个商家进行分析。")
        return

    approved_statuses = ['approved', 'approve', 'paid', 'confirmed', 'accept', 'accepted','paid','awaiting payment','1 (paid)','a']
    pending_statuses = ['pending', 'hold', 'unapproved', 'open', 'processing', 'under review','under evaluation','awaiting approval','2 (processing)','1 (on hold)','delayed','ps']

    # --- 1. 月度订单与结算率双趋势图 ---
    st.markdown("#### 📅 月度新增订单量 vs 结算率趋势（当月 vs 累计）")
    
    clean_tx = pd.to_datetime(target_df['tx_dt'], errors='coerce')
    target_df = target_df.copy()
    target_df['month'] = clean_tx.dt.strftime('%Y-%m')
    
    valid_months = sorted([str(m) for m in target_df['month'].dropna().unique() if str(m) not in ['nan', 'NaT', 'None']])
    
    monthly_stats = []
    cum_total_orders = 0
    cum_approved_orders = 0
    
    for month in valid_months:
        group = target_df[target_df['month'] == month]
        
        month_tot = len(group)
        month_app = int(group['status'].isin(approved_statuses).sum())
        monthly_realized_rate = round((month_app / month_tot * 100), 2) if month_tot > 0 else 0
        
        cum_total_orders += month_tot
        cum_approved_orders += month_app
        cum_realized_rate = round((cum_approved_orders / cum_total_orders * 100), 2) if cum_total_orders > 0 else 0
        
        monthly_stats.append({
            'month': month, 
            'total': month_tot, 
            'monthly_realized_rate': monthly_realized_rate, 
            'cum_realized_rate': cum_realized_rate
        })
        
    m_df = pd.DataFrame(monthly_stats)
    
    if len(m_df) == 0:
        st.warning("⚠️ 没有筛选到有效的月度订单数据。")
        return

    fig_month = make_subplots(specs=[[{"secondary_y": True}]])
    
    fig_month.add_trace(
        io.Bar(
            x=m_df['month'], 
            y=m_df['total'], 
            name="当月新增订单数", 
            marker_color='#2b5c8f', 
            opacity=0.75
        ),
        secondary_y=False
    )
    
    fig_month.add_trace(
        io.Scatter(
            x=m_df['month'], 
            y=m_df['monthly_realized_rate'], 
            name="当月独立结算率 (%)", 
            mode='lines+markers+text', 
            text=m_df['monthly_realized_rate'].apply(lambda x: f"{x}%"),
            textposition='top center', 
            line=dict(color='#f39c12', width=2, dash='dot')
        ),
        secondary_y=True
    )

    fig_month.add_trace(
        io.Scatter(
            x=m_df['month'], 
            y=m_df['cum_realized_rate'], 
            name="累计总体结算率 (%)", 
            mode='lines+markers+text', 
            text=m_df['cum_realized_rate'].apply(lambda x: f"{x}%"),
            textposition='bottom center', 
            line=dict(color='#e74c3c', width=3)
        ),
        secondary_y=True
    )
    
    fig_month.update_xaxes(title_text="时间节点（月份）")
    fig_month.update_yaxes(title_text="当月新增订单数", secondary_y=False)
    fig_month.update_yaxes(title_text="结算率 (%)", range=[0, 115], secondary_y=True)
    fig_month.update_layout(
        height=450, 
        hovermode="x unified", 
        template="plotly_white", 
        margin=dict(t=30, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig_month, use_container_width=True)
    
    # --- 2. 账龄风险分组分析 ---
    st.markdown("#### ⏳ 未结算订单账龄分布 (Aging Risk Analysis)")
    st.caption("注：按联盟实际结算习惯，**<90天** 为安全审核期；重点关注 **>180天** 的高危预警期订单。")
    
    now = pd.Timestamp.now()
    df_pending = target_df[target_df['status'].isin(pending_statuses) & target_df['tx_dt'].notna()].copy()
    
    if len(df_pending) > 0:
        df_pending['age_days'] = (now - df_pending['tx_dt']).dt.days
        
        bins = [-1, 89, 179, 99999]
        labels = ['<90天 (安全期)', '90-180天 (常规催款期)', '>180天 (高危预警期)']
        df_pending['aging_bucket'] = pd.cut(df_pending['age_days'], bins=bins, labels=labels)
        
        aging_summary = df_pending.groupby(['merchant_clean', 'aging_bucket'], observed=False).size().unstack(fill_value=0)
        
        fig_aging = io.Figure()
        colors = ['#2ecc71', '#f39c12', '#e74c3c']
        for idx, col in enumerate(aging_summary.columns):
            fig_aging.add_trace(io.Bar(
                x=aging_summary.index,
                y=aging_summary[col],
                name=col,
                marker_color=colors[idx]
            ))
            
        fig_aging.update_layout(
            barmode='stack',
            title_text="各商家 Pending 积压订单账龄分布（堆叠图）",
            xaxis_title="商家名称",
            yaxis_title="Pending 订单数",
            height=450,
            template="plotly_white"
        )
        st.plotly_chart(fig_aging, use_container_width=True)
    else:
        st.success("🎉 当前选中的商家没有任何处于 Pending 状态的积压订单。")

# ============================================================
# Streamlit 界面
# ============================================================
st.title("📊 联盟与商家结算数据精算工具")
st.markdown("---")

uploaded_file = st.file_uploader(
    "📥 请点击或将您的 Excel / CSV 数据文件拖拽至此处", 
    type=["xlsx", "xls", "csv"],
    help="支持百万级数据量的快速精算与可视化"
)

if uploaded_file is not None:
    try:
        if uploaded_file.name.endswith('.csv'):
            header_df = pd.read_csv(uploaded_file, nrows=1)
        else:
            header_df = pd.read_excel(uploaded_file, nrows=1)
            
        raw_cols = list(header_df.columns)
        cols_with_none = ["-- 不设置 / 无该字段 --"] + raw_cols
        
        st.success(f"✅ 文件 【{uploaded_file.name}】 上传成功！已完成数据列识别。")
        
        with st.expander("⚙️ **字段映射设置（请匹配您的数据列）**", expanded=True):
            r1_c1, r1_c2 = st.columns(2)
            with r1_c1:
                merchant_col = st.selectbox("1. 选择【商家名称 / ID】列*", raw_cols, index=0)
            with r1_c2:
                status_col = st.selectbox("2. 选择【订单状态】列*", raw_cols, index=min(1, len(raw_cols)-1))
            
            r2_c1, r2_c2 = st.columns(2)
            with r2_c1:
                settlement_col = st.selectbox("3. 选择【Settlement ID】列*", raw_cols, index=min(2, len(raw_cols)-1))
            with r2_c2:
                comm_col = st.selectbox("4. 选择【佣金 / 预估佣金金额】列*", raw_cols, index=min(3, len(raw_cols)-1))
                
            r3_c1, r3_c2 = st.columns(2)
            with r3_c1:
                tx_time_col = st.selectbox("5. 选择【订单产生时间】列 (Transaction Time)", cols_with_none, index=0)
            with r3_c2:
                val_time_col = st.selectbox("6. 选择【订单打款/审核时间】列 (Validation Date)", cols_with_none, index=0)

        if st.button("🚀 开始极速计算并生成报告", type="primary"):
            summary_table, df_raw, total_count = process_and_summarize(
                uploaded_file, uploaded_file.name, 
                merchant_col, status_col, settlement_col, comm_col, tx_time_col, val_time_col
            )
            
            st.warning("🔍 调试信息：当前数据中包含的所有独立状态如下：")
            st.write(df_raw['status'].unique())
            
            st.info(f"💡 本次分析已成功处理 **{total_count:,}** 条订单明细。")
            
            tab1, tab2 = st.tabs(["📋 结算指标精算汇总表", "📈 商家履约与账期风险看板"])
            
            # --- TAB 1：精算汇总表 ---
            with tab1:
                st.markdown("### 📋 商家基础结算指标汇总表")
                display_df = summary_table.copy()
                pct_columns = ['1. 当前总体结算率', '2. 概率加权预期结算率', '3. 商家订单取消率', '4. 商家打款履约率', '5. 佣金有效率']
                for col in pct_columns:
                    display_df[col] = display_df[col].astype(str) + '%'
                
                st.dataframe(display_df, use_container_width=True)
                
                csv_data = display_df.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    label="📥 下载精算结果 (CSV 格式)",
                    data=csv_data,
                    file_name="联盟与商家结算指标汇总.csv",
                    mime="text/csv"
                )

            # --- TAB 2：高级可视化看板 ---
            with tab2:
                all_merchants = sorted(df_raw['merchant_clean'].unique().tolist())
                selected_merchants = st.multiselect(
                    "🔍 **选择筛选商家 (默认显示全部，可多选具体商家进行聚焦分析)**：",
                    options=all_merchants,
                    default=all_merchants
                )
                
                st.markdown("---")
                
                st.markdown("### 📌 商家打款水位线看板 (Settlement Waterline)")
                waterline_df = calculate_waterline_df(df_raw, tx_time_col, selected_merchants)
                
                if waterline_df is not None:
                    st.dataframe(waterline_df, use_container_width=True)
                else:
                    st.info("💡 请配置【订单产生时间】列后查看商家全量打款截止日水位线。")
                    
                st.markdown("---")
                
                st.markdown("### 📈 商家履约与账期风险可视化")
                render_advanced_dashboard(df_raw, tx_time_col, selected_merchants)

    except Exception as e:
        st.error(f"❌ 处理文件时出错：{e}")
else:
    st.info("👆 请先在上方拖拽上传您的 Excel 或 CSV 数据表格。")