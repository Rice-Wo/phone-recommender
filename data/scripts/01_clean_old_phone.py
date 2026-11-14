import shutil
from pathlib import Path

# ===== 設定 =====
MIN_YEAR = 2023
DELETE = True  # False：預覽，True：實際刪除

ROOT = Path(__file__).resolve().parents[1] / "raw" / "smartphone"


def preprocess():
    if not ROOT.is_dir():
        raise FileNotFoundError(f"找不到資料集：{ROOT}")

    for brand_dir in ROOT.iterdir():
        if not brand_dir.is_dir():
            continue

        year_dirs = [
            path for path in brand_dir.iterdir()
            if path.is_dir() and path.name.isdigit()
        ]

        for year_dir in year_dirs:
            if int(year_dir.name) < MIN_YEAR:
                print(f"{'刪除' if DELETE else '預計刪除'}：{year_dir}")

                if DELETE:
                    shutil.rmtree(year_dir)

        remaining = [
            path for path in brand_dir.iterdir()
            if path.is_dir() and path.name.isdigit()
        ]

        if not remaining:
            print(f"{'刪除' if DELETE else '預計刪除'}品牌：{brand_dir}")

            if DELETE:
                shutil.rmtree(brand_dir)


if __name__ == "__main__":
    preprocess()
