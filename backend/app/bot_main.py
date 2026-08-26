import html
import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)
from sqlalchemy import select
from sqlalchemy import func

from app.character_service import get_character, require_character
from app.db import SessionLocal
from app.game_engine import clear_checkpoint, log_activity, undo_activity
from app.ai_service import parse_activity
from app.gm_service import generate_gm_brief
from app.achievement_service import (
    refresh_achievements,
)
from app.report_service import (
    get_report,
)
from app.models import (
    Achievement,
    AchievementUnlock,
    TimelineEvent,
)
from app.daily_close_service import (
    close_day,
    disc_status,
    is_day_closed,
    reopen_day,
)
from app.streak_service import (
    get_habit_stats,
)
from app.quest_service import (
    get_weekly_operations,
    priority_operations,
)
from app.settings import (
    FOCUS_HABIT_CODE,
    FOCUS_HABIT_LABEL,
    NUTRITION_ENABLED,
    OLLAMA_ENABLED,
    TIMEZONE_NAME,
    WEIGHT_TRACKING_ENABLED,
    character_rank,
)
from app.today_service import (
    get_today_snapshot,
    log_weight,
    set_nutrition_status,
)
from app.models import (
    ActivityTemplate,
    Character,
    Checkpoint,
    Quest,
    Skill,
    WeightLog,
)


TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
ALLOWED_USER_ID = int(os.environ["TELEGRAM_USER_ID"])

dp = Dispatcher()

WAITING_WEIGHT_USERS: set[int] = set()
AI_PENDING: dict[int, dict] = {}


MAIN_KEYBOARD = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="☀️ Today"),
            KeyboardButton(text="➕ Add"),
        ],
        [
            KeyboardButton(text="📜 Quests"),
            KeyboardButton(text="🧍 Character"),
        ],
        [
            KeyboardButton(text="📊 Progress"),
            KeyboardButton(text="🤖 GM"),
        ],
    ],
    resize_keyboard=True,
    is_persistent=True,
)


SKILL_ICONS = {
    "muay_thai": "🥊",
    "russian": "🇷🇺",
    "shooting": "🎯",
    "strength": "🏋️",
    "endurance": "🏃",
    "mobility": "🧘",
    "no_gi_grappling": "🤼",
    "german": "🇩🇪",
    "general_knowledge": "🧠",
    "cooking": "🍳",
    "life_skills": "🛠️",
    "personal_finance": "💰",
    "investing": "📈",
}


def authorized_user(user_id: int | None) -> bool:
    return user_id == ALLOWED_USER_ID


def is_authorized(message: Message) -> bool:
    return (
        message.from_user is not None
        and authorized_user(message.from_user.id)
    )


def habit_icon(state: str) -> str:
    return {
        "DONE": "✅",
        "MISSED": "❌",
        "PAUSED": "⏸️",
        "PENDING": "⏳",
    }.get(state, "•")


def format_rate(value):
    if value is None:
        return "—"

    return f"{value:.0f}%"




def character_menu_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🏆 Achievements",
                    callback_data="char:achievements",
                ),
                InlineKeyboardButton(
                    text="🗂 Timeline",
                    callback_data="char:timeline",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📚 History",
                    callback_data="char:history",
                ),
                InlineKeyboardButton(
                    text="📑 Reports",
                    callback_data="char:reports",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⚙️ Settings",
                    callback_data="char:settings",
                ),
            ],
        ]
    )


def achievements_text(session):
    refresh_achievements(
        session
    )

    total = session.scalar(
        select(
            func.count(
                Achievement.id
            )
        ).where(
            Achievement.active.is_(True)
        )
    ) or 0

    rows = session.execute(
        select(
            AchievementUnlock,
            Achievement,
        )
        .join(
            Achievement,
            Achievement.id
            == AchievementUnlock.achievement_id,
        )
        .order_by(
            AchievementUnlock.unlocked_at.desc()
        )
    ).all()

    icons = {
        "COMMON": "⚪",
        "UNCOMMON": "🟢",
        "RARE": "🔵",
        "EPIC": "🟣",
        "LEGENDARY": "🟡",
    }

    lines = [
        "🏆 <b>ACHIEVEMENT HALL</b>",
        "",
        f"Unlocked: <b>{len(rows)}/{total}</b>",
        "",
        "<b>LATEST UNLOCKS</b>",
    ]

    for _, achievement in rows[:10]:
        lines.append(
            f"{icons.get(achievement.rarity, '◆')} "
            f"<b>{html.escape(achievement.name)}</b>"
            f" · {achievement.rarity.title()}"
        )

    if not rows:
        lines.append(
            "No achievements unlocked."
        )

    return "\n".join(lines)


def timeline_text(session):
    events = session.scalars(
        select(TimelineEvent)
        .order_by(
            TimelineEvent.occurred_at.desc()
        )
        .limit(12)
    ).all()

    lines = [
        "🗂 <b>TIMELINE</b>",
        "",
    ]

    if not events:
        lines.append(
            "No significant events yet."
        )

    for event in events:
        lines.append(
            f"<b>{event.local_date.strftime('%d %b')}</b>"
            f" · {html.escape(event.title)}"
        )

    return "\n".join(lines)


def history_text(session):
    from app.models import Activity, Skill
    from app.today_service import life_timezone

    activities = session.scalars(
        select(Activity)
        .where(
            Activity.deleted_at.is_(None)
        )
        .order_by(
            Activity.occurred_at.desc()
        )
        .limit(12)
    ).all()

    skills = {
        skill.id: skill.name
        for skill in session.scalars(
            select(Skill)
        ).all()
    }

    tz = life_timezone()

    lines = [
        "📚 <b>ACTIVITY HISTORY</b>",
        "",
    ]

    if not activities:
        lines.append(
            "No activities logged."
        )

    for activity in activities:
        local_dt = (
            activity.occurred_at
            .astimezone(tz)
        )

        lines.append(
            f"<b>{local_dt.strftime('%d %b %H:%M')}</b>"
            f" · {html.escape(skills.get(activity.primary_skill_id, 'Unknown'))}"
        )

        lines.append(
            f"   {activity.duration_minutes or 0} min"
            f" · {html.escape(activity.template_code or 'manual')}"
        )

    return "\n".join(lines)


