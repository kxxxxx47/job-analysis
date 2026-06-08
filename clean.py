import pandas as pd

df = pd.read_csv('job_raw.csv', encoding='utf-8-sig')

print(f"原始数据量: {len(df)} 条")
print("列名预览：", df.columns.tolist())
print(df.head())

df = df.drop(columns=['福利'])
index_to_drop = df[df['职业'] == '职业'].index
# 根据索引删除
df = df.drop(index_to_drop)
df = df.reset_index(drop=True)

print(f"数据量: {len(df)} 条")

# ---薪资字段清洗---
# 1. 删除空值
df.dropna(subset=['薪资'], inplace=True)
# 2. 删除面议
df = df[~df['薪资'].str.contains('面议', na=False)]

df.reset_index(drop=True, inplace=True)


def extract_salary_info(s):
    if pd.isna(s):
        return 0, 0, 0

    # 1. 基础清洗
    text = str(s).strip()

    # ==========================================
    # 第一步：处理年终奖 (·16薪)
    # ==========================================
    bonus_multiplier = 1.0  # 默认12薪，系数为1

    if '·' in text:
        parts = text.split('·')
        text = parts[0]  # 取出薪资主体，例如 '10-15K'
        if len(parts) > 1:
            # 处理 '16薪' -> 16/12
            bonus_str = parts[1].replace('薪', '')
            try:
                bonus_months = float(bonus_str)
                bonus_multiplier = bonus_months / 12
            except:
                pass

    # ==========================================
    # 第二步：确定单位倍率 (时/天/周/月)
    # ==========================================
    rate = 1  # 最终倍率，默认为1 (即月薪)

    # 1. 处理时薪
    if '/时' in text:
        text = text.replace('/时', '').replace('元', '')
        rate = 8 * 22  # 每天8小时 * 每月22天

    # 2. 处理日薪
    elif '/天' in text:
        text = text.replace('/天', '').replace('元', '')
        rate = 22  # 每月22天

    # 3. 处理周薪
    elif '/周' in text:
        text = text.replace('/周', '').replace('元', '')
        rate = 52 / 12  # 每年52周 / 12个月

    # 4. 处理月薪 (默认)
    else:
        # 去掉末尾可能存在的 '/月'
        text = text.replace('/月', '').replace('元', '')

    # ==========================================
    # 第三步：提取数值并计算
    # ==========================================
    # 处理 'K' 或 'k'
    unit_factor = 1000 if ('k' in text or 'K' in text) else 1
    text = text.replace('k', '').replace('K', '')

    min_sal, max_sal, avg_sal = 0, 0, 0

    try:
        # 处理范围 '10-15'
        if '-' in text:
            nums = text.split('-')
            val_min = float(nums[0])
            val_max = float(nums[1])
        else:
            # 处理单一值 '10'
            val_min = float(text)
            val_max = float(text)

        # 最终计算公式：
        # 数值 * 单位(K) * 时间换算(时/天/周) * 年终奖系数
        final_min = val_min * unit_factor * rate * bonus_multiplier
        final_max = val_max * unit_factor * rate * bonus_multiplier

        min_sal = round(final_min, 1)
        max_sal = round(final_max, 1)
        avg_sal = round((final_min + final_max) / 2, 1)

    except ValueError:
        # 如果无法转换为数字，保持0
        min_sal, max_sal, avg_sal = 0, 0, 0

    return min_sal, max_sal, avg_sal

salary_data = df['薪资'].apply(lambda x: pd.Series(extract_salary_info(x)))

# 赋值给新列
df['最低薪资'] = salary_data[0]
df['最高薪资'] = salary_data[1]
df['平均薪资'] = salary_data[2]


# 1. 清洗【城市】列：拆分行政区
# 原始数据示例：'北京·朝阳区·望京'  -> 目标是提取 '北京' 和 '朝阳区'
# ==========================================
def clean_city(text):
    if pd.isna(text):
        return '未知', '未知'
    # 使用 '·' 进行分割
    parts = str(text).split('·')
    city = parts[0] # 第一个是城市，如 北京
    district = parts[1] if len(parts) > 1 else '未知' # 第二个是区
    return city, district

# 应用拆分
df[['城市', '区']] = df['城市'].apply(lambda x: pd.Series(clean_city(x)))


