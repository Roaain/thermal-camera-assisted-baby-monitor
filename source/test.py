import numpy as np
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif'] = ['Noto Sans CJK JP', 'Noto Sans CJK SC', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False


# 模拟生成一个 20行 x 2列 的数据（用数字0~39填充，方便观察颜色变化）
# 假设 4001 在这里简化为 5，便于演示
N = 20
SHIFT = 5

# 生成模拟数据：第一列是索引，第二列是数值（用颜色深浅表示）
temp_table = np.arange(N * 2).reshape(N, 2)
# 为了更直观，把第二列设为 100~119
temp_table[:, 1] = np.arange(100, 100 + N)

# ---- 1. 原始数据 ----
original = temp_table.copy()

# ---- 2. 错误的 hstack（会改变列数） ----
# 注意：为了能 hstack 成功，需要保证两段行数一致，这里 N=20, SHIFT=5, 需要 N-SHIFT == SHIFT? 不。
# 标准情况下 hstack 会报错，为了演示形状，我们强制切成两段行数相等的 (N必须=2*SHIFT)
# 修改：为演示画图，强制把 N 重新设为 10，SHIFT=5，让 hstack 可以执行。
N = 10
SHIFT = 5
temp_table = np.arange(N * 2).reshape(N, 2)
temp_table[:, 1] = np.arange(100, 100 + N)

# 错误操作：水平拼接
try:
    # 注意：这里行数刚好相等(5和5)，所以不会报错，但结果形状变成了 (5, 4)
    wrong_result = np.hstack((temp_table[SHIFT:], temp_table[:SHIFT]))
    can_show_wrong = True
except ValueError:
    wrong_result = None
    can_show_wrong = False
    print("注意：如果行数不匹配，hstack 直接报错无法执行。此处为了演示强制让行数匹配。")

# 正确操作：垂直拼接
correct_result = np.vstack((temp_table[SHIFT:], temp_table[:SHIFT]))

# ---- 开始画图 ----
fig, axes = plt.subplots(1, 3, figsize=(12, 4))

# 子图1：原始矩阵
axes[0].imshow(original, aspect='auto', cmap='viridis')
axes[0].set_title(f'1. 原始数据 (N={N}, 2列)')
axes[0].set_xlabel('列索引 (0=Key, 1=Value)')
axes[0].set_ylabel('行号')
for i in range(original.shape[0]):
    for j in range(original.shape[1]):
        axes[0].text(j, i, str(original[i, j]), ha='center', va='center', color='white', fontsize=8)

# 子图2：错误拼接（如果可执行）
if can_show_wrong:
    axes[1].imshow(wrong_result, aspect='auto', cmap='tab20')
    axes[1].set_title(f'2. 错误: np.hstack (形状={wrong_result.shape})\n(列数变成4，破坏数据结构)')
    axes[1].set_xlabel('列索引 (0,1=后半段 | 2,3=前半段)')
    for i in range(wrong_result.shape[0]):
        for j in range(wrong_result.shape[1]):
            axes[1].text(j, i, str(wrong_result[i, j]), ha='center', va='center', color='white', fontsize=8)
else:
    axes[1].text(0.5, 0.5, 'hstack 因形状不匹配\n直接报错崩溃', ha='center', va='center', transform=axes[1].transAxes)
    axes[1].set_title('2. 错误: 程序崩溃')

# 子图3：正确拼接
axes[2].imshow(correct_result, aspect='auto', cmap='viridis')
axes[2].set_title(f'3. 正确: np.vstack (形状={correct_result.shape})\n(保持2列，仅行重排)')
axes[2].set_xlabel('列索引 (0=Key, 1=Value)')
for i in range(correct_result.shape[0]):
    for j in range(correct_result.shape[1]):
        axes[2].text(j, i, str(correct_result[i, j]), ha='center', va='center', color='white', fontsize=8)

plt.tight_layout()
# plt.show()
plt.savefig('result.png')
print("圖表已成功儲存為 result.png")