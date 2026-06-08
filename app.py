import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

# --- 1. 页面配置与全局字体设置 ---
st.set_page_config(page_title="招聘网站数据分析", layout="wide")
st.title("📊 招聘网站数据分析")
st.markdown("---")

# 设置 Matplotlib 中文字体，防止乱码
plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False


# --- 2. 数据加载 ---
@st.cache_data
def load_data():
    try:
        df = pd.read_csv("data.csv", encoding='utf-8-sig')
        return df
    except FileNotFoundError:
        st.error("未找到 'data.csv' 文件，请确保文件已清洗并位于同目录下。")
        st.stop()


df = load_data()

# --- 定义规模等级的中文映射字典 ---
scale_map_reverse = {
    1: '0-20人', 2: '20-99人', 3: '100-499人',
    4: '500-999人', 5: '1000-9999人', 6: '10000人以上'
}

# --- 3. 侧边栏筛选器 ---
st.sidebar.header("🔍 筛选条件")

all_cities = sorted(df['城市'].dropna().unique())
selected_city = st.sidebar.multiselect("选择城市", options=all_cities, default=["北京"])

if selected_city:
    filtered_districts_df = df[df['城市'].isin(selected_city)]
    all_districts = sorted(filtered_districts_df['区'].dropna().unique())
else:
    all_districts = sorted(df['区'].dropna().unique())
selected_district = st.sidebar.multiselect("选择区域 (可选)", options=all_districts, default=[])

all_sectors = sorted(df['领域'].dropna().unique())
selected_sector = st.sidebar.multiselect("选择行业领域", options=all_sectors, default=["互联网"])

all_educations = sorted(df['学历标准'].dropna().unique())
selected_education = st.sidebar.multiselect("选择学历要求", options=all_educations, default=["本科"])

# 薪资范围筛选
if '平均薪资' in df.columns:
    # 获取平均薪资的全局最小值和最大值
    avg_min = int(df['平均薪资'].min())
    avg_max = int(df['平均薪资'].max())

    # 创建滑动条
    salary_range = st.sidebar.slider(
        "期望平均月薪 (¥/月)",
        min_value=avg_min,
        max_value=avg_max,
        value=(avg_min, avg_max)
    )
else:
    # 兜底逻辑
    st.sidebar.warning("无平均薪资数据")
    salary_range = (0, 100000)  # 给一个默认的大范围，防止报错

if '融资阶段' in df.columns:
    all_stages = sorted(df['融资阶段'].dropna().unique())
    selected_stages = st.sidebar.multiselect("公司发展阶段", options=all_stages, default=all_stages)
else:
    selected_stages = []

# --- 4. 数据筛选逻辑 ---
mask = pd.Series([True] * len(df))
if selected_city: mask &= df['城市'].isin(selected_city)
if selected_district: mask &= df['区'].isin(selected_district)
if selected_sector: mask &= df['领域'].isin(selected_sector)
if selected_education: mask &= df['学历标准'].isin(selected_education)
if '平均薪资' in df.columns:
    # 逻辑：岗位的“平均薪资”必须在你选择的 [最小值, 最大值] 之间
    mask &= (df['平均薪资'] >= salary_range[0]) & (df['平均薪资'] <= salary_range[1])
elif '最低薪资' in df.columns and '最高薪资' in df.columns:
    # 备用逻辑（如果没有平均薪资列）：只要区间有重叠就算
    mask &= (df['最低薪资'] <= salary_range[1]) & (df['最高薪资'] >= salary_range[0])
if '融资阶段' in df.columns and selected_stages:
    mask &= df['融资阶段'].isin(selected_stages)

filtered_df = df[mask].copy()

# --- 5. 顶部关键指标 (KPI) ---
st.subheader("📌 核心指标概览")
col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)

job_count = len(filtered_df)
avg_salary_val = filtered_df['平均薪资'].mean() if not filtered_df.empty else 0
max_salary_val = filtered_df['最高薪资'].max() if not filtered_df.empty else 0
avg_exp_val = filtered_df['经验_最低年限'].mean() if not filtered_df.empty and '经验_最低年限' in filtered_df.columns else 0

col_kpi1.metric(label="岗位总数", value=job_count)
col_kpi2.metric(label="平均薪资 (¥/月)", value=f"{avg_salary_val:,.0f}")
col_kpi3.metric(label="最高薪资 (¥/月)", value=f"{max_salary_val:,.0f}")
col_kpi4.metric(label="平均经验要求 (年)", value=f"{avg_exp_val:.1f}")

st.markdown("---")

# --- 6. 深度分析图表区域 ---

# 第一部分：行业与公司规模关联分析
st.subheader("🏢 行业与公司规模薪资关联分析")
row1_col1, row1_col2 = st.columns(2)

