"""Seed geo_code_presets table with major Russian cities/regions.

Usage (run from project root):
    python -m services.project_service.seeds.geo_codes

Requires:
    - Docker Compose stack running (for PostgreSQL)
    - Alembic migration 0006 already applied
"""

import asyncio
import json
import sys
from pathlib import Path

# Ensure project root is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from sqlalchemy import select, text
from shared.database.session import AsyncSessionLocal


# Major Russian cities with Yandex geo IDs
# Source: https://yandex.ru/maps (approximate Yandex region codes)
CITIES = [
    # Moscow & Moscow Oblast
    {"name": "Москва", "city_name": "Москва", "region_name": "Московская область", "yandex_geo_id": 214, "aliases": "moscow,mowsksv,москва,mow"},
    {"name": "Подмосковье (Север)", "city_name": "Мытищи", "region_name": "Московская область", "yandex_geo_id": 18021, "aliases": "mytishchi,мытищи"},
    {"name": "Подмосковье (Юг)", "city_name": "Ногинск", "region_name": "Московская область", "yandex_geo_id": 17951, "aliases": "noginsk,ногинск,балашиха,balakhsiha"},
    {"name": "Подмосковье (Запад)", "city_name": "Красногорск", "region_name": "Московская область", "yandex_geo_id": 17893, "aliases": "krasnogorsk,красногорск"},
    {"name": "Подмосковье (Восток)", "city_name": "Балашиха", "region_name": "Московская область", "yandex_geo_id": 17752, "aliases": "balashikha,балашиха"},

    # St. Petersburg
    {"name": "Санкт-Петербург", "city_name": "Санкт-Петербург", "region_name": "Санкт-Петербург", "yandex_geo_id": 58, "aliases": "spb,sankt-peterburg,petersburg,питер,列宁格勒"},

    # Novosibirsk Oblast
    {"name": "Новосибирск", "city_name": "Новосибирск", "region_name": "Новосибирская область", "yandex_geo_id": 1047, "aliases": "novosibirsk,новосибирск,nsk"},

    # Yekaterinburg
    {"name": "Екатеринбург", "city_name": "Екатеринбург", "region_name": "Свердловская область", "yandex_geo_id": 187, "aliases": "ekaterinburg,yekaterinburg,екатеринбург,sverdlovsk"},

    # Kazan
    {"name": "Казань", "city_name": "Казань", "region_name": "Республика Татарстан", "yandex_geo_id": 297, "aliases": "kazan,казань,tatarstan"},

    # Nizhny Novgorod
    {"name": "Нижний Новгород", "city_name": "Нижний Новгород", "region_name": "Нижегородская область", "yandex_geo_id": 196, "aliases": "nizhny,nizhny_novgorod,нижний,nnovgorod"},

    # Chelyabinsk
    {"name": "Челябинск", "city_name": "Челябинск", "region_name": "Челябинская область", "yandex_geo_id": 137, "aliases": "chelyabinsk,челябинск"},

    # Samara
    {"name": "Самара", "city_name": "Самара", "region_name": "Самарская область", "yandex_geo_id": 652, "aliases": "samara,самара,kuybyshev"},

    # Omsk
    {"name": "Омск", "city_name": "Омск", "region_name": "Омская область", "yandex_geo_id": 1983, "aliases": "omsk,омск"},

    # Rostov-on-Don
    {"name": "Ростов-на-Дону", "city_name": "Ростов-на-Дону", "region_name": "Ростовская область", "yandex_geo_id": 261, "aliases": "rostov,rostov_on_don,ростов"},

    # Ufa
    {"name": "Уфа", "city_name": "Уфа", "region_name": "Республика Башкортостан", "yandex_geo_id": 1877, "aliases": "ufa,уфа,bashkortostan"},

    # Krasnoyarsk
    {"name": "Красноярск", "city_name": "Красноярск", "region_name": "Красноярский край", "yandex_geo_id": 1347, "aliases": "krasnoyarsk,красноярск"},

    # Voronezh
    {"name": "Воронеж", "city_name": "Воронеж", "region_name": "Воронежская область", "yandex_geo_id": 1960, "aliases": "voronezh,воронеж"},

    # Krasnodar
    {"name": "Краснодар", "city_name": "Краснодар", "region_name": "Краснодарский край", "yandex_geo_id": 1375, "aliases": "krasnodar,краснодар,sochi_region"},

    # Siberian Federal District
    {"name": "Томск", "city_name": "Томск", "region_name": "Томская область", "yandex_geo_id": 3323, "aliases": "tomsk,томск"},
    {"name": "Кемерово", "city_name": "Кемерово", "region_name": "Кузбасс (Кемеровская область)", "yandex_geo_id": 1405, "aliases": "kemerovo,kuzbass,кемерово"},
    {"name": "Омск", "city_name": "Омск", "region_name": "Сибирский ФО", "yandex_geo_id": 1983, "aliases": "omsk,siberia,омск"},

    # Volga Federal District
    {"name": "Пермь", "city_name": "Пермь", "region_name": "Пермский край", "yandex_geo_id": 2084, "aliases": "perm,пермь,molotov"},
    {"name": "Волгоград", "city_name": "Волгоград", "region_name": "Волгоградская область", "yandex_geo_id": 1953, "aliases": "volgograd,волгоград,tsaritsyn,pavlovsk"},

    # Far East
    {"name": "Хабаровск", "city_name": "Хабаровск", "region_name": "Хабаровский край", "yandex_geo_id": 6817, "aliases": "khabarovsk,хабаровск"},
    {"name": "Владивосток", "city_name": "Владивосток", "region_name": "Приморский край", "yandex_geo_id": 5969, "aliases": "vladivostok,владивосток"},
    {"name": "Иркутск", "city_name": "Иркутск", "region_name": "Иркутская область", "yandex_geo_id": 4073, "aliases": "irkutsk,иркутск"},

    # Central Federal District extras
    {"name": "Тула", "city_name": "Тула", "region_name": "Тульская область", "yandex_geo_id": 9285, "aliases": "tula,тула"},
    {"name": "Курск", "city_name": "Курск", "region_name": "Курская область", "yandex_geo_id": 10739, "aliases": "kursk,курск"},
    {"name": "Белгород", "city_name": "Белгород", "region_name": "Белгородская область", "yandex_geo_id": 11181, "aliases": "belgorod,белгород"},
    {"name": "Липецк", "city_name": "Липецк", "region_name": "Липецкая область", "yandex_geo_id": 12649, "aliases": "lipetsk,липецк"},

    # Northwestern
    {"name": "Сочи", "city_name": "Сочи", "region_name": "Краснодарский край", "yandex_geo_id": 1375001, "aliases": "sochi,сочи"},
    {"name": "Архангельск", "city_name": "Архангельск", "region_name": "Архангельская область", "yandex_geo_id": 5162, "aliases": "arkhangelsk,архангельск"},
    {"name": "Мурманск", "city_name": "Мурманск", "region_name": "Мурманская область", "yandex_geo_id": 2314, "aliases": "murmansk,мурманск,northwestern"},

    # South
    {"name": "Волгоград", "city_name": "Волгоград", "region_name": "Южный ФО", "yandex_geo_id": 1953, "aliases": "volgograd,south,волгоград"},
    {"name": "Саратов", "city_name": "Саратов", "region_name": "Саратовская область", "yandex_geo_id": 654, "aliases": "saratov,саратов"},

    # Ural
    {"name": "Тюмень", "city_name": "Тюмень", "region_name": "Тюменская область", "yandex_geo_id": 3729, "aliases": "tyumen,тюмень"},
    {"name": "Курган", "city_name": "Курган", "region_name": "Курганская область", "yandex_geo_id": 10739001, "aliases": "kurgan,курган"},
]


