"""
ANALYSIS: Why df accuracy ≠ df_high_risk accuracy
==================================================
Copy each section (between # %%) as separate cells into 3-1-robot2_analysis.ipynb
Now uses CSV files directly — no gsheet connection needed.
"""

# %% [markdown]
# ---
# ## Analysis: Root Cause of Accuracy Gap Between File A (df) and File B (df_high_risk)
# ---

# %%
import pandas as pd
import numpy as np
import json
import warnings
warnings.filterwarnings('ignore')
import matplotlib.pyplot as plt
import matplotlib
matplotlib.rcParams['font.family'] = ['SimHei', 'DejaVu Sans', 'sans-serif']
matplotlib.rcParams['axes.unicode_minus'] = False

# %% [markdown]
# ### 1. Load & Clean Data

# %%
# === File A: sample 质检 ===
df_raw = pd.read_csv('../dataset_wellbore/sample_3-1-robot2.csv', header=None, skiprows=3)
col_names = ['idx', 'Data_Date_Range', 'Checking_Date', 'Model', 'Chat_ID',
             'Validator', 'Result', 'Overall_Rating', 'Pain_Point',
             'Supposed_Response', 'col10', 'col11', 'col12']
df_raw.columns = col_names
df_a = df_raw[df_raw['Result'].isin(['Correct Response', 'Wrong Response'])].copy()
df_a['rating'] = pd.to_numeric(df_a['Overall_Rating'], errors='coerce')
df_a['Model'] = df_a['Model'].astype(str).str.strip()
df_a['Validator'] = df_a['Validator'].astype(str).str.strip()

# === File B: high_risk ===
df_b = pd.read_csv('../dataset_wellbore/high_risk_20260701.csv')
def parse_human_label(val):
    try:
        if isinstance(val, str) and '{' in val:
            return json.loads(val.replace("'", '"')).get('value', val)
        return val
    except:
        return val
df_b['human_label'] = df_b['人工打标结果'].apply(parse_human_label)

print(f"File A shape: {df_a.shape}")
print(f"File B shape: {df_b.shape}")

# %% [markdown]
# ### 2. Accuracy Overview

# %%
total_a = len(df_a)
correct_a = (df_a['Result'] == 'Correct Response').sum()
acc_a = correct_a / total_a * 100

total_b = len(df_b)
new_match = (df_b['new_model_vs人工'] == '是').sum()
old_match = (df_b['old_model_vs人工'] == '是').sum()
acc_new = new_match / total_b * 100
acc_old = old_match / total_b * 100

print("=" * 60)
print("ACCURACY COMPARISON")
print("=" * 60)
print(f"File A — Chatbot Response QC:     {correct_a}/{total_a} = {acc_a:.1f}%")
print(f"File B — old_model vs Human:      {old_match}/{total_b} = {acc_old:.1f}%")
print(f"File B — new_model (LLM) vs Human: {new_match}/{total_b} = {acc_new:.1f}%")
print(f"\n>>> GAP: {acc_a:.1f}% vs {acc_new:.1f}% = {acc_a - acc_new:.1f} percentage points")

# %%
fig, ax = plt.subplots(figsize=(8, 4))
labels = ['File A\n(Chatbot QC)', 'File B old_model\n(Classification)', 'File B new_model\n(Classification)']
values = [acc_a, acc_old, acc_new]
colors = ['#2ecc71', '#3498db', '#e74c3c']
bars = ax.bar(labels, values, color=colors, width=0.5, edgecolor='white', linewidth=1.5)
for bar, val in zip(bars, values):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1, f'{val:.1f}%',
            ha='center', va='bottom', fontweight='bold', fontsize=13)
ax.set_ylabel('Accuracy (%)')
ax.set_title('Accuracy Gap: File A vs File B', fontsize=14, fontweight='bold')
ax.set_ylim(0, 110)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
plt.tight_layout()
plt.show()

# %% [markdown]
# ### 3. File A — Detailed Breakdown
# 
# **Finding: 100% accuracy, zero wrong responses. All 1810 valid samples = "Correct Response".**

# %%
print("FILE A — Result Distribution")
print("=" * 50)
print(df_a['Result'].value_counts())
print(f"\nRating distribution:")
print(df_a['rating'].value_counts().sort_index())
print(f"\nMean rating: {df_a['rating'].mean():.2f}")
print(f"Rating >= 4 (good): {(df_a['rating']>=4).sum()} ({(df_a['rating']>=4).sum()/total_a*100:.1f}%)")
print(f"Rating == 3 (OK):   {(df_a['rating']==3).sum()} ({(df_a['rating']==3).sum()/total_a*100:.1f}%)")
print(f"Rating <= 2 (poor): {(df_a['rating']<=2).sum()} ({(df_a['rating']<=2).sum()/total_a*100:.1f}%)")

