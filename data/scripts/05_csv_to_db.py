import sqlite3
from pathlib import Path

import pandas as pd

# 路徑設定（以 data/scripts/ 往上兩層為專案根目錄）
BASE_DIR = Path(__file__).resolve().parents[2]
PROCESSED_CSV = BASE_DIR / "data" / "processed" / "phones.csv"
DB_PATH = BASE_DIR / "data" / "phones.db"


def create_schema(conn: sqlite3.Connection) -> None:
    """建立資料表結構與常用查詢索引"""
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS phones;")

    cursor.execute("""
        CREATE TABLE phones (
            slug TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            brand TEXT NOT NULL,
            release_date TEXT,
            ram_gb REAL,
            battery_mah INTEGER,
            weight_g REAL,
            os TEXT,
            storage_options_gb TEXT,
            soc TEXT,
            display_resolution TEXT,
            display_type TEXT,
            display_size_inch REAL,
            display_ppi REAL,
            soc_raw TEXT,
            soc_score REAL,
            normalized_soc_score REAL
        );
    """)

    cursor.execute("CREATE INDEX idx_phones_brand ON phones(brand);")
    cursor.execute("CREATE INDEX idx_phones_os ON phones(os);")
    cursor.execute("CREATE INDEX idx_phones_ram ON phones(ram_gb);")
    cursor.execute("CREATE INDEX idx_phones_soc_score ON phones(normalized_soc_score);")
    conn.commit()


def main() -> None:
    if not PROCESSED_CSV.exists():
        raise FileNotFoundError(f"找不到輸入檔案：{PROCESSED_CSV}")

    df = pd.read_csv(PROCESSED_CSV)
    df.columns = df.columns.str.replace(".", "_", regex=False)

    # 主鍵防呆：移除 slug 為空或重複的資料
    before_count = df.shape[0]
    df = df.dropna(subset=["slug"]).drop_duplicates(subset=["slug"], keep="first")
    dropped = before_count - df.shape[0]
    if dropped > 0:
        print(f"警告：已過濾 {dropped} 筆重複或無效的 slug 資料")

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DB_PATH) as conn:
        create_schema(conn)

        # 使用 append 將資料灌入已定義好 PRIMARY KEY 與 INDEX 的資料表中
        df.to_sql("phones", conn, if_exists="append", index=False)

        # 驗證寫入結果
        count = conn.execute("SELECT COUNT(*) FROM phones;").fetchone()[0]
        print(f"成功建立 SQLite 資料庫：{DB_PATH}")
        print(f"資料表 phones 總計筆數：{count} 筆")


if __name__ == "__main__":
    main()
