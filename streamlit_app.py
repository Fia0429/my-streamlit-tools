import streamlit as st

st.set_page_config(page_title="数据分析工具箱", layout="wide")
st.title("欢迎使用数据分析工具箱")
st.write("请在左侧侧边栏选择需要使用的具体工具：")
st.markdown("""
* **工具一**：联盟商家风控筛查
* **工具二**：联盟商家结算情况
* **工具三**：联盟商家业绩预测
""")