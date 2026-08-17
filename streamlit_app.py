import streamlit as st

# 1. 页面基本配置
st.set_page_config(
    page_title="数据分析工具箱",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 2. 自定义 CSS 样式注入
st.markdown("""
    <style>
    /* 调整主区域边距 */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 1200px;
    }
    
    /* 卡片容器样式 */
    .tool-card {
        background-color: #f8f9fa;
        border: 1px solid #e9ecef;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 20px;
        transition: all 0.3s ease-in-out;
    }
    .tool-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 8px 24px rgba(0,0,0,0.08);
        border-color: #4f46e5;
    }
    
    /* 图标与标题 */
    .tool-icon {
        font-size: 28px;
        margin-bottom: 10px;
    }
    .tool-title {
        font-size: 18px;
        font-weight: 600;
        color: #1f2937;
        margin-bottom: 8px;
    }
    .tool-desc {
        font-size: 14px;
        color: #6b7280;
        line-height: 1.5;
    }
    </style>
""", unsafe_allow_html=True)

# 3. 头部 Hero 区域
st.title("📊 联盟数据分析工具箱")
st.caption("一站式业务风控、数据预测与运营结算辅助平台")
st.divider()

# 4. 侧边栏优化（添加图标与提示）
with st.sidebar:
    st.image("https://img.icons8.com/color/96/analytics.png", width=60)
    st.title("功能导航")
    # 如果使用 st.navigation（Streamlit 1.31+ 多页面模式）：
    # 页面的 title 会自动读取，也可以搭配 emoji 图标。

# 5. 主页功能模块卡片化展示 (2x2 网格)
col1, col2 = st.columns(2)

with col1:
    st.markdown("""
        <div class="tool-card">
            <div class="tool-icon">🛡️</div>
            <div class="tool-title">风控筛选</div>
            <div class="tool-desc">识别联盟商家高风险流量与异常订单，支持自动化规则审计与风险排查。</div>
        </div>
    """, unsafe_allow_html=True)
    if st.button("进入风控筛选 →", key="btn1", use_container_width=True):
        st.switch_page("pages/1_风控筛选.py") # 需配置多页面路径

    st.markdown("""
        <div class="tool-card">
            <div class="tool-icon">📈</div>
            <div class="tool-title">月目标预测</div>
            <div class="tool-desc">基于历史数据与趋势模型，对联盟商家月度业绩与 GMV 进行智能预测。</div>
        </div>
    """, unsafe_allow_html=True)
    if st.button("进入业绩预测 →", key="btn3", use_container_width=True):
        st.switch_page("pages/3_联盟月目标预测.py")

with col2:
    st.markdown("""
        <div class="tool-card">
            <div class="tool-icon">💰</div>
            <div class="tool-title">商家结算情况</div>
            <div class="tool-desc">汇总与统计联盟商家账单结算进度、佣金明细及异常对账数据。</div>
        </div>
    """, unsafe_allow_html=True)
    if st.button("进入结算管理 →", key="btn2", use_container_width=True):
        st.switch_page("pages/2_联盟商家结算情况.py")

    st.markdown("""
        <div class="tool-card">
            <div class="tool-icon">🧮</div>
            <div class="tool-title">商家预算 & 安全订单数计算器</div>
            <div class="tool-desc">测算商家投入产出比，快速计算保本及安全风险阈值下的订单量要求。</div>
        </div>
    """, unsafe_allow_html=True)
    if st.button("进入计算器 →", key="btn4", use_container_width=True):
        st.switch_page("pages/4_商家预算计算器.py")
