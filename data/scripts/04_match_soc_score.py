import re
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

# ===== 1. 明文特例對照表 =====
EXPLICIT_MAP: dict[str, str] = {
    "samsung-google-tensor-g3-gs301-s5p9865": "Google Tensor G3",
    "samsung-google-tensor-g2-gs201-s5p9855": "Google Tensor G2",
    "qualcomm-snapdragon-8-gen-1-5g-sm8475": "Qualcomm Snapdragon 8+ Gen 1",
    "mediatek-dimensity-8400-ultra-mt6899": "MediaTek Dimensity 8400",
    "mediatek-dimensity-8300-ultra-mt6897": "MediaTek Dimensity 8300",
    "mediatek-dimensity-7300x-mt6878": "MediaTek Dimensity 7300",
    "mediatek-dimensity-6100-mt6835": "MediaTek Dimensity 6100+",
    "snapdragon-778g-plus": "Qualcomm Snapdragon 778G+ 5G",
    "unisoc-t616": "Unisoc T616",
    "unisoc-tiger-t616": "Unisoc T616",
    "unisoc-tiger-t606-ums9230": "Unisoc Tiger T606",
    "unisoc-t606": "Unisoc Tiger T606",
    "unisoc-t612": "Unisoc Tiger T612",
    "kirin-9000s": "Huawei Kirin 9000S",
    "kirin-710a": "Huawei Kirin 710A",
    "kirin-9010": "Huawei Kirin 9010",
    "unisoc-sc9863": "Unisoc SC9863A",
}

# 無效的垃圾佔位符（直接轉為 None，不參與配對）
INVALID_SOC_SLUGS = {
    "0", "0.0", "qualcomm", "qualcomm-snapdragon",
    "mediatek", "mediatek-helio", "samsung-exynos", "apple", "unisoc"
}

BRAND_PREFIXES = ("qualcomm ", "mediatek ", "samsung ", "apple ", "hisilicon ", "google ", "unisoc ", "huawei ")


def normalize_soc_str(text: str) -> str:
    """統一處理連字號與 plus 符號差異"""
    if pd.isna(text):
        return ""
    s = str(text).lower().replace("-", " ")
    s = re.sub(r"\s+plus\b", "+", s)
    return " ".join(s.split())


def strip_brand(clean_name: str) -> str:
    """移除開頭廠牌名稱"""
    for prefix in BRAND_PREFIXES:
        if clean_name.startswith(prefix):
            return clean_name[len(prefix):].strip()
    return clean_name


# ===== 2. 讀取資料 =====
phones_df = pd.read_csv(PHONES_PATH, encoding="utf-8-sig", low_memory=False)
soc_df = pd.read_csv(SOC_PATH, encoding="utf-8-sig")

soc_score_map = dict(zip(soc_df["name"], soc_df["inno_score"]))

candidates = []
for name in soc_df["name"].dropna().unique():
    full_clean = normalize_soc_str(name)
    short_clean = strip_brand(full_clean)
    candidates.append((full_clean, short_clean, name))

candidates.sort(key=lambda x: len(x[1]), reverse=True)


def match_standard_soc(raw_slug: str) -> str | None:
    if pd.isna(raw_slug):
        return None

    raw_slug_str = str(raw_slug).strip().lower()
    if not raw_slug_str or raw_slug_str in INVALID_SOC_SLUGS:
        return None

    # 1. 先查明文特例表
    if raw_slug_str in EXPLICIT_MAP:
        return EXPLICIT_MAP[raw_slug_str]

    target = f" {normalize_soc_str(raw_slug_str)} "

    # 2. 第一輪：完整標準名稱精準比對
    for full_clean, _, original_name in candidates:
        if f" {full_clean} " in target:
            return original_name

    # 3. 第二輪：去廠牌短名稱比對
    for _, short_clean, original_name in candidates:
        if len(short_clean) >= 4 and f" {short_clean} " in target:
            return original_name

    return None


# ===== 3. 套用比對並合併分數 =====
phones_df["soc_raw"] = phones_df["soc"]
phones_df.loc[
    phones_df["soc_raw"].astype(str).str.strip().str.lower().isin(INVALID_SOC_SLUGS),
    "soc_raw"
] = None

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

valid_soc_count = phones_df["soc_raw"].notna().sum()
matched_count = phones_df["soc_score"].notna().sum()

print(f"總計手機筆數：{phones_df.shape[0]}（其中具備有效 SoC 字串：{valid_soc_count} 筆）")
print(f"成功配對分數：{matched_count} 筆（有效配對率：{matched_count / max(valid_soc_count, 1):.1%}）")

if not unmatched.empty:
    print("\n⚠️ 以下 SoC 尚未配對到分數（可直接複製進 EXPLICIT_MAP）：")
    for slug, count in unmatched.items():
        print(f'    "{slug}": "",  # {count} 筆')
else:
    print("\n✅ 所有有效處理器皆已成功配對！")

# ===== 5. 線性正規化分數 =====
s_min = phones_df["soc_score"].min()
s_max = phones_df["soc_score"].max()

target_min = soc_df["inno_score"].min()
target_max = soc_df["inno_score"].max()

phones_df["normalized_soc_score"] = (
        target_min + ((phones_df["soc_score"] - s_min) / (s_max - s_min)) * (target_max - target_min)
).round(2)

# ===== 6. 輸出至 processed =====
OUTPUT_PATH = PROCESSED_DIR / "phones.csv"
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
phones_df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")

print(f"\n已輸出最終寬表：{OUTPUT_PATH}")

# ===== 7. 自動反查未配對 SoC 在 Ranking 表裡的可能候選 =====
if not unmatched.empty:
    print("\n🔍 Ranking 表中可能對應的候選名稱：")
    for slug in unmatched.index:
        tokens = [
            t for t in re.split(r"[-_]", slug.lower())
            if
            t not in {"qualcomm", "mediatek", "unisoc", "samsung", "plus", "helio", "dimensity", "snapdragon"} and len(
                t) >= 3
        ]
        if not tokens:
            continue
        pattern = "|".join(re.escape(t) for t in tokens)
        matches = soc_df[soc_df["name"].str.contains(pattern, case=False, na=False)]["name"].tolist()
        print(f"  {slug:<35} -> {matches if matches else '❌ 表中無任何相近項目'}")
