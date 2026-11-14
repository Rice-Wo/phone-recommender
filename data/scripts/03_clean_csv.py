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

# ===== 保留已驗證資料 =====
df = df.loc[df["verified"].eq(True)].copy()

# ===== 市場篩選 =====
mask = (
        df["market_countries"].fillna("").str.contains(
            r"\bTaiwan\b|\bGlobal\b|\bWorldwide\b",
            case=False, regex=True
        )
        | df["market_regions"].fillna("").str.contains(
    r"\bGlobal\b|\bWorldwide\b",
    case=False, regex=True
)
)

df = df.loc[mask].copy()

# ===== 刪除全空欄位 =====
df = df.dropna(axis=1, how="all")

# ===== 刪除原始來源欄位 =====
raw_columns = [
    column for column in df.columns
    if column.startswith(("raw_smartprix.", "raw_phones_2024."))
]
df = df.drop(columns=raw_columns)

# ===== 刪除低完整度欄位 =====
MIN_COMPLETENESS = 0.7

completeness = df.notna().mean()
low_completeness_columns = completeness[
    completeness < MIN_COMPLETENESS
    ].index

df = df.drop(columns=low_completeness_columns)

# ===== 刪除不需要的欄位 =====
REMOVE_COLUMNS = [
    "image_url",
    "image_attribution",
    "image_license",
    "variant.market_regions",
    "variant.memory.ram_gb",
    "display.size",
    "source_urls",
    "verified",
    "base_model_slug",
    "market_countries",
    "market_regions"
]

df = df.drop(columns=REMOVE_COLUMNS, errors="ignore")

# ===== 結果摘要 =====
print(f"保留資料：{len(df)} 筆")
print(f"保留欄位：{len(df.columns)} 個")

# ===== 輸出中繼清理後資料 =====
OUTPUT_PATH = INTERIM_DIR / "phones.csv"
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")

print(f"已輸出：{OUTPUT_PATH}")