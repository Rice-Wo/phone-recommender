import ast
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Optional

from .model import Phone

# 專案根目錄 (src/phone_recommender/catalog/repository.py -> 往上 3 層)
BASE_DIR = Path(__file__).resolve().parents[3]
DB_PATH = BASE_DIR / "data" / "phones.db"


def _connect() -> sqlite3.Connection:
    """建立唯讀 SQLite 連線，避免意外寫入與檔案鎖定"""
    if not DB_PATH.exists():
        raise FileNotFoundError(f"找不到資料庫檔案：{DB_PATH}")
    uri = f"{DB_PATH.resolve().as_uri()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=5.0)
    conn.row_factory = sqlite3.Row
    return conn


def _parse_storage_options(raw: Optional[str]) -> tuple[int, ...]:
    """將資料庫中的 '[128, 256]' 字串安全解析為不可變的 tuple[int, ...]"""
    if not raw:
        return ()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        try:
            parsed = ast.literal_eval(raw)
        except (ValueError, SyntaxError):
            return ()
    if isinstance(parsed, (list, tuple)):
        return tuple(int(x) for x in parsed if isinstance(x, (int, float)))
    return ()


def _row_to_phone(row: sqlite3.Row) -> Phone:
    return Phone(
        slug=row["slug"],
        name=row["name"],
        brand=row["brand"],
        release_date=row["release_date"],
        ram_gb=row["ram_gb"],
        battery_mah=row["battery_mah"],
        weight_g=row["weight_g"],
        os=row["os"],
        storage_options_gb=_parse_storage_options(row["storage_options_gb"]),
        soc=row["soc"],
        display_resolution=row["display_resolution"],
        display_type=row["display_type"],
        display_size_inch=row["display_size_inch"],
        display_ppi=row["display_ppi"],
        soc_raw=row["soc_raw"],
        soc_score=row["soc_score"],
        normalized_soc_score=row["normalized_soc_score"],
    )


def load_all() -> list[Phone]:
    """載入所有手機資料（供決策樹訓練、向量特徵建置使用）"""
    with closing(_connect()) as conn:
        rows = conn.execute("SELECT * FROM phones;").fetchall()
        return [_row_to_phone(r) for r in rows]


def get_by_slug(slug: str) -> Optional[Phone]:
    """依主鍵 slug 精準查詢單支手機（供前端詳情頁、RAG 檢索使用）"""
    with closing(_connect()) as conn:
        row = conn.execute("SELECT * FROM phones WHERE slug = ?;", (slug,)).fetchone()
        return _row_to_phone(row) if row else None


def get_by_slugs(slugs: list[str]) -> list[Phone]:
    """依一組 slug 批量查詢並保留原始排序（供推薦引擎 Top-K 結果還原完整物件）"""
    if not slugs:
        return []

    unique_slugs = list(dict.fromkeys(slugs))
    placeholders = ",".join("?" for _ in unique_slugs)

    with closing(_connect()) as conn:
        rows = conn.execute(
            f"SELECT * FROM phones WHERE slug IN ({placeholders});",
            unique_slugs,
        ).fetchall()

    phone_map = {row["slug"]: _row_to_phone(row) for row in rows}
    return [phone_map[s] for s in slugs if s in phone_map]


def filter_by(
        *,
        brand: Optional[str] = None,
        min_ram_gb: Optional[float] = None,
        min_battery_mah: Optional[int] = None,
        max_weight_g: Optional[float] = None,
        min_soc_score: Optional[float] = None,
) -> list[Phone]:
    """依可選條件動態組合 WHERE 子句查詢（自動吃滿資料庫索引且防注入）"""
    conditions: list[str] = []
    params: list[object] = []

    if brand is not None:
        conditions.append("brand = ?")
        params.append(brand)
    if min_ram_gb is not None:
        conditions.append("ram_gb >= ?")
        params.append(min_ram_gb)
    if min_battery_mah is not None:
        conditions.append("battery_mah >= ?")
        params.append(min_battery_mah)
    if max_weight_g is not None:
        conditions.append("weight_g <= ?")
        params.append(max_weight_g)
    if min_soc_score is not None:
        conditions.append("normalized_soc_score >= ?")
        params.append(min_soc_score)

    sql = "SELECT * FROM phones"
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += ";"

    with closing(_connect()) as conn:
        rows = conn.execute(sql, params).fetchall()
        return [_row_to_phone(r) for r in rows]