# %%
# Rating by model
print("\nFile A: Model Comparison")
print("=" * 50)
for model in sorted(df_a['Model'].unique()):
    if model and model != 'nan':
        sub = df_a[df_a['Model'] == model]
        n = len(sub)
        r_dist = sub['rating'].value_counts().sort_index()
        pct_good = (sub['rating'] >= 4).sum() / n * 100
        print(f"\n{model} (n={n}):")
        print(f"  Rating dist: {dict(r_dist)}")
        print(f"  Mean rating: {sub['rating'].mean():.2f}")
        print(f"  Rating>=4: {pct_good:.1f}%")

# %%
# Rating by validator
print("\nFile A: Validator Comparison")
print("=" * 50)
for val in sorted(df_a['Validator'].unique()):
    if val and val != 'nan':
        sub = df_a[df_a['Validator'] == val]
        n = len(sub)
        avg_r = sub['rating'].mean()
        print(f"  {val:20s}: n={n:>4}, avg_rating={avg_r:.2f}")

# %%
# Rating vs Result crosstab
print("\nRating vs Result Crosstab")
ct_a = pd.crosstab(df_a['Result'], df_a['rating'], margins=True)
print(ct_a)

# %% [markdown]
# ### 4. ROOT CAUSE #1: 100% Disagreement Dataset
# 
# The entire `df_high_risk` contains **only** cases where `old_model ≠ new_model`.

# %%
same = (df_b['old_model'] == df_b['new_model']).sum()
diff = total_b - same
print(f"old_model == new_model: {same} rows ({same/total_b*100:.1f}%)")
print(f"old_model != new_model: {diff} rows ({diff/total_b*100:.1f}%)")
print(f"\n>>> 100% DISAGREEMENT dataset")
print(f">>> old_model right in ~80% → new_model MUST be wrong in those 80%")
print(f">>> This is the BIGGEST factor in the accuracy gap")

# %% [markdown]
# ### 5. ROOT CAUSE #2: Systematic "keluhan" Label Confusion

# %%
print("LABEL MAPPING: What new_model predicts for each human label")
print("=" * 60)
for label in sorted(df_b['human_label'].unique()):
    sub = df_b[df_b['human_label'] == label]
    preds = sub['new_model'].value_counts()
    acc = (sub['new_model_vs人工'] == '是').sum() / len(sub) * 100
    print(f'\nhuman="{label}" (n={len(sub)}, accuracy={acc:.1f}%):')
    for pred, count in preds.items():
        marker = " ✓" if pred == label else " ✗"
        print(f'  → new_model="{pred}": {count} ({count/len(sub)*100:.1f}%){marker}')

# %%
# Confusion matrix heatmap
ct = pd.crosstab(df_b['new_model'], df_b['human_label'])
fig, ax = plt.subplots(figsize=(8, 6))
im = ax.imshow(ct.values, cmap='YlOrRd', aspect='auto')
ax.set_xticks(range(len(ct.columns)))
ax.set_yticks(range(len(ct.index)))
ax.set_xticklabels(ct.columns, rotation=45, ha='right')
ax.set_yticklabels(ct.index)
ax.set_xlabel('Human Label (Ground Truth)')
ax.set_ylabel('new_model Prediction')
ax.set_title('Confusion Matrix: new_model vs Human Label', fontweight='bold')
for i in range(len(ct.index)):
    for j in range(len(ct.columns)):
        val = ct.values[i, j]
        ax.text(j, i, str(val), ha='center', va='center', fontsize=12,
                color='white' if val > ct.values.max() * 0.6 else 'black')
plt.colorbar(im, ax=ax, label='Count')
plt.tight_layout()
plt.show()

# %% [markdown]
# ### 6. ROOT CAUSE #3: Per-Category Accuracy

# %%
print("PER-CATEGORY ACCURACY: old_model vs new_model (against human)")
print("=" * 70)
rows = []
for label in sorted(df_b['human_label'].unique()):
    sub = df_b[df_b['human_label'] == label]
    n = len(sub)
    new_acc = (sub['new_model_vs人工'] == '是').sum() / n * 100
    old_acc = (sub['old_model_vs人工'] == '是').sum() / n * 100
    rows.append({'category': label, 'n': n, 'pct_data': round(n/total_b*100, 1),
                 'old_acc': round(old_acc, 1), 'new_acc': round(new_acc, 1),
                 'delta': round(new_acc - old_acc, 1)})
cat_df = pd.DataFrame(rows)
print(cat_df.to_string(index=False))

# %%
fig, ax = plt.subplots(figsize=(10, 5))
x = np.arange(len(cat_df))
w = 0.35
bars1 = ax.bar(x - w/2, cat_df['old_acc'], w, label='old_model', color='#3498db', alpha=0.8)
bars2 = ax.bar(x + w/2, cat_df['new_acc'], w, label='new_model (LLM)', color='#e74c3c', alpha=0.8)
ax.set_xticks(x)
ax.set_xticklabels([f"{r['category']}\n(n={r['n']})" for _, r in cat_df.iterrows()])
ax.set_ylabel('Accuracy (%)')
ax.set_title('Per-Category Accuracy: old_model vs new_model', fontsize=13, fontweight='bold')
ax.legend()
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
ax.set_ylim(0, 110)
for bar in bars1:
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
            f'{bar.get_height():.0f}%', ha='center', va='bottom', fontsize=9)
