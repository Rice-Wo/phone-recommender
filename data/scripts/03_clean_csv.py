import re
from pathlib import Path

import pandas as pd

# ===== 設定 =====
ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
INTERIM_DIR = DATA_DIR / "interim"

CSV_PATH = RAW_DIR / "phones.csv"

if not CSV_PATH.is_file():
    raise FileNotFoundError(CSV_PATH)

df = pd.read_csv(CSV_PATH, encoding="utf-8-sig", low_memory=False)

# ===== 1. 保留已驗證資料 =====
df = df.loc[df["verified"].eq(True)].copy()

# ===== 2. 跨資料來源的市場篩選（涵蓋所有品牌） =====
mc = df["market_countries"].fillna("")
mr = df["market_regions"].fillna("")
vmc = df["variant.market_country"].fillna("")
vr = df["variant.region"].fillna("")

# 條件 A：明確標註台灣（涵蓋各來源的國家欄位）
is_taiwan = (
        mc.str.contains(r"\bTaiwan\b", case=False, regex=True)
        | vmc.str.contains(r"\bTaiwan\b|\bTW\b", case=False, regex=True)
)

# 條件 B：全球/國際通用版（涵蓋 phonedb 的 Worldwide 與 smartprix 的 global）
is_global = (
        mc.str.contains(r"\bGlobal\b|\bWorldwide\b", case=False, regex=True)
        | mr.str.contains(r"\bGlobal\b|\bWorldwide\b", case=False, regex=True)
        | vmc.str.contains(r"\bGlobal\b|\bWorldwide\b", case=False, regex=True)
        | vr.str.contains(r"\bGlobal\b|\bWorldwide\b", case=False, regex=True)
)

# 設定優先權：1 = 明確台灣版 > 2 = 全球版
df["_region_priority"] = 99
df.loc[is_global, "_region_priority"] = 2
df.loc[is_taiwan, "_region_priority"] = 1

df = df.loc[df["_region_priority"] < 99].copy()


# ===== 3. 提取純淨行銷型號並去重（台灣版優先於全球版） =====
def extract_canonical_name(row) -> str:
    name = str(row.get("name", "")).strip()
    brand = str(row.get("brand", "")).strip()

    # 去掉括號內容，如 (Apple iPhone 15,4) 或 (Global)
    clean = re.sub(r"\s*\([^)]*\)", "", name)

    # 從常見的通訊制式、SIM卡規格、容量或地區後綴處截斷，保留純型號
    # 例如 "Apple iPhone 15 5G A3089 Dual SIM..." -> "Apple iPhone 15"
    clean = re.split(
        r"\s+(?:5G|4G|LTE|TD-LTE|Dual\s+SIM|Single\s+SIM|Global|International|Unlocked|\d+(?:GB|TB))\b",
        clean,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]

    clean = re.sub(r"\s+", " ", clean).strip().lower()
    return f"{brand.lower()}::{clean}"


df["_canonical_model"] = df.apply(extract_canonical_name, axis=1)

# 依優先權排序（1 在前），同一款手機只保留台灣版（若無則保留全球版）
# 註：若同一型號有多筆相同優先權（例如不同容量變體），保留最新或資訊最完整的一筆
df = (
    df.sort_values(by=["_region_priority", "release_date"], ascending=[True, False])
    .drop_duplicates(subset=["_canonical_model"], keep="first")
)

# ===== 4. 刪除全空欄位 =====
df = df.dropna(axis=1, how="all")

# ===== 5. 刪除原始來源欄位 =====
raw_columns = [
    column for column in df.columns
    if column.startswith(("raw_smartprix.", "raw_phones_2024.", "raw_aitoolbuzz."))
]
df = df.drop(columns=raw_columns)

# ===== 6. 檢視並刪除低完整度欄位 =====
MIN_COMPLETENESS = 0.7

completeness = df.notna().mean().sort_values(ascending=False)

print("\n=== 所有欄位完整度一覽 ===")
for col, ratio in completeness.items():
    status = "保留" if ratio >= MIN_COMPLETENESS else "刪除 ❌"
    print(f"{col:<30} : {ratio:>6.1%}  [{status}]")

low_completeness_columns = completeness[completeness < MIN_COMPLETENESS].index
df = df.drop(columns=low_completeness_columns)

# ===== 7. 刪除不需要的欄位（包含暫存輔助欄位） =====
REMOVE_COLUMNS = [
    "image_url",
    "image_attribution",
    "image_license",
    "variant.market_regions",
    "variant.market_country",
    "variant.region",
    "variant.memory.ram_gb",
    "display.size",
    "source_urls",
    "verified",
    "base_model_slug",
    "market_countries",
    "market_regions",
    "_region_priority",
    "_canonical_model",
]

df = df.drop(columns=REMOVE_COLUMNS, errors="ignore")

# ===== 8. 結果摘要 =====
print(f"保留資料：{len(df)} 筆")
print("\n各品牌保留筆數分佈：")
print(df["brand"].value_counts().to_string())
print(f"\n保留欄位：{len(df.columns)} 個")

# ===== 9. 輸出中繼清理後資料 =====
OUTPUT_PATH = INTERIM_DIR / "phones.csv"
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")

print(f"\n已輸出：{OUTPUT_PATH}")
