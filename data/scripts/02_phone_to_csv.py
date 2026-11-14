import csv
import json
from pathlib import Path

# ===== 設定 =====
ROOT = Path(__file__).resolve().parents[1] / "raw" / "smartphone"
OUTPUT = Path(__file__).resolve().parents[1] / "interim" / "phones.csv"


def flatten(data: dict, parent_key: str = "") -> dict:
    """展開巢狀字典，陣列保留為 JSON 字串。"""
    result = {}

    for key, value in data.items():
        field = f"{parent_key}.{key}" if parent_key else key

        if isinstance(value, dict):
            result.update(flatten(value, field))
        elif isinstance(value, list):
            result[field] = json.dumps(
                value, ensure_ascii=False
            )
        else:
            result[field] = value

    return result


def preprocess():
    if not ROOT.is_dir():
        raise FileNotFoundError(f"找不到資料集：{ROOT}")

    records = []
    fields = dict()

    for json_file in sorted(ROOT.rglob("*.json")):
        with json_file.open("r", encoding="utf-8-sig") as file:
            data = json.load(file)

        if not isinstance(data, dict):
            raise ValueError(f"JSON 格式錯誤：{json_file}")

        record = flatten(data)
        records.append(record)

        for field in record:
            fields.setdefault(field, None)

    if not records:
        print("沒有找到任何手機資料。")
        return

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=list(fields),
            extrasaction="raise"
        )
        writer.writeheader()
        writer.writerows(records)

    print(f"轉換完成：{len(records)} 筆")
    print(f"欄位數量：{len(fields)}")
    print(f"輸出位置：{OUTPUT}")


if __name__ == "__main__":
    preprocess()