def reports_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📅 Weekly",
                    callback_data="char:report:weekly",
                ),
                InlineKeyboardButton(
                    text="🗓 Monthly",
                    callback_data="char:report:monthly",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Character",
                    callback_data="char:home",
                )
            ],
        ]
    )


def build_today_view(session):
    refresh_achievements(session)
    snapshot = get_today_snapshot(session)
    operations = priority_operations(session=session, limit=3)
    discipline = disc_status(session)
    day_closed = is_day_closed(session, snapshot.local_date)

    focus_stats = None
    if snapshot.focus_code and snapshot.focus_state != "DISABLED":
        try:
            focus_stats = get_habit_stats(session, snapshot.focus_code, snapshot.local_date)
        except Exception:
            focus_stats = None

    nutrition_stats = None
    if NUTRITION_ENABLED:
        for nutrition_code in ("nutrition_target", "nutrition_surplus"):
            try:
                nutrition_stats = get_habit_stats(session, nutrition_code, snapshot.local_date)
                break
            except Exception:
                continue

    lines = [
        "☀️ <b>TODAY</b>",
        "",
        snapshot.local_date.strftime("%d %b %Y"),
        "",
        "<b>PRIORITY OPS</b>",
    ]

    if not operations:
        lines.append("✅ Weekly minimums secured.")
    else:
        for operation in operations:
            remaining = max(0, operation.minimum - operation.current)
            icon = SKILL_ICONS.get(operation.skill_code, "◆")
            lines.append(
                f"{icon} {html.escape(operation.skill_name)} · "
                f"<b>{operation.current}/{operation.minimum}</b> minimum"
            )
            lines.append(
                f"   {remaining} session{'' if remaining == 1 else 's'} remaining"
            )

    lines.extend(["", "<b>HABITS</b>"])

    if snapshot.focus_state != "DISABLED":
        lines.append(
            f"{habit_icon(snapshot.focus_state)} "
            f"🎯 {html.escape(snapshot.focus_name)} · "
            f"<b>{snapshot.focus_minutes}/{snapshot.focus_target} min</b>"
        )
        if focus_stats is not None:
            lines.append(
                f"   🔥 {focus_stats.current_streak}d "
                f"· 7d {format_rate(focus_stats.rate_7)} "
                f"· 30d {format_rate(focus_stats.rate_30)}"
            )

    if NUTRITION_ENABLED:
        lines.append(
            f"{habit_icon(snapshot.nutrition_state)} "
            f"🍽 Nutrition Target · "
            f"<b>{snapshot.nutrition_target_kcal} kcal</b>"
        )
        if nutrition_stats is not None:
            lines.append(
                f"   🔥 {nutrition_stats.current_streak}d "
                f"· 7d {format_rate(nutrition_stats.rate_7)} "
                f"· 30d {format_rate(nutrition_stats.rate_30)}"
            )

    if snapshot.focus_state == "DISABLED" and not NUTRITION_ENABLED:
        lines.append("No daily habits configured.")

    lines.extend([
        "",
        "<b>DISCIPLINE</b>",
        "DISC · <b>UNRANKED</b>" if not discipline["ranked"] else f"DISC · <b>{discipline['score']}</b>",
        f"Calibration: <b>{discipline['closed_days']}/30</b> closed days",
    ])

    if WEIGHT_TRACKING_ENABLED:
        lines.extend(["", "<b>BODY</b>"])
        if snapshot.latest_weight_kg is None:
            lines.append("⚖️ Weight: <i>not logged yet</i>")
        else:
            lines.append(f"⚖️ Latest: <b>{snapshot.latest_weight_kg:.1f} kg</b>")
            if snapshot.latest_weight_date:
                lines.append("Last weigh-in: " + snapshot.latest_weight_date.strftime("%d %b"))
        lines.append("📍 Weigh-in: <b>DUE</b>" if snapshot.weight_due else "📍 Weigh-in: not due yet")

    lines.extend(["", "🔒 <b>DAY CLOSED</b>" if day_closed else "🟢 Day open"])

    buttons = []
    if NUTRITION_ENABLED:
        buttons.append([
            InlineKeyboardButton(text="✅ Nutrition hit", callback_data="today:nutrition:yes"),
            InlineKeyboardButton(text="❌ Missed", callback_data="today:nutrition:no"),
        ])

    utility_row = []
    if WEIGHT_TRACKING_ENABLED:
        utility_row.append(InlineKeyboardButton(text="⚖️ Log weight", callback_data="today:weight"))
    utility_row.append(InlineKeyboardButton(text="🔄 Refresh", callback_data="today:refresh"))
    buttons.append(utility_row)

    if day_closed:
        buttons.append([InlineKeyboardButton(text="🔓 Reopen day", callback_data="today:reopen")])
    else:
        buttons.append([InlineKeyboardButton(text="🔒 Close day", callback_data="today:close_request")])

    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=buttons)

def add_skills_keyboard() -> InlineKeyboardMarkup:
    with SessionLocal() as session:
        rows = session.execute(
            select(Skill.code, Skill.name)
            .join(
                ActivityTemplate,
                ActivityTemplate.skill_id == Skill.id,
            )
            .where(
                Skill.status == "ACTIVE",
                ActivityTemplate.enabled.is_(True),
            )
            .distinct()
            .order_by(Skill.name)
        ).all()

    buttons = []

    for code, name in rows:
        icon = SKILL_ICONS.get(code, "◆")

        buttons.append(
            InlineKeyboardButton(
                text=f"{icon} {name}",
                callback_data=f"skill:{code}",
            )
        )

    keyboard = [
        buttons[i:i + 2]
        for i in range(0, len(buttons), 2)
    ]

    return InlineKeyboardMarkup(
        inline_keyboard=keyboard
    )


def templates_keyboard(skill_code: str) -> InlineKeyboardMarkup:
    with SessionLocal() as session:
        skill = session.scalar(
            select(Skill).where(
                Skill.code == skill_code,
                Skill.status == "ACTIVE",
            )
        )

        if skill is None:
            return InlineKeyboardMarkup(
                inline_keyboard=[]
            )

        templates = session.scalars(
            select(ActivityTemplate)
            .where(
                ActivityTemplate.skill_id == skill.id,
                ActivityTemplate.enabled.is_(True),
            )
            .order_by(
                ActivityTemplate.base_xp,
                ActivityTemplate.name,
            )
        ).all()

    keyboard = []

    for template in templates:
        duration = (
            f" · {template.default_duration_minutes}m"
            if template.default_duration_minutes
            else ""
        )

        keyboard.append([
            InlineKeyboardButton(
                text=(
                    f"{template.name}{duration} "
                    f"· +{template.base_xp} XP"
                ),
                callback_data=f"tpl:{template.code}",
            )
        ])

    keyboard.append([
        InlineKeyboardButton(
            text="← Skills",
            callback_data="add:skills",
        )
    ])

    return InlineKeyboardMarkup(
        inline_keyboard=keyboard
    )