# 新增一列“最低经验年限”用于计算
def get_min_years(text):
    if pd.isna(text): return 0
    text = str(text)

    # 实习/不限/应届 -> 0
    if any(x in text for x in ['不限', '应届', '在校', '/周', '天']):
        return 0

    # 提取 "X-Y年" 中的 X
    if '-' in text:
        return int(text.split('-')[0].replace('年', ''))

    # 提取 "X年以内" 或 "X年以上"
    if '年' in text:
        return int(text.replace('年', '').replace('以内', '').replace('以上', ''))

    return 0


# 生成新列
df['经验_最低年限'] = df['经验'].apply(get_min_years)


def clean_education(text):
    if pd.isna(text):
        return '未知', 0

    text = str(text).strip()

    # ==========================================
    # 第一步：清洗脏数据（图中混入的“时间”数据）
    # 如果包含“个月”，说明是实习时长数据错位到了这里，归为“未知”
    # ==========================================
    if '个月' in text:
        return '未知', 0

    # 处理“学历”、“学历不限”这种无效标签
    if text == '学历' or '不限' in text:
        return '不限', 0

    # ==========================================
    # 第二步：统一学历标准（分类）
    # 将各种写法映射到 5个标准类别
    # ==========================================
    edu_level = '未知'

    # 博士
    if '博士' in text or '博士后' in text:
        edu_level = '博士'
    # 硕士
    elif '硕士' in text or '研究生' in text:
        edu_level = '硕士'
    # 本科
    elif '本科' in text or '学士' in text:
        edu_level = '本科'
    # 大专
    elif '大专' in text or '专科' in text:
        edu_level = '大专'
    # 高中/中专
    elif '高中' in text or '中专' in text or '中技' in text:
        edu_level = '高中/中专'
    # 初中及以下
    elif '初中' in text or '小学' in text:
        edu_level = '初中及以下'

    # ==========================================
    # 第三步：数值化（用于排序）
    # 学历越高，数字越大
    # ==========================================
    edu_map = {
        '初中及以下': 1,
        '高中/中专': 2,
        '大专': 3,
        '本科': 4,
        '硕士': 5,
        '博士': 6,
        '不限': 0,
        '未知': 0
    }

    score = edu_map.get(edu_level, 0)

    return edu_level, score


# 应用清洗
# 返回两列：'学历标准' (文本) 和 '学历等级' (数字)
df[['学历标准', '学历等级']] = df['学历'].apply(lambda x: pd.Series(clean_education(x)))


def map_financing_stage(stage):
    if pd.isna(stage):
        return '未知'

    # 处理无融资情况
    if '未融资' in stage or '不需要融资' in stage:
        return '无融资/无需融资'

    # 处理上市情况
    if '已上市' in stage:
        return '已上市'

    # 处理天使轮
    if '天使轮' in stage:
        return '天使轮'

    # 处理 A轮、B轮、C轮、D轮
    if 'A轮' in stage or 'B轮' in stage or 'C轮' in stage or 'D轮' in stage:
        return '成长期(A-D轮)'

    return '其他'


# 应用函数，生成新列（建议保留原列，生成新列用于分析）
df['融资阶段'] = df['融资'].apply(map_financing_stage)


# 定义等级映射（数字越大，代表公司越成熟/越有钱）
stage_mapping = {
    '未融资': 0,
    '不需要融资': 0,
    '天使轮': 1,
    'A轮': 2,
    'B轮': 3,
    'C轮': 4,
    'D轮及以上': 5,
    '已上市': 6
}

# 提取关键词并映射为数字
def extract_stage_score(text):
    if pd.isna(text):
        return -1
    for key in stage_mapping.keys():
        if key in str(text):
            return stage_mapping[key]
    return -1

df['融资等级'] = df['融资'].apply(extract_stage_score)


# 规模处理
# 定义映射字典（从小到大排序）
scale_map = {
    '0-20人': 1,
    '20-99人': 2,
    '100-499人': 3,
    '500-999人': 4,
    '1000-9999人': 5,
    '10000人以上': 6
}

# 映射生成新列
df['规模等级'] = df['规模'].map(scale_map)

# 只要这一列是空值，就删除这一整行
df = df.dropna(subset=['要求'])

# 删除后，数据的索引（行号）会变得不连续，重置一下索引
df = df.reset_index(drop=True)

# 打印一下剩余的数据量，确认删除成功
print(f"删除空值后，剩余数据量：{len(df)} 条")

df.to_csv("data.csv", index=False, encoding="utf-8-sig")