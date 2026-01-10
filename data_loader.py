import json
import sys
import os
from app import app
from models import db, Location

def migrate_database():
    try:
        from sqlalchemy import inspect, text
        
        inspector = inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns('locations')]
        
        added_columns = False
        
        if 'discount_min' not in columns:
            print("Добавляю столбец discount_min...")
            with db.engine.begin() as conn:
                conn.execute(text("ALTER TABLE locations ADD COLUMN discount_min FLOAT NULL"))
            print("✓ Столбец discount_min добавлен")
            added_columns = True
        
        if 'discount_max' not in columns:
            print("Добавляю столбец discount_max...")
            with db.engine.begin() as conn:
                conn.execute(text("ALTER TABLE locations ADD COLUMN discount_max FLOAT NULL"))
            print("✓ Столбец discount_max добавлен")
            added_columns = True
        
        if added_columns:
            print("✓ Миграция базы данных завершена\n")
        else:
            print("✓ Столбцы discount_min и discount_max уже существуют\n")
    except Exception as e:
        print(f"⚠ Ошибка при миграции: {e}")
        print("\nДобавьте столбцы вручную через phpMyAdmin (SQL вкладка):\n")
        print("ALTER TABLE locations ADD COLUMN discount_min FLOAT NULL;")
        print("ALTER TABLE locations ADD COLUMN discount_max FLOAT NULL;\n")
        raise

def load_data_from_json(json_file_path):
    try:
        with open(json_file_path, 'r', encoding='cp1251') as f:
            data = json.load(f)
        
        print(f"Найдено записей в файле: {len(data)}")
        
        added_count = 0
        skipped_count = 0
        
        allowed_categories = {
            'Аптека',
            'Магазин',
            'Продовольственные',
            'Предприятия услуг',
            'Общественное питание',
            'Кафе',
            'Столовая',
            'Бытовые услуги',
            'Книги',
            'Одежда',
            'Обувь'
        }

        for item in data:
            name = (item.get('Name') or item.get('CommonName') or '').strip()
            address = (item.get('Address') or item.get('AddressString') or '').strip()
            category = (item.get('Category') or item.get('ObjectCategory') or '').strip()
            
            discount = (item.get('Discount') or item.get('DiscountSize') or 'По социальной карте').strip()
            description = (item.get('Description') or item.get('Note') or '').strip()
            
            discount_min = None
            discount_max = None
            
            min_keys = [
                'Минимальный размер скидки, %',
                'Минимальный размер скидки',
                'MinDiscountSize',
                'MinDiscount',
                'DiscountMin',
                'discount_min',
                'MinimumDiscount'
            ]
            
            max_keys = [
                'Максимальный размер скидки, %',
                'Максимальный размер скидки',
                'MaxDiscountSize',
                'MaxDiscount',
                'DiscountMax',
                'discount_max',
                'MaximumDiscount'
            ]
            
            for key in min_keys:
                if key in item and item[key] is not None:
                    try:
                        value = item[key]
                        if isinstance(value, str):
                            value = value.replace('%', '').replace(',', '.').strip()
                        discount_min = float(value)
                        break
                    except (ValueError, TypeError):
                        continue
            
            for key in max_keys:
                if key in item and item[key] is not None:
                    try:
                        value = item[key]
                        if isinstance(value, str):
                            value = value.replace('%', '').replace(',', '.').strip()
                        discount_max = float(value)
                        break
                    except (ValueError, TypeError):
                        continue

            if not name or not address:
                skipped_count += 1
                continue

            if 'москв' not in address.lower():
                skipped_count += 1
                continue

            if discount_min is None and discount_max is None and not discount:
                skipped_count += 1
                continue

            if allowed_categories:
                if not any(cat.lower() in category.lower() for cat in allowed_categories):
                    skipped_count += 1
                    continue

            existing = Location.query.filter_by(
                name=name,
                address=address
            ).first()
            if existing:
                skipped_count += 1
                continue
            latitude = None
            longitude = None
            if 'geoData' in item and item['geoData']:
                try:
                    geo = item['geoData']
                    if isinstance(geo, dict) and 'coordinates' in geo:
                        longitude = float(geo['coordinates'][0])
                        latitude = float(geo['coordinates'][1])
                except:
                    pass

            if discount_min is not None or discount_max is not None:
                if discount_min is not None and discount_max is not None:
                    if discount_min == discount_max:
                        discount_value = f"{int(discount_min)}%"
                    else:
                        discount_value = f"{int(discount_min)}-{int(discount_max)}%"
                elif discount_min is not None:
                    discount_value = f"{int(discount_min)}%"
                elif discount_max is not None:
                    discount_value = f"{int(discount_max)}%"
            else:
                discount_value = discount 
            
            location = Location(
                name=name,
                address=address,
                category=category,
                discount_value=discount_value,
                discount_min=discount_min,
                discount_max=discount_max,
                latitude=latitude,
                longitude=longitude,
                description=description
            )

            db.session.add(location)
            added_count += 1

            if added_count % 100 == 0:
                db.session.commit()
        
        db.session.commit()
        print(f"✓ Успешно добавлено записей: {added_count}")
        print(f"✓ Пропущено записей (не подошли под фильтр): {skipped_count}")
        
    except Exception as e:
        print(f"Ошибка при загрузке данных: {e}")
        db.session.rollback()

if __name__ == '__main__':
    with app.app_context():
        # Создаем таблицы, если их нет
        db.create_all()
        
        # Выполняем миграцию для добавления новых столбцов
        migrate_database()
        
        json_file = 'data.json'
        if os.path.exists(json_file):
            print(f"Начинаю загрузку из {json_file}...")
            load_data_from_json(json_file)
        else:
            print(f"Файл {json_file} не найден в папке проекта!")