@dp.message(CommandStart())
async def start(message: Message):
    if not is_authorized(message):
        return

    with SessionLocal() as session:
        character = require_character(session)

    await message.answer(
        "LIFE RPG // ONLINE\n\n"
        f"🧍 <b>{character.name}</b>\n"
        f"LVL {character.character_level} · "
        f"{character_rank(character.character_level)}\n"
        f"Title: {character.current_title}\n"
        f"CXP: {character.character_xp}",
        reply_markup=MAIN_KEYBOARD,
    )


@dp.message(Command("character"))
@dp.message(F.text == "🧍 Character")
async def character_view(message: Message):
    if not is_authorized(message):
        return

    from app.models import Character

    with SessionLocal() as session:
        character = session.scalar(
            select(Character).limit(1)
        )

        if character is None:
            await message.answer(
                "Character not found."
            )
            return

        discipline = disc_status(
            session
        )

        lines = [
            "🧍 <b>CHARACTER</b>",
            "",
            f"<b>{html.escape(character.name)}</b>",
            (
                f"LVL <b>{character.character_level}</b>"
                f" · {character_rank(character.character_level)}"
            ),
            (
                f"Title · "
                f"<b>{html.escape(character.current_title or '—')}</b>"
            ),
            (
                f"CXP · "
                f"<b>{character.character_xp}</b>"
            ),
            "",
            (
                "DISC · <b>UNRANKED</b>"
                if not discipline["ranked"]
                else
                f"DISC · <b>{discipline['score']}</b>"
            ),
        ]

    await message.answer(
        "\n".join(lines),
        reply_markup=character_menu_keyboard(),
    )

@dp.message(Command("progress"))
@dp.message(F.text == "📊 Progress")
async def progress_view(message: Message):
    if not is_authorized(message):
        return

    with SessionLocal() as session:
        skills = session.scalars(
            select(Skill)
            .where(
                Skill.status == "ACTIVE",
                Skill.priority.in_(
                    ["MAIN", "SIDE"]
                ),
            )
            .order_by(
                Skill.current_level.desc()
            )
        ).all()

    lines = [
        "📊 <b>PROGRESS</b>",
        "",
    ]

    for skill in skills:
        lines.append(
            f"{skill.name}: "
            f"<b>LVL {skill.current_level}</b>"
        )

    await message.answer("\n".join(lines))


@dp.message(Command("add"))
@dp.message(F.text == "➕ Add")
async def add_view(message: Message):
    if not is_authorized(message):
        return

    await message.answer(
        "➕ <b>ADD ACTIVITY</b>\n\n"
        "Select skill:",
        reply_markup=add_skills_keyboard(),
    )


@dp.callback_query(F.data == "add:skills")
async def add_skills_callback(
    callback: CallbackQuery,
):
    if not authorized_user(
        callback.from_user.id
    ):
        return

    await callback.answer()

    if callback.message:
        await callback.message.edit_text(
            "➕ <b>ADD ACTIVITY</b>\n\n"
            "Select skill:",
            reply_markup=add_skills_keyboard(),
        )


@dp.callback_query(F.data.startswith("skill:"))
async def skill_callback(
    callback: CallbackQuery,
):
    if not authorized_user(
        callback.from_user.id
    ):
        return

    skill_code = callback.data.split(
        ":",
        1,
    )[1]

    with SessionLocal() as session:
        skill = session.scalar(
            select(Skill).where(
                Skill.code == skill_code
            )
        )

    if skill is None:
        await callback.answer(
            "Skill not found.",
            show_alert=True,
        )
        return

    await callback.answer()

    if callback.message:
        await callback.message.edit_text(
            f"{SKILL_ICONS.get(skill_code, '◆')} "
            f"<b>{skill.name}</b>\n\n"
            f"Current level: <b>{skill.current_level}</b>\n"
            "Select activity:",
            reply_markup=templates_keyboard(
                skill_code
            ),
        )


@dp.callback_query(F.data.startswith("tpl:"))
async def template_callback(
    callback: CallbackQuery,
):
    if not authorized_user(
        callback.from_user.id
    ):
        return

    template_code = callback.data.split(
        ":",
        1,
    )[1]

    await callback.answer(
        "Logging activity..."
    )

    with SessionLocal() as session:
        try:
            result = log_activity(
                session=session,
                template_code=template_code,
                source="TELEGRAM",
            )

            session.commit()

            skill = session.scalar(
                select(Skill).where(
                    Skill.name == result.skill
                )
            )

            character = require_character(session)

            checkpoint = None

            if result.checkpoint_locked:
                checkpoint = session.scalar(
                    select(Checkpoint).where(
                        Checkpoint.skill_id
                        == skill.id,
                        Checkpoint.level
                        == result.checkpoint_level,
                    )
                )

        except Exception:
            session.rollback()
            logging.exception(
                "Activity logging failed"
            )

            if callback.message:
                await callback.message.answer(
                    "❌ Activity logging failed."
                )

            return

    lines = [
        "✅ <b>ACTIVITY LOGGED</b>",
        "",
        f"{result.skill}",
        f"{result.template}",
        "",
        f"XP: <b>+{result.base_xp}</b>",
    ]

    if result.banked_xp > 0:
        lines.append(
            f"Applied: +{result.applied_xp}"
        )
        lines.append(
            f"Banked: +{result.banked_xp}"
        )

    if result.new_level > result.old_level:
        lines.extend([
            "",
            f"⬆️ <b>LEVEL UP</b>",
            f"LVL {result.old_level} "
            f"→ LVL {result.new_level}",
        ])

    if result.checkpoint_locked:
        lines.extend([
            "",
            "🔒 <b>CHECKPOINT REACHED</b>",
            f"LVL {result.checkpoint_level}",
            result.checkpoint_name or "",
            "",
            "Progress is now banked until "
            "you validate this checkpoint.",
        ])

    lines.extend([
        "",
        f"Current Skill LVL: "
        f"<b>{skill.current_level}</b>",
        f"Character CXP: "
        f"<b>{character.character_xp}</b>",
    ])

    if callback.message:
        buttons = []

        if result.checkpoint_locked:
            buttons.append([
                InlineKeyboardButton(
                    text="✅ Cleared",
                    callback_data=(
                        f"checkpoint_clear:"
                        f"{skill.code}:"
                        f"{result.checkpoint_level}"
                    ),
                ),
                InlineKeyboardButton(
                    text="⏳ Not Yet",
                    callback_data=(
                        f"checkpoint_wait:"
                        f"{skill.code}:"
                        f"{result.checkpoint_level}"
                    ),
                ),
            ])

        buttons.append([
            InlineKeyboardButton(
                text="↩️ Undo",
                callback_data=f"undo:{result.activity_id}",
            )
        ])

        await callback.message.edit_text(
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=buttons
            ),
        )




