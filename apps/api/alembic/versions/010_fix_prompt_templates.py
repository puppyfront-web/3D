"""Fix prompt templates to match skill frameworks.

Replace generic English seed templates with concise Chinese supplementary
instructions that complement (not duplicate) the skill's default prompt.

Revision ID: 010
Revises: 009
"""

ANALYSIS_TEMPLATE = """请额外关注以下维度：
- 企业在3D显示/LED/数字视觉产业链中的角色定位
- 企业数字化和沉浸式体验相关投入
- 品牌视觉基因和传播调性
- 是否有裸眼3D、XR、数字孪生等技术布局

六看各方向分析深度建议：
- 向后看：重点挖掘品牌故事和创始愿景，为创意主题提供灵感
- 向前看：关注企业在新媒体、数字展示方面的战略规划
- 向右看：关注3D显示、LED媒体立面行业趋势
- 向下看：重点分析企业在产业链中的不可替代性"""

GENERATION_TEMPLATE = """策划案生成补充要求：
- 创意主题需结合企业品牌基因和行业特征
- 视觉方向建议需考虑3D展示幕墙的物理特性（观看距离、屏幕比例、环境光）
- 实施建议需区分内容制作阶段和现场实施阶段
- 参考案例优先引用与客户同行业、同场景的成功案例

行业常见场景参考：
- 商业综合体：裸眼3D地标、节日主题、品牌联动
- 品牌发布：产品视觉冲击、品牌叙事、社交媒体传播
- 文旅夜游：沉浸式体验、故事化内容、互动装置
- 展览展示：科技感呈现、数据可视化、空间氛围"""

VISUAL_TEMPLATE = """视觉 Prompt 生成补充要求：
- positive_prompt 需包含画面主体、环境、氛围、光线、材质等关键描述
- 负向 Prompt 需排除低质量、变形、文字等常见问题
- 构图需考虑3D展示幕墙的异形屏比例和最佳观看角度

行业视觉风格参考：
- 科技品牌：深色背景 + 发光线条 + 粒子效果 + 金属质感
- 商业综合体：城市天际线 + 光影流动 + 3D纵深感
- 文旅夜游：自然元素 + 光效 + 沉浸式氛围
- 汽车品牌：产品特写 + 动态模糊 + 科技感环境"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Update the three prompt templates to supplementary instructions."""
    op.execute(
        sa.text(
            """
            UPDATE prompt_templates
            SET name = :name,
                description = :desc,
                template_text = :text,
                variables = :vars,
                is_default = :is_default,
                updated_at = CURRENT_TIMESTAMP
            WHERE category = :category
            """
        ).bindparams(
            sa.bindparam(
                "name",
                value="企业分析补充指令",
            ),
            sa.bindparam(
                "desc",
                value="企业解析 Skill 的补充分析指令，管理员可自定义行业侧重点",
            ),
            sa.bindparam(
                "text",
                value=ANALYSIS_TEMPLATE,
            ),
            sa.bindparam(
                "vars",
                value=["company_name", "industry", "context"],
                type_=postgresql.JSONB,
            ),
            sa.bindparam("is_default", value=True),
            sa.bindparam("category", value="analysis"),
        )
    )

    op.execute(
        sa.text(
            """
            UPDATE prompt_templates
            SET name = :name,
                description = :desc,
                template_text = :text,
                variables = :vars,
                is_default = :is_default,
                updated_at = CURRENT_TIMESTAMP
            WHERE category = :category
            """
        ).bindparams(
            sa.bindparam(
                "name",
                value="策划案补充指令",
            ),
            sa.bindparam(
                "desc",
                value="策划案生成 Skill 的补充指令，管理员可自定义行业偏好和强调重点",
            ),
            sa.bindparam(
                "text",
                value=GENERATION_TEMPLATE,
            ),
            sa.bindparam(
                "vars",
                value=[
                    "project_name",
                    "client_name",
                    "requirements",
                    "case_studies",
                    "company_profile",
                ],
                type_=postgresql.JSONB,
            ),
            sa.bindparam("is_default", value=True),
            sa.bindparam("category", value="generation"),
        )
    )

    op.execute(
        sa.text(
            """
            UPDATE prompt_templates
            SET name = :name,
                description = :desc,
                template_text = :text,
                variables = :vars,
                is_default = :is_default,
                updated_at = CURRENT_TIMESTAMP
            WHERE category = :category
            """
        ).bindparams(
            sa.bindparam(
                "name",
                value="视觉 Prompt 补充指令",
            ),
            sa.bindparam(
                "desc",
                value="视觉 Prompt 生成 Skill 的补充指令，管理员可自定义风格偏好和行业规范",
            ),
            sa.bindparam(
                "text",
                value=VISUAL_TEMPLATE,
            ),
            sa.bindparam(
                "vars",
                value=["project_type", "industry", "style_preferences", "target_audience"],
                type_=postgresql.JSONB,
            ),
            sa.bindparam("is_default", value=True),
            sa.bindparam("category", value="visual"),
        )
    )


def downgrade() -> None:
    """No-op: we don't restore the old generic English templates."""
    pass
