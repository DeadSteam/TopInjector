"""add_geo_code_presets_table

Revision ID: 0006_add_geo_code_presets
Revises: 0005_add_audit_log
Create Date: 2026-10-14 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0006_add_geo_code_presets'
down_revision: str | None = '0005_add_audit_log'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Seed data for geo_code_presets — major Russian cities and regions
_SEED_DATA = [
    # Moscow & major city centers
    ("Москва Цетр", "RU", "Москва", "Москва", True, "москва,muscov,moscow center,msc"),
    ("Санкт-Петербург Центр", "RU", "Ленинградская область", "Санкт-Петербург", True, "спб,saint petersburg,st petersburg,piter,spb"),
    ("Новосибирск", "RU", "Новосибирская область", "Новосибирск", True, "новосибирск,novosibirsk,nsk"),
    ("Екатеринбург", "RU", "Свердловская область", "Екатеринбург", True, "екатеринбург,yekaterinburg,yek"),
    ("Казань", "RU", "Республика Татарстан", "Казань", True, "казань,kazan,kzn"),
    ("Нижний Новгород", "RU", "Нижегородская область", "Нижний Новгород", True, "нижний новгород,nizhny novgorod,novg,nizhnij"),
    ("Челябинск", "RU", "Челябинская область", "Челябинск", True, "челябинск,chelyabinsk,chel"),
    ("Самара", "RU", "Самарская область", "Самара", True, "самара,samara"),
    ("Омск", "RU", "Омская область", "Омск", True, "омск,omsk"),
    ("Ростов-на-Дону", "RU", "Ростовская область", "Ростов-на-Дону", True, "ростов,rostov,on-donu"),
    ("Уфа", "RU", "Республика Башкортостан", "Уфа", True, "уфа,ufa"),
    ("Красноярск", "RU", "Красноярский край", "Красноярск", True, "красноярск,krasnoyarsk,krsk"),
    ("Воронеж", "RU", "Воронежская область", "Воронеж", True, "воронеж,voronezh"),
    ("Пермь", "RU", "Пермский край", "Пермь", True, "пермь,perm"),
    ("Волгоград", "RU", "Волгоградская область", "Волгоград", True, "волгоград,volgograd"),
    ("Краснодар", "RU", "Краснодарский край", "Краснодар", True, "краснодар,krasnodar"),
    ("Саратов", "RU", "Саратовская область", "Саратов", True, "саратов,saratov"),
    ("Тюмень", "RU", "Тюменская область", "Тюмень", True, "тюмень,tumen,tom"),
    ("Тольятти", "RU", "Самарская область", "Тольятти", False, "тольятти,tolyatti"),
    ("Ижевск", "RU", "Удмуртская Республика", "Ижевск", True, "ижжевск,izhevsk"),
    ("Барнаул", "RU", "Алтайский край", "Барнаул", True, "барнаул,barnaul"),
    ("Ульяновск", "RU", "Ульяновская область", "Ульяновск", True, "ульяновск,ulyanovsk"),
    ("Иркутск", "RU", "Иркутская область", "Иркутск", True, "иркутск,irkutsk"),
    ("Владивосток", "RU", "Приморский край", "Владивосток", True, "владивосток,vladivostok"),
    ("Ярославль", "RU", "Ярославская область", "Ярославль", True, "ярославль,yaroslavl"),
    ("Махачкала", "RU", "Республика Дагестан", "Махачкала", True, "махачкала,makhachkala"),
    ("Хабаровск", "RU", "Хабаровский край", "Хабаровск", True, "хабаровск,khabarovsk"),
    ("Оренбург", "RU", "Оренбургская область", "Оренбург", True, "оренбург,orenburg"),
    ("Кемерово", "RU", "Кемеровская область", "Кемерово", True, "кемерово,kemerovo"),
    ("Рязань", "RU", "Рязанская область", "Рязань", True, "рязань,ryazan"),
    ("Астрахань", "RU", "Астраханская область", "Астрахань", True, "астрахань,astrakhan"),
    ("Калининград", "RU", "Калининградская область", "Калининград", True, "калининград,kaliningrad"),
    ("Сочи", "RU", "Краснодарский край", "Сочи", True, "сочи,sochi"),
    ("Мурманск", "RU", "Мурманская область", "Мурманск", True, "мурманск,murmansk"),
    ("Архангельск", "RU", "Архангельская область", "Архангельск", True, "архангельск,arkhangelsk"),
    ("Тула", "RU", "Тульская область", "Тула", True, "тула,tula"),
    ("Курск", "RU", "Курская область", "Курск", True, "курск,kursk"),
    ("Смоланськ", "RU", "Смоленская область", "Смоленск", True, "смоленск,smolensk"),
    ("Владимир", "RU", "Владимирская область", "Владимир", True, "владимир,vladimir"),
    ("Пенза", "RU", "Пензенская область", "Пенза", True, "пенза,penza"),
    ("Киров", "RU", "Кировская область", "Киров", True, "киров,kirov"),
    ("Тверь", "RU", "Тверская область", "Тверь", True, "тверь,tver"),
    ("Белгород", "RU", "Белгородская область", "Белгород", True, "белгород,belgorod"),
    ("Вологда", "RU", "Вологодская область", "Вологда", True, "вологда,vologda"),
    ("Тамбов", "RU", "Тамбовская область", "Тамбов", True, "тамбов,tambov"),
    ("Псков", "RU", "Псковская область", "Псков", True, "псков,pskov"),
    ("Якутск", "RU", "Республика Саха", "Якутск", True, "якутск,yakutsk"),
    ("Петрозаводск", "RU", "Республика Карелия", "Петрозаводск", True, "петрозаводск,petrozavodsk"),
    ("Гродно", "BY", "Гродненская область", "Гродно", True, "гродно,grodno"),
    ("Минск", "BY", "Минская область", "Минск", True, "минск,minsk,minsk.by"),
    ("Брест", "BY", "Брестская область", "Брест", True, "брест,brest"),
    ("Витебск", "BY", "Витебская область", "Витебск", True, "витебск,vitebsk"),
]


def upgrade() -> None:
    op.create_table(
        "geo_code_presets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("yandex_geo_id", sa.JSON(), nullable=True),
        sa.Column("country_code", sa.String(3), nullable=False, server_default="ru"),
        sa.Column("region_name", sa.String(200), nullable=False),
        sa.Column("city_name", sa.String(200), nullable=False),
        sa.Column("is_city_center", sa.JSON(), nullable=True),
        sa.Column("search_aliases", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("city_name", "region_name", name="uq_geo_code_preset_city_region"),
    )

    # Insert seed data
    conn = op.get_bind()
    from datetime import datetime, timezone
    _now = datetime.now(timezone.utc).isoformat()
    for name, country, region, city, is_center, aliases in _SEED_DATA:
        yandex_id = {"type": "region", "id": __import__("hashlib").md5(region.encode()).hexdigest()[:8]}
        conn.execute(
            sa.text("""
                INSERT INTO geo_code_presets
                    (id, name, yandex_geo_id, country_code, region_name, city_name, is_city_center, search_aliases, created_at, updated_at)
                VALUES
                    (:id, :name, :yandex_geo_id, :country_code, :region_name, :city_name, :is_city_center, :search_aliases, :created_at, :updated_at)
                ON CONFLICT (city_name, region_name) DO NOTHING
            """),
            {
                "id": str(__import__("uuid").uuid4()),
                "name": name,
                "yandex_geo_id": __import__("json").dumps(yandex_id),
                "country_code": country,
                "region_name": region,
                "city_name": city,
                "is_city_center": is_center,
                "search_aliases": aliases,
                "created_at": _now,
                "updated_at": _now,
            },
        )


def downgrade() -> None:
    op.drop_table("geo_code_presets")