@dp.callback_query(F.data.startswith("undo:"))
async def undo_callback(
    callback: CallbackQuery,
):
    if not authorized_user(
        callback.from_user.id
    ):
        return

    try:
        activity_id = int(
            callback.data.split(":", 1)[1]
        )
    except (ValueError, IndexError):
        await callback.answer(
            "Invalid activity.",
            show_alert=True,
        )
        return

    with SessionLocal() as session:
        try:
            result = undo_activity(
                session=session,
                activity_id=activity_id,
            )

            session.commit()

            skill = session.scalar(
                select(Skill).where(
                    Skill.name == result.skill
                )
            )

            character = require_character(session)

        except ValueError as exc:
            session.rollback()

            await callback.answer(
                str(exc),
                show_alert=True,
            )
            return

        except Exception:
            session.rollback()

            logging.exception(
                "Activity undo failed"
            )

            await callback.answer(
                "Undo failed.",
                show_alert=True,
            )
            return

    await callback.answer(
        "Activity undone"
    )

    lines = [
        "↩️ <b>ACTIVITY UNDONE</b>",
        "",
        f"{result.skill}",
        "",
        f"Removed visible XP: "
        f"<b>{result.removed_visible_xp}</b>",
    ]

    if result.removed_banked_xp:
        lines.append(
            f"Removed banked XP: "
            f"<b>{result.removed_banked_xp}</b>"
        )

    if result.removed_character_xp:
        lines.append(
            f"Removed CXP: "
            f"<b>{result.removed_character_xp}</b>"
        )

    lines.extend([
        "",
        f"Skill LVL: "
        f"<b>{skill.current_level}</b>",
        f"Skill XP: "
        f"<b>{skill.total_xp}</b>",
        f"Character CXP: "
        f"<b>{character.character_xp}</b>",
    ])

    if callback.message:
        await callback.message.edit_text(
            "\n".join(lines)
        )



@dp.callback_query(F.data.startswith("checkpoint_clear:"))
async def checkpoint_clear_callback(
    callback: CallbackQuery,
):
    if not authorized_user(callback.from_user.id):
        return

    try:
        _, skill_code, level_raw = callback.data.split(":")
        level = int(level_raw)
    except (ValueError, AttributeError):
        await callback.answer(
            "Invalid checkpoint.",
            show_alert=True,
        )
        return

    with SessionLocal() as session:
        try:
            result = clear_checkpoint(
                session=session,
                skill_code=skill_code,
                checkpoint_level=level,
                user_note="Cleared via Telegram",
            )

            session.commit()

            skill = session.scalar(
                select(Skill).where(
                    Skill.code == skill_code
                )
            )

            character = require_character(session)

        except ValueError as exc:
            session.rollback()

            await callback.answer(
                str(exc),
                show_alert=True,
            )
            return

        except Exception:
            session.rollback()
            logging.exception(
                "Checkpoint clear failed"
            )

            await callback.answer(
                "Checkpoint validation failed.",
                show_alert=True,
            )
            return

    await callback.answer("Checkpoint cleared")

    lines = [
        "✅ <b>CHECKPOINT CLEARED</b>",
        "",
        f"{result.skill}",
        f"LVL {result.checkpoint_level} · "
        f"{result.checkpoint_name}",
        "",
        f"Released XP: "
        f"<b>+{result.released_xp}</b>",
    ]

    if result.new_level > result.old_level:
        lines.extend([
            "",
            "⬆️ <b>LEVEL UP</b>",
            f"LVL {result.old_level} "
            f"→ LVL {result.new_level}",
        ])

    if result.remaining_banked_xp:
        lines.append(
            f"Remaining banked XP: "
            f"<b>{result.remaining_banked_xp}</b>"
        )

    if result.next_checkpoint_reached:
        lines.extend([
            "",
            "🔒 <b>NEXT CHECKPOINT REACHED</b>",
            f"LVL {result.next_checkpoint_level}",
            result.next_checkpoint_name or "",
        ])

    lines.extend([
        "",
        f"Current Skill LVL: "
        f"<b>{skill.current_level}</b>",
        f"Character CXP: "
        f"<b>{character.character_xp}</b>",
    ])

    keyboard = None

    if result.next_checkpoint_reached:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(
                    text="✅ Cleared",
                    callback_data=(
                        f"checkpoint_clear:"
                        f"{skill_code}:"
                        f"{result.next_checkpoint_level}"
                    ),
                ),
                InlineKeyboardButton(
                    text="⏳ Not Yet",
                    callback_data=(
                        f"checkpoint_wait:"
                        f"{skill_code}:"
                        f"{result.next_checkpoint_level}"
                    ),
                ),
            ]]
        )

    if callback.message:
        await callback.message.edit_text(
            "\n".join(lines),
            reply_markup=keyboard,
        )


@dp.callback_query(F.data.startswith("checkpoint_wait:"))
async def checkpoint_wait_callback(
    callback: CallbackQuery,
):
    if not authorized_user(callback.from_user.id):
        return

    await callback.answer(
        "Checkpoint remains locked."
    )

    if callback.message:
        await callback.message.edit_reply_markup(
            reply_markup=None
        )