with row1_col1:
    st.caption("各行业平均薪资 Top 10")
    fig1, ax1 = plt.subplots(figsize=(8, 5))
    if not filtered_df.empty:
        sector_salary = filtered_df.groupby('领域')['平均薪资'].mean().sort_values(ascending=False).head(10)
        sns.barplot(y=sector_salary.index, x=sector_salary.values, ax=ax1, palette='coolwarm')
        ax1.set_xlabel("平均薪资 (元/月)")
        ax1.set_ylabel("行业领域")
    else:
        ax1.text(0.5, 0.5, '无数据', transform=ax1.transAxes, ha='center')
    st.pyplot(fig1)

with row1_col2:
    st.caption("公司规模与融资阶段对薪资的影响")
    fig2, ax2 = plt.subplots(figsize=(8, 5))
    if not filtered_df.empty and '规模等级' in filtered_df.columns:
        plot_data = filtered_df[filtered_df['规模等级'] > 0].copy()
        if not plot_data.empty:
            plot_data['规模描述'] = plot_data['规模等级'].map(scale_map_reverse)
            plot_data = plot_data.sort_values('规模等级')
            # 使用不同颜色区分不同融资阶段，展示更深层的关联
            sns.barplot(data=plot_data, x='规模描述', y='平均薪资', hue='融资阶段', ax=ax2, palette='viridis', errorbar=None)
            ax2.set_ylabel("平均薪资 (元/月)")
            ax2.set_xlabel("公司规模")
            plt.xticks(rotation=45)
            ax2.legend(title='融资阶段', bbox_to_anchor=(1.05, 1), loc='upper left')
        else:
            ax2.text(0.5, 0.5, '无有效规模等级数据', transform=ax2.transAxes, ha='center', color='red')
    else:
        ax2.text(0.5, 0.5, '未找到“规模等级”列', transform=ax2.transAxes, ha='center', color='red')
    st.pyplot(fig2)

# 第二部分：经验与技能趋势挖掘
st.subheader("🚀 经验要求与技能需求趋势挖掘")
row2_col1, row2_col2 = st.columns(2)

with row2_col1:
    st.caption("不同经验要求的薪资分布（箱线图）")
    fig3, ax3 = plt.subplots(figsize=(8, 5))
    if not filtered_df.empty and '经验_最低年限' in filtered_df.columns:
        sns.boxplot(data=filtered_df, x='经验_最低年限', y='平均薪资', ax=ax3, palette='Set2')
        ax3.set_xlabel("最低经验要求 (年)")
        ax3.set_ylabel("平均薪资 (元/月)")
        ax3.grid(True, alpha=0.3, axis='y')
    else:
        ax3.text(0.5, 0.5, '无经验数据', transform=ax3.transAxes, ha='center')
    st.pyplot(fig3)

with row2_col2:
    st.caption("初级(1-3年) vs 资深(5年+) 岗位技能需求对比")
    if not filtered_df.empty and '要求' in filtered_df.columns and '经验_最低年限' in filtered_df.columns:
        from wordcloud import WordCloud

        # 提取初级岗位的技能要求
        junior_req = filtered_df[(filtered_df['经验_最低年限'] >= 1) & (filtered_df['经验_最低年限'] <= 3)]['要求'].dropna().astype(
            str)
        # 提取资深岗位的技能要求
        senior_req = filtered_df[filtered_df['经验_最低年限'] >= 5]['要求'].dropna().astype(str)

        if len(junior_req) > 0 and len(senior_req) > 0:
            fig4, axes = plt.subplots(1, 2, figsize=(12, 5))

            # 绘制初级岗位词云
            text_junior = " ".join(junior_req)
            try:
                wc_junior = WordCloud(background_color='white', width=400, height=300, max_words=50,
                                      font_path='simhei.ttf', colormap='Blues').generate(text_junior)
            except:
                wc_junior = WordCloud(background_color='white', width=400, height=300, max_words=50).generate(
                    text_junior)
            axes[0].imshow(wc_junior, interpolation='bilinear')
            axes[0].set_title('初级岗位 (1-3年) 技能热词', fontsize=12)
            axes[0].axis('off')

            # 绘制资深岗位词云
            text_senior = " ".join(senior_req)
            try:
                wc_senior = WordCloud(background_color='white', width=400, height=300, max_words=50,
                                      font_path='simhei.ttf', colormap='Reds').generate(text_senior)
            except:
                wc_senior = WordCloud(background_color='white', width=400, height=300, max_words=50).generate(
                    text_senior)
            axes[1].imshow(wc_senior, interpolation='bilinear')
            axes[1].set_title('资深岗位 (5年+) 技能热词', fontsize=12)
            axes[1].axis('off')

            plt.tight_layout()
            st.pyplot(fig4)
        else:
            st.info("当前筛选条件下，初级或资深岗位数据不足，无法生成对比词云。")
    else:
        st.info("未找到“要求”或“经验_最低年限”列。")

# 底部数据明细
st.subheader("📝 数据明细")
display_cols = ['职业', '城市', '区', '公司', '领域', '学历标准', '规模', '融资阶段', '平均薪资']
valid_cols = [col for col in display_cols if col in filtered_df.columns]
st.dataframe(filtered_df[valid_cols].head(10))
