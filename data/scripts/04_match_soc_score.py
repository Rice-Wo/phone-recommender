from pathlib import Path

import pandas as pd

# ===== 路徑設定 =====
ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
INTERIM_DIR = DATA_DIR / "interim"
PROCESSED_DIR = DATA_DIR / "processed"

PHONES_PATH = INTERIM_DIR / "phones.csv"
SOC_PATH = RAW_DIR / "innoreviews-soc-ranking-2026-11-09.csv"

# ===== 1. 明文特例對照表（針對「名稱結構不同」的少數特例） =====
# 左邊：phones.csv 裡的原始 slug / 右邊：innoreviews 表裡的標準名稱
EXPLICIT_MAP: dict[str, str] = {
    # Samsung 代工的 Google Tensor 前面多了 samsung-
    "samsung-google-tensor-g3-gs301-s5p9865": "Google Tensor G3",
    "samsung-google-tensor-g2-gs201-s5p9855": "Google Tensor G2",
    # sm8475 實際上是 Snapdragon 8+ Gen 1（你的來源寫成 8-gen-1-5g-sm8475）
    "qualcomm-snapdragon-8-gen-1-5g-sm8475": "Qualcomm Snapdragon 8+ Gen 1",
    # 聯發科 Ultra / X 特調版（若 ranking 表只有標準版名稱可這樣對應，若 ranking 表有 Ultra 則可刪掉）
    "mediatek-dimensity-8400-ultra-mt6899": "MediaTek Dimensity 8400",
    "mediatek-dimensity-8300-ultra-mt6897": "MediaTek Dimensity 8300",
    "mediatek-dimensity-7300x-mt6878": "MediaTek Dimensity 7300",
    # 展銳（若 ranking 表沒收錄則保留 None，或填入對應名稱）
    "unisoc-tiger-t606-ums9230": "Unisoc Tiger T606",
    "mediatek-dimensity-6100-mt6835": "MediaTek Dimensity 6100+",
}


def clean_text(text: str) -> str:
    """純粹把連字號換成空白並轉小寫，不用任何正則"""
    if pd.isna(text):
        return ""
    return " ".join(str(text).lower().replace("-", " ").split())


# ===== 2. 讀取資料 =====
phones_df = pd.read_csv(PHONES_PATH, encoding="utf-8-sig", low_memory=False)
soc_df = pd.read_csv(SOC_PATH, encoding="utf-8-sig")

# 建立標準名稱 -> 分數的查詢字典
soc_score_map = dict(zip(soc_df["name"], soc_df["inno_score"]))

# 將 Ranking 表的標準名稱依字串長度「由長到短」排序（避免短名稱搶先誤判長名稱）
candidates = sorted(
    [(clean_text(name), name) for name in soc_df["name"].dropna().unique()],
    key=lambda x: len(x[0]),
    reverse=True,
)


def match_standard_soc(raw_slug: str) -> str | None:
    if pd.isna(raw_slug):
        return None

    # 1. 先查明文特例表
    if raw_slug in EXPLICIT_MAP:
        return EXPLICIT_MAP[raw_slug]

    # 2. 用 Ranking 表的標準名稱由長到短做包含比對（加前後空白避免子字串誤判，例如 700 誤判 7000）
    target = f" {clean_text(raw_slug)} "
    for clean_cand, original_name in candidates:
        if f" {clean_cand} " in target:
            return original_name

    return None


# ===== 3. 套用比對並合併分數 =====
phones_df["soc_raw"] = phones_df["soc"]
phones_df["soc"] = phones_df["soc_raw"].apply(match_standard_soc)
phones_df["soc_score"] = phones_df["soc"].map(soc_score_map)

# 若有沒對到的，soc 欄位暫時填回原始值以免變空值
phones_df["soc"] = phones_df["soc"].fillna(phones_df["soc_raw"])

# ===== 4. 檢查未配對項目 =====
unmatched = (
    phones_df.loc[phones_df["soc_score"].isna(), "soc_raw"]
    .dropna()
    .value_counts()
)

print(f"總計手機筆數：{phones_df.shape[0]}")
print(f"成功配對分數：{phones_df['soc_score'].notna().sum()} 筆")

if not unmatched.empty:
    print("\n⚠️ 以下 SoC 尚未配對到分數（可直接複製進 EXPLICIT_MAP）：")
    for slug, count in unmatched.items():
        print(f'    "{slug}": "",  # {count} 筆')
else:
    print("\n✅ 所有處理器皆已成功配對！")
# 1. 取得目前 255 筆手機子集的實際上下界 (24.4 ~ 79.7)
s_min = phones_df["soc_score"].min()
s_max = phones_df["soc_score"].max()

# 2. 取得目標區間上下界（InnoReviews 全表上下界：24.1 ~ 95.5）
target_min = soc_df["inno_score"].min()  # 24.1
target_max = soc_df["inno_score"].max()  # 95.5

# 3. 線性對應（將 [24.4, 79.7] 映射到 [24.1, 95.5]）
phones_df["normalized_soc_score"] = (
        target_min + ((phones_df["soc_score"] - s_min) / (s_max - s_min)) * (target_max - target_min)
).round(2)
# ===== 5. 輸出至 processed =====
OUTPUT_PATH = PROCESSED_DIR / "phones.csv"
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
phones_df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")

print(f"\n已輸出最終寬表：{OUTPUT_PATH}")