@dp.message(Command("today"))
@dp.message(F.text == "☀️ Today")
async def today_view(message: Message):
    if not is_authorized(message):
        return

    WAITING_WEIGHT_USERS.discard(
        message.from_user.id
    )

    with SessionLocal() as session:
        text, keyboard = build_today_view(
            session
        )

        session.commit()

    await message.answer(
        text,
        reply_markup=keyboard,
    )


@dp.callback_query(
    F.data == "today:refresh"
)
async def today_refresh_callback(
    callback: CallbackQuery,
):
    if not authorized_user(
        callback.from_user.id
    ):
        return

    with SessionLocal() as session:
        text, keyboard = build_today_view(
            session
        )

        session.commit()

    await callback.answer(
        "Refreshed"
    )

    if callback.message:
        await callback.message.edit_text(
            text,
            reply_markup=keyboard,
        )


@dp.callback_query(
    F.data.startswith(
        "today:nutrition:"
    )
)
async def nutrition_callback(
    callback: CallbackQuery,
):
    if not authorized_user(
        callback.from_user.id
    ):
        return

    reached = (
        callback.data
        == "today:nutrition:yes"
    )

    with SessionLocal() as session:
        set_nutrition_status(
            session=session,
            reached=reached,
        )

        session.commit()

        text, keyboard = build_today_view(
            session
        )

        session.commit()

    await callback.answer(
        "Nutrition updated"
    )

    if callback.message:
        await callback.message.edit_text(
            text,
            reply_markup=keyboard,
        )




@dp.callback_query(
    F.data == "today:close_request"
)
async def today_close_request_callback(
    callback: CallbackQuery,
):
    if not authorized_user(
        callback.from_user.id
    ):
        return

    await callback.answer()

    if callback.message:
        await callback.message.edit_reply_markup(
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[
                    InlineKeyboardButton(
                        text="✅ Confirm close",
                        callback_data="today:close_confirm",
                    ),
                    InlineKeyboardButton(
                        text="Cancel",
                        callback_data="today:refresh",
                    ),
                ]]
            )
        )


@dp.callback_query(
    F.data == "today:close_confirm"
)
async def today_close_confirm_callback(
    callback: CallbackQuery,
):
    if not authorized_user(
        callback.from_user.id
    ):
        return

    with SessionLocal() as session:
        close_day(
            session=session,
            manual=True,
        )

        session.commit()

        text, keyboard = build_today_view(
            session
        )

        session.commit()

    await callback.answer(
        "Day closed"
    )

    if callback.message:
        await callback.message.edit_text(
            text,
            reply_markup=keyboard,
        )


@dp.callback_query(
    F.data == "today:reopen"
)
async def today_reopen_callback(
    callback: CallbackQuery,
):
    if not authorized_user(
        callback.from_user.id
    ):
        return

    with SessionLocal() as session:
        try:
            reopen_day(
                session=session
            )

            session.commit()

            text, keyboard = build_today_view(
                session
            )

            session.commit()

        except ValueError as exc:
            session.rollback()

            await callback.answer(
                str(exc),
                show_alert=True,
            )
            return

    await callback.answer(
        "Day reopened"
    )

    if callback.message:
        await callback.message.edit_text(
            text,
            reply_markup=keyboard,
        )


@dp.callback_query(
    F.data == "today:weight"
)
async def weight_start_callback(
    callback: CallbackQuery,
):
    if not authorized_user(
        callback.from_user.id
    ):
        return

    WAITING_WEIGHT_USERS.add(
        callback.from_user.id
    )

    await callback.answer()

    if callback.message:
        await callback.message.answer(
            "⚖️ <b>LOG WEIGHT</b>\n\n"
            "Send your weight in kg.\n"
            "Example: <code>69.2</code>\n\n"
            "Send <code>cancel</code> to cancel."
        )


@dp.message(Command("quests"))
@dp.message(F.text == "📜 Quests")
async def quests_view(message: Message):
    if not is_authorized(message):
        return

    with SessionLocal() as session:
        quests = session.scalars(
            select(Quest)
            .where(Quest.status == "ACTIVE", Quest.quest_type == "MAIN")
            .order_by(Quest.id)
        ).all()
        skills = {skill.id: skill for skill in session.scalars(select(Skill)).all()}
        latest_weight = session.scalar(
            select(WeightLog)
            .where(WeightLog.valid.is_(True))
            .order_by(WeightLog.measured_at.desc())
            .limit(1)
        )
        weekly_ops = get_weekly_operations(session)

        lines = ["📜 <b>MAIN QUESTS</b>", ""]

        if not quests:
            lines.append("No active main quests.")
            lines.append("")

        for quest in quests:
            skill = skills.get(quest.skill_id) if quest.skill_id else None
            icon = SKILL_ICONS.get(skill.code, "◆") if skill else "◆"
            lines.append(f"{icon} <b>{html.escape(quest.title)}</b>")

            if skill is not None:
                if quest.target_unit == "SKILL_LEVEL" and quest.target_value is not None:
                    lines.append(
                        f"{html.escape(skill.name)} · LVL <b>{skill.current_level}</b> "
                        f"→ LVL <b>{int(quest.target_value)}</b>"
                    )
                else:
                    lines.append(f"{html.escape(skill.name)} · LVL <b>{skill.current_level}</b>")

                cp = session.scalar(
                    select(Checkpoint)
                    .where(
                        Checkpoint.skill_id == skill.id,
                        Checkpoint.status != "CLEARED",
                        Checkpoint.level > skill.current_level,
                    )
                    .order_by(Checkpoint.level)
                    .limit(1)
                )
                if cp:
                    lines.append(f"Next: LVL {cp.level} · {html.escape(cp.name)}")

            elif quest.target_unit == "WEIGHT_G" and quest.target_value is not None:
                if latest_weight:
                    lines.append(f"Current: <b>{latest_weight.weight_g / 1000:.1f} kg</b>")
                else:
                    lines.append("Current: <i>not logged yet</i>")
                lines.append(f"Target: <b>{quest.target_value / 1000:.1f} kg</b>")

            elif quest.description:
                lines.append(html.escape(quest.description))

            lines.append("")

        lines.extend(["<b>WEEKLY OPERATIONS</b>", ""])
        if weekly_ops:
            first = weekly_ops[0]
            lines.append(
                f"Cycle: {first.week_start.strftime('%d %b')} → "
                f"{first.week_end.strftime('%d %b')}"
            )
            lines.append("")
        else:
            lines.append("No weekly operations configured.")

        for operation in weekly_ops:
            icon = SKILL_ICONS.get(operation.skill_code, "◆")
            status = "🏆" if operation.stretch_met else ("✅" if operation.minimum_met else "⏳")
            lines.append(f"{status} {icon} <b>{html.escape(operation.skill_name)}</b>")
            lines.append(
                f"{operation.current}/{operation.minimum} minimum · stretch {operation.stretch}"
            )
            lines.append("")

    await message.answer("\n".join(lines).rstrip())