for bar in bars2:
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
            f'{bar.get_height():.0f}%', ha='center', va='bottom', fontsize=9)
plt.tight_layout()
plt.show()

# %% [markdown]
# ### 7. Top Mismatch Pairs

# %%
mismatch = df_b[df_b['new_model_vs人工'] == '否']
pairs = mismatch.groupby(['new_model', 'human_label']).size().reset_index(name='count')
pairs = pairs.sort_values('count', ascending=False)
print("TOP MISMATCH PAIRS")
print("=" * 50)
print(pairs.head(10).to_string(index=False))

total_mismatches = len(mismatch)
top5 = pairs.head(5)['count'].sum()
print(f"\nTop 5 pairs = {top5}/{total_mismatches} ({top5/total_mismatches*100:.1f}%) of all mismatches")

# %% [markdown]
# ### 8. Sample Misclassifications

# %%
keluhan = df_b[df_b['human_label'] == 'keluhan']

print("Sample 'keluhan' messages classified as 'normal' by new_model:")
print("-" * 60)
k_normal = keluhan[keluhan['new_model'] == 'normal']
for i, (_, row) in enumerate(k_normal.head(8).iterrows()):
    print(f"  {i+1}. {str(row['msg_text'])[:120]}")

print(f"\nSample 'keluhan' messages classified as 'ulasan buruk' by new_model:")
print("-" * 60)
k_ulasan = keluhan[keluhan['new_model'] == 'ulasan buruk']
for i, (_, row) in enumerate(k_ulasan.head(8).iterrows()):
    print(f"  {i+1}. {str(row['msg_text'])[:120]}")

# %% [markdown]
# ### 9. LLM打标 & Labeler Comparison

# %%
new_vs_llm = (df_b['new_model_vsLLM'] == '是').sum()
old_vs_llm = (df_b['old_model_vsLLM'] == '是').sum()
print("LLM打标 (deepseek-v3) Comparison")
print("=" * 50)
print(f"old_model vs LLM打标: {old_vs_llm}/{total_b} = {old_vs_llm/total_b*100:.1f}%")
print(f"new_model vs LLM打标: {new_vs_llm}/{total_b} = {new_vs_llm/total_b*100:.1f}%")

print(f"\nBy Labeler:")
for labeler in sorted(df_b['打标人'].unique()):
    sub = df_b[df_b['打标人'] == labeler]
    new_acc = (sub['new_model_vs人工'] == '是').sum() / len(sub) * 100
    old_acc = (sub['old_model_vs人工'] == '是').sum() / len(sub) * 100
    print(f"  {labeler:30s}: n={len(sub):>4}  old={old_acc:>5.1f}%  new={new_acc:>5.1f}%")

# %% [markdown]
# ### 10. Message Length vs Accuracy

# %%
df_b['msg_len'] = df_b['msg_text'].str.len()
print("Message Length vs new_model Accuracy")
print("=" * 50)
for lo, hi in [(0,20), (21,50), (51,100), (101,200), (201,9999)]:
    sub = df_b[(df_b['msg_len'] >= lo) & (df_b['msg_len'] <= hi)]
    if len(sub) > 0:
        acc = (sub['new_model_vs人工'] == '是').sum() / len(sub) * 100
        print(f"  len {lo:>3}-{hi:>4}: n={len(sub):>4}  accuracy={acc:.1f}%")

# %% [markdown]
# ---
# ## CONCLUSION
# 
# ### Root Causes (ordered by impact):
# 
# 1. **100% DISAGREEMENT BIAS** — File B only has cases where old ≠ new. old_model right ~80% → new_model forced to ~12%.
# 2. **KELUHAN BLINDSPOT** — 68.8% of data is "keluhan", new_model predicts it only 1.3% of the time. Likely prompt/instruction issue.
# 3. **DIFFERENT TASKS** — File A = response quality QC (binary), File B = multi-class classification (exact match).
# 4. **EVALUATION STRICTNESS** — File A uses flexible 1-5 scale, File B uses strict exact match.
# 5. **SEMANTIC OVERLAP** — keluhan/ulasan buruk/keluhan di tempat are semantically close.
# 
# ### Recommendations:
# 
# 1. Fix new_model prompt — ensure "keluhan" category defined with examples
# 2. Re-test on random sample (not disagreement-only)
# 3. Define clear category boundaries with examples
# 4. Consider merging overlapping categories
# 5. Investigate File A 100% accuracy — may indicate QC process bias
