"""Add Row Level Security policies for tenant isolation

Revision ID: 0010
Revises: 0009
Create Date: 2026-06-14

Note: RLS requires setting the 'current_user' session variable to the teacher_id
before each query. This is done via: SET LOCAL app.current_teacher_id = '<uuid>'
"""
from alembic import op
import sqlalchemy as sa

revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable RLS on all teacher-owned tables
    tables = [
        'students', 'lessons', 'lesson_sessions', 'homeworks',
        'knowledge_classes', 'knowledge_sections', 'knowledge_topics',
        'topic_files', 'topic_assets', 'student_progress',
        'training_videos', 'teaching_profiles', 'parental_consents',
        'content_embeddings',
    ]

    for table in tables:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")

    # Create policies — teacher can only see their own data
    policies = [
        ('students', 'teacher_id'),
        ('lessons', 'teacher_id'),
        ('homeworks', 'teacher_id'),
        ('knowledge_classes', 'teacher_id'),
        ('student_progress', 'student_id'),  # through student -> teacher
        ('training_videos', 'teacher_id'),
        ('teaching_profiles', 'teacher_id'),
        ('parental_consents', 'student_id'),  # through student -> teacher
        ('content_embeddings', 'teacher_id'),
    ]

    for table, column in policies:
        op.execute(f"""
            DROP POLICY IF EXISTS teacher_isolation ON {table};
        """)
        if column == 'teacher_id':
            op.execute(f"""
                CREATE POLICY teacher_isolation ON {table}
                    USING (teacher_id::text = current_setting('app.current_teacher_id', true));
            """)
        elif column == 'student_id':
            op.execute(f"""
                CREATE POLICY teacher_isolation ON {table}
                    USING (student_id IN (
                        SELECT id FROM students
                        WHERE teacher_id::text = current_setting('app.current_teacher_id', true)
                    ));
            """)

    # Allow bot service to bypass RLS (uses service role)
    op.execute("""
        CREATE POLICY bot_bypass ON students FOR ALL USING (true) WITH CHECK (true);
    """)
    op.execute("""
        CREATE POLICY bot_bypass ON lessons FOR ALL USING (true) WITH CHECK (true);
    """)
    op.execute("""
        CREATE POLICY bot_bypass ON lesson_sessions FOR ALL USING (true) WITH CHECK (true);
    """)


def downgrade() -> None:
    tables = [
        'students', 'lessons', 'lesson_sessions', 'homeworks',
        'knowledge_classes', 'knowledge_sections', 'knowledge_topics',
        'topic_files', 'topic_assets', 'student_progress',
        'training_videos', 'teaching_profiles', 'parental_consents',
        'content_embeddings',
    ]

    for table in tables:
        op.execute(f"DROP POLICY IF EXISTS teacher_isolation ON {table}")
        op.execute(f"DROP POLICY IF EXISTS bot_bypass ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