@dp.message(F.text == "🤖 GM")
async def gm_view(message: Message):
    if not is_authorized(message):
        return

    status = await message.answer(
        "🤖 <b>GAME MASTER</b>\n\n"
        "Analyzing current operation state..."
    )

    def run_gm():
        with SessionLocal() as session:
            return generate_gm_brief(
                session
            )

    try:
        result = await asyncio.to_thread(
            run_gm
        )

    except Exception:
        logging.exception(
            "GM generation failed"
        )

        await status.edit_text(
            "🤖 <b>GAME MASTER</b>\n\n"
            "GM analysis unavailable."
        )
        return

    await status.edit_text(
        result["text"]
    )




@dp.message(Command("achievements"))
async def achievements_view(
    message: Message,
):
    if not is_authorized(message):
        return

    with SessionLocal() as session:
        newly_unlocked = refresh_achievements(
            session
        )

        session.commit()

        total = session.scalar(
            select(
                func.count(
                    Achievement.id
                )
            ).where(
                Achievement.active.is_(True)
            )
        ) or 0

        rows = session.execute(
            select(
                AchievementUnlock,
                Achievement,
            )
            .join(
                Achievement,
                Achievement.id
                == AchievementUnlock.achievement_id,
            )
            .order_by(
                AchievementUnlock.unlocked_at.desc()
            )
        ).all()

        lines = [
            "🏆 <b>ACHIEVEMENT HALL</b>",
            "",
            f"Unlocked: <b>{len(rows)}/{total}</b>",
        ]

        if newly_unlocked:
            lines.extend([
                "",
                (
                    "✨ Newly unlocked: "
                    f"<b>{len(newly_unlocked)}</b>"
                ),
            ])

        lines.extend([
            "",
            "<b>LATEST UNLOCKS</b>",
        ])

        rarity_icons = {
            "COMMON": "⚪",
            "UNCOMMON": "🟢",
            "RARE": "🔵",
            "EPIC": "🟣",
            "LEGENDARY": "🟡",
        }

        if not rows:
            lines.append(
                "No achievements unlocked."
            )

        for unlock, achievement in rows[:12]:
            icon = rarity_icons.get(
                achievement.rarity,
                "◆",
            )

            lines.append(
                f"{icon} "
                f"<b>{html.escape(achievement.name)}</b>"
            )

            lines.append(
                "   "
                + achievement.rarity.title()
            )

    await message.answer(
        "\n".join(lines)
    )


@dp.message(Command("timeline"))
async def timeline_view(
    message: Message,
):
    if not is_authorized(message):
        return

    with SessionLocal() as session:
        events = session.scalars(
            select(TimelineEvent)
            .order_by(
                TimelineEvent.occurred_at.desc()
            )
            .limit(15)
        ).all()

        lines = [
            "🗂 <b>TIMELINE</b>",
            "",
        ]

        if not events:
            lines.append(
                "No significant events yet."
            )

        for event in events:
            lines.append(
                f"<b>{event.local_date.strftime('%d %b')}</b>"
                f" · {html.escape(event.title)}"
            )

            if event.description:
                lines.append(
                    "   "
                    + html.escape(
                        event.description
                    )
                )

    await message.answer(
        "\n".join(lines)
    )


@dp.message(Command("history"))
async def history_view(
    message: Message,
):
    if not is_authorized(message):
        return

    from app.today_service import life_timezone
    from app.models import Activity, Skill

    with SessionLocal() as session:
        activities = session.scalars(
            select(Activity)
            .where(
                Activity.deleted_at.is_(None)
            )
            .order_by(
                Activity.occurred_at.desc()
            )
            .limit(15)
        ).all()

        skills = {
            skill.id: skill
            for skill in session.scalars(
                select(Skill)
            ).all()
        }

        tz = life_timezone()

        lines = [
            "📚 <b>ACTIVITY HISTORY</b>",
            "",
        ]

        if not activities:
            lines.append(
                "No activities logged."
            )

        for activity in activities:
            skill = skills.get(
                activity.primary_skill_id
            )

            skill_name = (
                skill.name
                if skill
                else "Unknown"
            )

            local_dt = (
                activity.occurred_at
                .astimezone(tz)
            )

            lines.append(
                f"<b>{local_dt.strftime('%d %b %H:%M')}</b>"
                f" · {html.escape(skill_name)}"
            )

            lines.append(
                f"   {activity.duration_minutes or 0} min"
                f" · {html.escape(activity.template_code or 'manual')}"
            )

    await message.answer(
        "\n".join(lines)
    )


@dp.message(Command("report"))
async def report_view(
    message: Message,
):
    if not is_authorized(message):
        return

    parts = (
        message.text or ""
    ).split()

    report_type = (
        parts[1].upper()
        if len(parts) >= 2
        else "WEEKLY"
    )

    refresh = (
        len(parts) >= 3
        and parts[2].lower()
        == "refresh"
    )

    if report_type not in (
        "WEEKLY",
        "MONTHLY",
    ):
        await message.answer(
            "Usage:\n"
            "<code>/report weekly</code>\n"
            "<code>/report monthly</code>\n"
            "<code>/report weekly refresh</code>"
        )
        return

    with SessionLocal() as session:
        try:
            report, created = get_report(
                session,
                report_type,
                refresh=refresh,
            )

            session.commit()

        except ValueError as exc:
            session.rollback()

            await message.answer(
                html.escape(
                    str(exc)
                )
            )
            return

    state = (
        "Generated"
        if created
        else "Frozen"
    )

    await message.answer(
        (
            f"📑 <b>{report.report_type} REPORT</b>\n"
            f"Version <b>{report.version}</b>"
            f" · {state}\n\n"
            f"<pre>{html.escape(report.content_text)}</pre>"
        )
    )



