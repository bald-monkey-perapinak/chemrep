"""
Сид-скрипт: заполняет базу демонстрационными данными.
Запуск: python -m src.db.seeds.seed_demo
"""

import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.db.base import Base
from src.models.teacher import Teacher
from src.models.student import Student
from src.models.knowledge import KnowledgeClass, KnowledgeSection, KnowledgeTopic, TopicFile
from src.models.lesson import Lesson, LessonStatus, VCSPlatform
from src.models.homework import Homework, HomeworkDeliveryStatus

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://chemrep:password@localhost:5432/chemrep")
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)


def seed():
    db = Session()
    try:
        # ── Преподаватель ──────────────────────────────────────────────────────
        teacher = Teacher(
            id=uuid.uuid4(),
            email="ivanova@chemrep.ru",
            hashed_password="$2b$12$hashed_placeholder",
            full_name="Иванова Алина Петровна",
            subject="Химия",
            default_vcs_platform="zoom",
        )
        db.add(teacher)
        db.flush()

        # ── Ученики ────────────────────────────────────────────────────────────
        students = [
            Student(teacher_id=teacher.id, full_name="Петров Михаил",    email="petrov@mail.ru",   grade=10),
            Student(teacher_id=teacher.id, full_name="Сидорова Анна",    email="sidorova@mail.ru", grade=10),
            Student(teacher_id=teacher.id, full_name="Козлов Дмитрий",   email="kozlov@mail.ru",   grade=9),
            Student(teacher_id=teacher.id, full_name="Новикова Елена",   email="novikova@mail.ru", grade=11),
            Student(teacher_id=teacher.id, full_name="Морозов Артём",    email="morozov@mail.ru",  grade=8),
        ]
        db.add_all(students)
        db.flush()

        # ── База знаний: 8 класс ──────────────────────────────────────────────
        cls8 = KnowledgeClass(teacher_id=teacher.id, name="8 класс", grade_number=8, sort_order=1)
        db.add(cls8); db.flush()
        sec8_base = KnowledgeSection(class_id=cls8.id, name="Основные понятия", sort_order=1)
        db.add(sec8_base); db.flush()
        topic_atom = KnowledgeTopic(
            section_id=sec8_base.id, name="Атом и молекула",
            keywords="атом молекула вещество элемент",
            estimated_duration_min=40,
            lesson_script=[
                {"step": 1, "text": "Сегодня мы изучим строение атома. Атом — наименьшая частица химического элемента.", "miro_action": "show_frame_1"},
                {"step": 2, "text": "Атом состоит из ядра и электронной оболочки. Ядро содержит протоны и нейтроны.", "miro_action": "show_frame_2"},
                {"step": 3, "text": "Проверочный вопрос: из чего состоит ядро атома?", "miro_action": None},
            ]
        )
        db.add(topic_atom); db.flush()
        db.add(TopicFile(topic_id=topic_atom.id, original_name="Конспект_атом.pdf",    storage_path="s3://chemrep/8klass/atom_konspekt.pdf",   mime_type="application/pdf", size_bytes=1258291, file_role="material"))
        db.add(TopicFile(topic_id=topic_atom.id, original_name="Схема_строения.png",   storage_path="s3://chemrep/8klass/atom_schema.png",      mime_type="image/png",       size_bytes=348160,  file_role="image"))

        # ── База знаний: 9 класс ──────────────────────────────────────────────
        cls9 = KnowledgeClass(teacher_id=teacher.id, name="9 класс", grade_number=9, sort_order=2)
        db.add(cls9); db.flush()
        sec9_reac = KnowledgeSection(class_id=cls9.id, name="Типы реакций", sort_order=1)
        db.add(sec9_reac); db.flush()

        topic_sub = KnowledgeTopic(section_id=sec9_reac.id, name="Реакции замещения",  keywords="замещение металл кислота соль", estimated_duration_min=45)
        topic_exch = KnowledgeTopic(section_id=sec9_reac.id, name="Реакции обмена",    keywords="обмен ионы осадок", estimated_duration_min=45)
        db.add_all([topic_sub, topic_exch]); db.flush()
        db.add(TopicFile(topic_id=topic_sub.id, original_name="Конспект_замещение.pdf", storage_path="s3://chemrep/9klass/zameshenie.pdf", mime_type="application/pdf", size_bytes=911360, file_role="material"))

        # ── База знаний: 10 класс ─────────────────────────────────────────────
        cls10 = KnowledgeClass(teacher_id=teacher.id, name="10 класс", grade_number=10, sort_order=3)
        db.add(cls10); db.flush()
        sec10_org = KnowledgeSection(class_id=cls10.id, name="Органическая химия", sort_order=1)
        db.add(sec10_org); db.flush()

        topic_alk = KnowledgeTopic(
            section_id=sec10_org.id, name="Алканы",
            keywords="алканы углеводороды метан этан пропан гомологи",
            estimated_duration_min=50,
            lesson_script=[
                {"step": 1, "text": "Алканы — предельные углеводороды с общей формулой CₙH₂ₙ₊₂.", "miro_action": "show_formula"},
                {"step": 2, "text": "Простейший алкан — метан CH₄. Рассмотрим его строение.", "miro_action": "draw_methane"},
                {"step": 3, "text": "Гомологический ряд: метан, этан, пропан, бутан...", "miro_action": "show_table"},
                {"step": 4, "text": "Химические свойства: реакции горения и замещения.", "miro_action": "show_reactions"},
            ]
        )
        topic_alkene = KnowledgeTopic(section_id=sec10_org.id, name="Алкены", keywords="алкены этилен двойная связь", estimated_duration_min=50)
        db.add_all([topic_alk, topic_alkene]); db.flush()
        db.add(TopicFile(topic_id=topic_alk.id, original_name="Алканы_конспект.pdf",   storage_path="s3://chemrep/10klass/alkany_konspekt.pdf",  mime_type="application/pdf", size_bytes=1572864, file_role="material"))
        db.add(TopicFile(topic_id=topic_alk.id, original_name="Таблица_свойств.xlsx",  storage_path="s3://chemrep/10klass/alkany_table.xlsx",    mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", size_bytes=225280, file_role="material"))
        db.add(TopicFile(topic_id=topic_alk.id, original_name="Домашнее_задание.pdf",  storage_path="s3://chemrep/10klass/alkany_hw.pdf",        mime_type="application/pdf", size_bytes=512000, file_role="homework"))

        # ── База знаний: 11 класс ─────────────────────────────────────────────
        cls11 = KnowledgeClass(teacher_id=teacher.id, name="11 класс", grade_number=11, sort_order=4)
        db.add(cls11); db.flush()
        sec11_per = KnowledgeSection(class_id=cls11.id, name="Периодический закон", sort_order=1)
        db.add(sec11_per); db.flush()
        topic_per = KnowledgeTopic(section_id=sec11_per.id, name="Периодическая система элементов", keywords="периодический закон менделеев таблица элементы", estimated_duration_min=55)
        db.add(topic_per); db.flush()

        # ── Занятия ────────────────────────────────────────────────────────────
        now = datetime.now(timezone.utc)
        petrov, sidorova, kozlov, novikova, morozov = students

        lessons_data = [
            # Прошедшие
            Lesson(teacher_id=teacher.id, student_id=novikova.id, topic_id=topic_per.id,
                   scheduled_at=now - timedelta(days=4, hours=2), started_at=now - timedelta(days=4, hours=2),
                   finished_at=now - timedelta(days=4, hours=1), vcs_platform=VCSPlatform.ZOOM,
                   vcs_link="https://zoom.us/j/111111", status=LessonStatus.COMPLETED,
                   transcript="Бот: Сегодня изучаем периодический закон...\nУченик: А почему элементы расположены именно так?",
                   homework_sent=True),
            Lesson(teacher_id=teacher.id, student_id=kozlov.id, topic_id=topic_sub.id,
                   scheduled_at=now - timedelta(days=2, hours=3), started_at=now - timedelta(days=2, hours=3),
                   finished_at=now - timedelta(days=2, hours=2), vcs_platform=VCSPlatform.ZOOM,
                   vcs_link="https://zoom.us/j/222222", status=LessonStatus.COMPLETED, homework_sent=True),
            # Сегодня
            Lesson(teacher_id=teacher.id, student_id=petrov.id, topic_id=topic_alk.id,
                   scheduled_at=now.replace(hour=16, minute=0, second=0), vcs_platform=VCSPlatform.ZOOM,
                   vcs_link="https://zoom.us/j/123456", status=LessonStatus.SCHEDULED),
            Lesson(teacher_id=teacher.id, student_id=sidorova.id, topic_id=topic_sub.id,
                   scheduled_at=now.replace(hour=18, minute=30, second=0), vcs_platform=VCSPlatform.YANDEX,
                   vcs_link="https://telemost.yandex.ru/j/abc", status=LessonStatus.SCHEDULED),
            # Будущие
            Lesson(teacher_id=teacher.id, student_id=kozlov.id, topic_id=topic_exch.id,
                   scheduled_at=now + timedelta(days=1, hours=2), vcs_platform=VCSPlatform.ZOOM,
                   vcs_link="https://zoom.us/j/789", status=LessonStatus.SCHEDULED),
            Lesson(teacher_id=teacher.id, student_id=morozov.id, topic_id=topic_atom.id,
                   scheduled_at=now + timedelta(days=2, hours=3), vcs_platform=VCSPlatform.ZOOM,
                   vcs_link="https://zoom.us/j/999", status=LessonStatus.SCHEDULED),
            Lesson(teacher_id=teacher.id, student_id=petrov.id, topic_id=topic_alkene.id,
                   scheduled_at=now + timedelta(days=7, hours=1), vcs_platform=VCSPlatform.ZOOM,
                   vcs_link="https://zoom.us/j/777", status=LessonStatus.SCHEDULED),
        ]
        db.add_all(lessons_data)
        db.flush()

        # ── Домашние задания для завершённых уроков ────────────────────────────
        db.add(Homework(
            lesson_id=lessons_data[0].id,
            title="ДЗ: Периодический закон",
            description="Выучить первые 20 элементов таблицы Менделеева. Составить электронные конфигурации для Na, Cl, O.",
            file_path="s3://chemrep/10klass/alkany_hw.pdf",
            delivery_status=HomeworkDeliveryStatus.SENT,
            delivery_channel="email",
            sent_at=now - timedelta(days=4, hours=1),
        ))
        db.add(Homework(
            lesson_id=lessons_data[1].id,
            title="ДЗ: Реакции замещения",
            description="Решить задачи №12-15 из учебника. Написать уравнения реакций цинка с серной кислотой.",
            delivery_status=HomeworkDeliveryStatus.SENT,
            delivery_channel="email",
            sent_at=now - timedelta(days=2, hours=2),
        ))

        db.commit()
        print("✅ Демо-данные успешно добавлены в базу!")
        print(f"   Преподаватель: {teacher.email}")
        print(f"   Учеников:      {len(students)}")
        print(f"   Тем:           6")
        print(f"   Занятий:       {len(lessons_data)}")

    except Exception as e:
        db.rollback()
        print(f"❌ Ошибка: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
