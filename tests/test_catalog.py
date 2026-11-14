import unittest
from dataclasses import FrozenInstanceError

from phone_recommender.catalog import (
    Phone,
    filter_by,
    get_by_slug,
    get_by_slugs,
    load_all,
)


class TestCatalog(unittest.TestCase):
    def test_load_all_and_immutability(self):
        """驗證全量載入筆數、型別轉換（tuple）與深度不可變保護"""
        phones = load_all()
        self.assertEqual(len(phones), 255)

        first = phones[0]
        self.assertIsInstance(first, Phone)
        self.assertIsInstance(first.storage_options_gb, tuple)
        self.assertTrue(all(isinstance(cap, int) for cap in first.storage_options_gb))

        # 驗證 @dataclass(frozen=True) 確實阻擋修改
        with self.assertRaises(FrozenInstanceError):
            first.brand = "FakeBrand"  # type: ignore[misc]

    def test_get_by_slug(self):
        """驗證主鍵單筆查詢與查無資料時的 None 回傳"""
        sample = load_all()[0]

        found = get_by_slug(sample.slug)
        self.assertEqual(found, sample)
        self.assertIsNone(get_by_slug("non-existent-slug-999"))

    def test_get_by_slugs_preserves_order(self):
        """驗證批量查詢會嚴格保留傳入的推薦排名順序"""
        phones = load_all()
        target_slugs = [phones[5].slug, phones[1].slug, phones[10].slug]

        results = get_by_slugs(target_slugs + ["non-existent-slug-999"])
        self.assertEqual([p.slug for p in results], target_slugs)
        self.assertEqual(get_by_slugs([]), [])

    def test_filter_by(self):
        """驗證多條件動態篩選與無條件全量回傳"""
        all_phones = load_all()
        self.assertEqual(len(filter_by()), len(all_phones))

        filtered = filter_by(min_ram_gb=8, min_battery_mah=4500)
        self.assertGreater(len(filtered), 0)
        self.assertTrue(
            all(
                (p.ram_gb is not None and p.ram_gb >= 8)
                and (p.battery_mah is not None and p.battery_mah >= 4500)
                for p in filtered
            )
        )

        sample_brand = all_phones[0].brand
        brand_phones = filter_by(brand=sample_brand)
        self.assertGreater(len(brand_phones), 0)
        self.assertTrue(all(p.brand == sample_brand for p in brand_phones))


if __name__ == "__main__":
    unittest.main()