@dp.callback_query(
    F.data == "char:home"
)
async def char_home_callback(
    callback: CallbackQuery,
):
    if not authorized_user(
        callback.from_user.id
    ):
        return

    from app.models import Character

    with SessionLocal() as session:
        character = session.scalar(
            select(Character).limit(1)
        )

        discipline = disc_status(
            session
        )

        text = (
            "🧍 <b>CHARACTER</b>\n\n"
            f"<b>{html.escape(character.name)}</b>\n"
            f"LVL <b>{character.character_level}</b>"
            f" · {character_rank(character.character_level)}\n"
            f"Title · <b>{html.escape(character.current_title or '—')}</b>\n"
            f"CXP · <b>{character.character_xp}</b>\n\n"
            + (
                "DISC · <b>UNRANKED</b>"
                if not discipline["ranked"]
                else f"DISC · <b>{discipline['score']}</b>"
            )
        )

    await callback.answer()

    if callback.message:
        await callback.message.edit_text(
            text,
            reply_markup=character_menu_keyboard(),
        )


@dp.callback_query(
    F.data == "char:achievements"
)
async def char_achievements_callback(
    callback: CallbackQuery,
):
    if not authorized_user(
        callback.from_user.id
    ):
        return

    with SessionLocal() as session:
        text = achievements_text(
            session
        )
        session.commit()

    await callback.answer()

    if callback.message:
        await callback.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[
                    InlineKeyboardButton(
                        text="⬅️ Character",
                        callback_data="char:home",
                    )
                ]]
            ),
        )


@dp.callback_query(
    F.data == "char:timeline"
)
async def char_timeline_callback(
    callback: CallbackQuery,
):
    if not authorized_user(
        callback.from_user.id
    ):
        return

    with SessionLocal() as session:
        text = timeline_text(
            session
        )

    await callback.answer()

    if callback.message:
        await callback.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[
                    InlineKeyboardButton(
                        text="⬅️ Character",
                        callback_data="char:home",
                    )
                ]]
            ),
        )


@dp.callback_query(
    F.data == "char:history"
)
async def char_history_callback(
    callback: CallbackQuery,
):
    if not authorized_user(
        callback.from_user.id
    ):
        return

    with SessionLocal() as session:
        text = history_text(
            session
        )

    await callback.answer()

    if callback.message:
        await callback.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[
                    InlineKeyboardButton(
                        text="⬅️ Character",
                        callback_data="char:home",
                    )
                ]]
            ),
        )


@dp.callback_query(
    F.data == "char:reports"
)
async def char_reports_callback(
    callback: CallbackQuery,
):
    if not authorized_user(
        callback.from_user.id
    ):
        return

    await callback.answer()

    if callback.message:
        await callback.message.edit_text(
            "📑 <b>REPORTS</b>\n\n"
            "Frozen deterministic operational reports.",
            reply_markup=reports_keyboard(),
        )


@dp.callback_query(
    F.data.startswith("char:report:")
)
async def char_report_callback(
    callback: CallbackQuery,
):
    if not authorized_user(
        callback.from_user.id
    ):
        return

    report_type = (
        callback.data
        .split(":")[-1]
        .upper()
    )

    with SessionLocal() as session:
        report, created = get_report(
            session,
            report_type,
        )

        session.commit()

    state = (
        "Generated"
        if created
        else "Frozen"
    )

    text = (
        f"📑 <b>{report.report_type} REPORT</b>\n"
        f"Version <b>{report.version}</b> · {state}\n\n"
        f"<pre>{html.escape(report.content_text)}</pre>"
    )

    await callback.answer()

    if callback.message:
        await callback.message.edit_text(
            text,
            reply_markup=reports_keyboard(),
        )


@dp.callback_query(
    F.data == "char:settings"
)
async def char_settings_callback(
    callback: CallbackQuery,
):
    if not authorized_user(
        callback.from_user.id
    ):
        return

    ai_state = "Enabled · Hybrid Local" if OLLAMA_ENABLED else "Disabled · Deterministic fallback"
    focus_state = FOCUS_HABIT_LABEL if FOCUS_HABIT_CODE else "Disabled"

    text = (
        "⚙️ <b>SETTINGS</b>\n\n"
        f"Timezone · <b>{html.escape(TIMEZONE_NAME)}</b>\n"
        "Interface · <b>Telegram</b>\n"
        "Theme · <b>Night Ops</b>\n"
        f"Local AI · <b>{html.escape(ai_state)}</b>\n"
        f"Daily focus · <b>{html.escape(focus_state)}</b>\n"
        f"Nutrition · <b>{'Enabled' if NUTRITION_ENABLED else 'Disabled'}</b>\n"
        f"Weight tracking · <b>{'Enabled' if WEIGHT_TRACKING_ENABLED else 'Disabled'}</b>\n"
        "DISC · <b>Calibration / v1 placeholder</b>\n\n"
        "Founding settings are installer-managed in v1."
    )

    await callback.answer()

    if callback.message:
        await callback.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[
                    InlineKeyboardButton(
                        text="⬅️ Character",
                        callback_data="char:home",
                    )
                ]]
            ),
        )



@dp.callback_query(
    F.data == "ai:cancel"
)
async def ai_cancel_callback(
    callback: CallbackQuery,
):
    if not authorized_user(
        callback.from_user.id
    ):
        return

    AI_PENDING.pop(
        callback.from_user.id,
        None,
    )

    await callback.answer(
        "Cancelled"
    )

    if callback.message:
        await callback.message.edit_text(
            "❌ Activity cancelled."
        )


