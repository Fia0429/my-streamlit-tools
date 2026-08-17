import streamlit as st

# 1. 页面基础设置
st.set_page_config(
    page_title="数据分析工具箱",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 2. 自定义 CSS：收紧页面边距，美化按钮与卡片
st.markdown("""
    <style>
    /* 限制内容最大宽度，解决白茫茫大留白问题 */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
        max-width: 1100px;
    }
    /* 隐藏顶部默认极简菜单线，提升精致感 */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* 统一按钮样式 */
    div.stButton > button {
        width: 100%;
        border-radius: 8px;
        font-weight: 500;
    }
    </style>
""", unsafe_allow_html=True)

# 3. 头部 Hero 区域
st.title("📊 联盟数据分析工具箱")
st.caption("集成了风控、结算、预测与智能识别的一站式运营数据辅助平台")
st.divider()

# 4. 侧边栏优化
with st.sidebar:
    st.header("⚙️ 工具箱导航")
    st.info("💡 请从上方/左侧菜单选择对应工具，或直接点击主页卡片快速进入。")

# 5. 定义 5 个工具的数据配置
tools = [
    {
        "title": "风控筛选",
        "icon": "🛡️",
        "desc": "识别联盟商家高风险流量与异常订单，支持自动化规则审计与风险排查。",
        "page": "pages/1_风控筛选.py", # 替换为你的实际文件路径
    },
    {
        "title": "联盟商家结算情况",
        "icon": "💳",
        "desc": "汇总与统计联盟商家账单结算进度、佣金明细及异常对账数据。",
        "page": "pages/2_联盟商家结算情况.py",
    },
    {
        "title": "联盟月目标预测",
        "icon": "📈",
        "desc": "基于历史数据与趋势模型，对联盟商家月度业绩与 GMV 进行智能预测。",
        "page": "pages/3_联盟月目标预测.py",
    },
    {
        "title": "商家预算&安全订单数计算器",
        "icon": "🧮",
        "desc": "测算商家投入产出比，快速计算保本及安全风险阈值下的订单量要求。",
        "page": "pages/4_商家预算安全单数计算器.py",
    },
    {
        "title": "商家类别自动识别",
        "icon": "🏷️",
        "desc": "利用文本挖掘与分类规则，快速对商家所属行业及品类进行自动标记与归类。",
        "page": "pages/5_商家类别自动识别.py",
    },
]

# 6. 动态网格渲染 (每行 2 列)
for i in range(0, len(tools), 2):
    cols = st.columns(2)
    
    # 左侧卡片
    with cols[0]:
        tool = tools[i]
        with st.container(border=True):
            st.subheader(f"{tool['icon']} {tool['title']}")
            st.write(tool["desc"])
            st.write("") # 间距
            if st.button("进入工具 →", key=f"btn_{i}", type="primary"):
                st.switch_page(tool["page"])

    # 右侧卡片（判断是否存在第 2 项，针对单数项补齐）
    if i + 1 < len(tools):
        with cols[1]:
            tool = tools[i + 1]
            with st.container(border=True):
                st.subheader(f"{tool['icon']} {tool['title']}")
                st.write(tool["desc"])
                st.write("")
                if st.button("进入工具 →", key=f"btn_{i+1}"):
                    st.switch_page(tool["page"])