async def seed_geo_codes():
    """Insert geo code presets into the database."""
    session = AsyncSessionLocal()
    try:
        # Check if table exists
        result = await session.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'geo_code_presets'
            ) AS exists;
        """))
        table_exists = result.scalar()

        if not table_exists:
            print("ERROR: geo_code_presets table does not exist. Run migrations first.")
            return

        for city in CITIES:
            await session.execute(text("""
                INSERT INTO geo_code_presets (id, name, city_name, region_name, country_code, yandex_geo_id, search_aliases)
                VALUES (:id, :name, :city_name, :region_name, :country_code, :yandex_geo_id, :search_aliases)
                ON CONFLICT (city_name, region_name) DO NOTHING
            """), {
                "id": str(__import__("uuid").uuid4()),
                "name": city["name"],
                "city_name": city["city_name"],
                "region_name": city["region_name"],
                "country_code": "ru",
                "yandex_geo_id": city.get("yandex_geo_id"),
                "search_aliases": city.get("aliases"),
            })

        await session.commit()
        print(f"Seeded {len(CITIES)} geo code presets (duplicates skipped).")
    except Exception as e:
        await session.rollback()
        print(f"Error seeding geo codes: {e}")
    finally:
        await session.close()


if __name__ == "__main__":
    asyncio.run(seed_geo_codes())