@dp.callback_query(
    F.data == "ai:confirm"
)
async def ai_confirm_callback(
    callback: CallbackQuery,
):
    if not authorized_user(
        callback.from_user.id
    ):
        return

    data = AI_PENDING.pop(
        callback.from_user.id,
        None,
    )

    if data is None:
        await callback.answer(
            "Preview expired.",
            show_alert=True,
        )
        return

    try:
        with SessionLocal() as session:
            result = log_activity(
                session=session,
                template_code=data["template_code"],
                duration_minutes=data["duration_minutes"],
                raw_user_input=data["raw_user_input"],
                source="TELEGRAM_AI",
            )

            session.commit()

            skill = session.scalar(
                select(Skill).where(
                    Skill.code
                    == data["skill_code"]
                )
            )

            character = require_character(session)

    except Exception:
        logging.exception(
            "AI confirmed activity logging failed"
        )

        await callback.answer(
            "Logging failed.",
            show_alert=True,
        )
        return

    lines = [
        "✅ <b>ACTIVITY LOGGED</b>",
        "",
        f"{result.skill}",
        f"{result.template}",
        f"Duration: <b>{data['duration_minutes']} min</b>",
        "",
        f"XP: <b>+{result.base_xp}</b>",
    ]

    if result.banked_xp > 0:
        lines.append(
            f"Applied: +{result.applied_xp}"
        )
        lines.append(
            f"Banked: +{result.banked_xp}"
        )

    if result.new_level > result.old_level:
        lines.extend([
            "",
            "⬆️ <b>LEVEL UP</b>",
            f"LVL {result.old_level} "
            f"→ LVL {result.new_level}",
        ])

    if result.checkpoint_locked:
        lines.extend([
            "",
            "🔒 <b>CHECKPOINT REACHED</b>",
            f"LVL {result.checkpoint_level}",
            result.checkpoint_name or "",
            "",
            "Progress is now banked until "
            "you validate this checkpoint.",
        ])

    lines.extend([
        "",
        f"Current Skill LVL: "
        f"<b>{skill.current_level}</b>",
        f"Character CXP: "
        f"<b>{character.character_xp}</b>",
    ])

    buttons = []

    if result.checkpoint_locked:
        buttons.append([
            InlineKeyboardButton(
                text="✅ Cleared",
                callback_data=(
                    f"checkpoint_clear:"
                    f"{skill.code}:"
                    f"{result.checkpoint_level}"
                ),
            ),
            InlineKeyboardButton(
                text="⏳ Not Yet",
                callback_data=(
                    f"checkpoint_wait:"
                    f"{skill.code}:"
                    f"{result.checkpoint_level}"
                ),
            ),
        ])

    buttons.append([
        InlineKeyboardButton(
            text="↩️ Undo",
            callback_data=(
                f"undo:{result.activity_id}"
            ),
        )
    ])

    await callback.answer(
        "Activity logged"
    )

    if callback.message:
        await callback.message.edit_text(
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=buttons
            ),
        )


@dp.message()
async def fallback(message: Message):
    if not is_authorized(message):
        return

    user_id = message.from_user.id

    if user_id in WAITING_WEIGHT_USERS:
        raw = (
            message.text or ""
        ).strip()

        if raw.lower() == "cancel":
            WAITING_WEIGHT_USERS.discard(
                user_id
            )

            await message.answer(
                "Weight logging cancelled.",
                reply_markup=MAIN_KEYBOARD,
            )
            return

        try:
            weight_kg = float(
                raw.replace(",", ".")
            )
        except ValueError:
            await message.answer(
                "Send only the weight in kg, "
                "for example <code>69.2</code>, "
                "or <code>cancel</code>."
            )
            return

        with SessionLocal() as session:
            try:
                entry = log_weight(
                    session=session,
                    weight_kg=weight_kg,
                )

                session.commit()

                text, keyboard = (
                    build_today_view(
                        session
                    )
                )

                session.commit()

            except ValueError as exc:
                session.rollback()

                await message.answer(
                    str(exc)
                )
                return

            except Exception:
                session.rollback()

                logging.exception(
                    "Weight logging failed"
                )

                await message.answer(
                    "Weight logging failed."
                )
                return

        WAITING_WEIGHT_USERS.discard(
            user_id
        )

        await message.answer(
            f"✅ Weight logged: "
            f"<b>{entry.weight_g / 1000:.1f} kg</b>"
        )

        await message.answer(
            text,
            reply_markup=keyboard,
        )

        return

    raw = (message.text or "").strip()

    if not raw or raw.startswith("/"):
        await message.answer(
            "Command not recognized.",
            reply_markup=MAIN_KEYBOARD,
        )
        return

    status = await message.answer(
        "🤖 <b>Interpreting activity...</b>"
    )

    def parse_in_thread():
        with SessionLocal() as session:
            return parse_activity(
                session,
                raw,
            )

    try:
        candidate = await asyncio.to_thread(
            parse_in_thread
        )

    except Exception:
        logging.exception(
            "AI activity parsing failed"
        )

        await status.edit_text(
            "❌ I couldn't interpret that safely. "
            "Use ➕ Add instead."
        )
        return

    AI_PENDING[user_id] = {
        "skill_code": candidate.skill_code,
        "template_code": candidate.template_code,
        "duration_minutes": candidate.duration_minutes,
        "confidence": candidate.confidence,
        "source": candidate.source,
        "raw_user_input": raw,
    }

    with SessionLocal() as session:
        template = session.scalar(
            select(ActivityTemplate).where(
                ActivityTemplate.code
                == candidate.template_code
            )
        )

        skill = session.scalar(
            select(Skill).where(
                Skill.code
                == candidate.skill_code
            )
        )

        base_xp = (
            template.base_xp
            if template
            else 0
        )

        template_name = (
            template.name
            if template
            else candidate.template_code
        )

        skill_name = (
            skill.name
            if skill
            else candidate.skill_code
        )

    preview = (
        "🤖 <b>ACTIVITY PREVIEW</b>\n\n"
        f"Skill · <b>{html.escape(skill_name)}</b>\n"
        f"Activity · <b>{html.escape(template_name)}</b>\n"
        f"Duration · <b>{candidate.duration_minutes} min</b>\n"
        f"Base XP · <b>+{base_xp}</b>\n"
        f"Confidence · <b>{candidate.confidence}</b>\n\n"
        "Nothing has been logged yet."
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text="✅ Confirm",
                callback_data="ai:confirm",
            ),
            InlineKeyboardButton(
                text="❌ Cancel",
                callback_data="ai:cancel",
            ),
        ]]
    )

    await status.edit_text(
        preview,
        reply_markup=keyboard,
    )


async def main():
    logging.basicConfig(level=logging.INFO)

    bot = Bot(
        token=TOKEN,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML,
        ),
    )

    await bot.delete_webhook(
        drop_pending_updates=False
    )

    await dp.start_polling(
        bot,
        tasks_concurrency_limit=4,
    )


if __name__ == "__main__":
    asyncio.run(main())
