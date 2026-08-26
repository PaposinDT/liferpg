import asyncio
import logging
import os

from datetime import (
    date,
    datetime,
    time,
    timedelta,
    timezone,
)
from zoneinfo import ZoneInfo

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from sqlalchemy import select

from app.db import SessionLocal

from app.daily_close_service import (
    close_day,
    is_day_closed,
)

from app.models import (
    DailySnapshot,
    JobRun,
    ScheduledJob,
)

from app.today_service import (
    get_today_snapshot,
)


TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
USER_ID = int(
    os.environ["TELEGRAM_USER_ID"]
)

DEFAULT_TIMEZONE = os.getenv(
    "LIFERPG_TIMEZONE",
    "UTC",
)

POLL_SECONDS = 30

logging.basicConfig(
    level=logging.INFO
)

log = logging.getLogger(
    "liferpg.scheduler"
)


def now_local(
    timezone_name: str,
):
    return datetime.now(
        ZoneInfo(timezone_name)
    )


def scheduled_time(
    day: date,
    job: ScheduledJob,
):
    return datetime.combine(
        day,
        time(
            hour=job.local_hour,
            minute=job.local_minute,
        ),
        tzinfo=ZoneInfo(
            job.timezone
        ),
    )


def get_run(
    session,
    job_code: str,
    run_key: str,
):
    return session.scalar(
        select(JobRun).where(
            JobRun.job_code
            == job_code,

            JobRun.run_key
            == run_key,
        )
    )


def begin_run(
    session,
    job_code: str,
    run_key: str,
    target_day: date,
):
    existing = get_run(
        session,
        job_code,
        run_key,
    )

    if existing is not None:
        return None

    run = JobRun(
        job_code=job_code,
        run_key=run_key,
        target_local_date=target_day,
        status="RUNNING",
    )

    session.add(run)
    session.flush()

    return run


def complete_run(
    run: JobRun,
    status: str,
    message: str,
):
    run.status = status
    run.message = message
    run.completed_at = datetime.now(
        timezone.utc
    )


def prepare_day(
    session,
    target_day: date,
):
    snapshot = session.scalar(
        select(DailySnapshot).where(
            DailySnapshot.local_date
            == target_day
        )
    )

    if snapshot is None:
        snapshot = DailySnapshot(
            local_date=target_day,
            status="OPEN",
            closed_manually=False,
            disc_ranked=False,
        )

        session.add(snapshot)

    # get_today_snapshot also ensures habit/nutrition
    # rows exist when target_day is today.
    today = now_local(
        DEFAULT_TIMEZONE
    ).date()

    if target_day == today:
        get_today_snapshot(
            session
        )

    return snapshot


async def execute_generate_today(
    session,
    job,
    target_day,
):
    run_key = (
        target_day.isoformat()
    )

    run = begin_run(
        session,
        job.code,
        run_key,
        target_day,
    )

    if run is None:
        return

    try:
        prepare_day(
            session,
            target_day,
        )

        complete_run(
            run,
            "SUCCESS",
            "Day prepared.",
        )

        session.commit()

        log.info(
            "generate_today success %s",
            target_day,
        )

    except Exception as exc:
        session.rollback()
        log.exception(
            "generate_today failed"
        )
        raise exc


async def execute_checkin(
    session,
    bot,
    job,
    target_day,
):
    run_key = (
        target_day.isoformat()
    )

    run = begin_run(
        session,
        job.code,
        run_key,
        target_day,
    )

    if run is None:
        return

    try:
        if is_day_closed(
            session,
            target_day,
        ):
            complete_run(
                run,
                "SKIPPED",
                "Day already closed.",
            )

            session.commit()

            log.info(
                "Check-in skipped: day closed."
            )
            return

        snapshot = (
            get_today_snapshot(
                session
            )
        )

        checkin_lines = [
            "🌙 <b>DAILY CHECK-IN</b>",
            "",
            "Day still open.",
            "",
        ]
        if snapshot.focus_target > 0:
            checkin_lines.append(
                f"{snapshot.focus_name}: <b>{snapshot.focus_minutes}/{snapshot.focus_target} min</b>"
            )
        if snapshot.nutrition_state != "DISABLED":
            checkin_lines.append(f"Nutrition: <b>{snapshot.nutrition_state}</b>")
        checkin_lines.extend(["", "Open ☀️ Today to review and close the day."])

        await bot.send_message(USER_ID, "\n".join(checkin_lines))

        complete_run(
            run,
            "SUCCESS",
            "Check-in sent.",
        )

        session.commit()

        log.info(
            "Daily check-in sent."
        )

    except Exception as exc:
        session.rollback()
        log.exception(
            "daily_checkin failed"
        )
        raise exc


async def execute_close_previous(
    session,
    job,
    execution_day,
):
    target_day = (
        execution_day
        - timedelta(days=1)
    )

    run_key = (
        execution_day.isoformat()
    )

    run = begin_run(
        session,
        job.code,
        run_key,
        target_day,
    )

    if run is None:
        return

    try:
        if is_day_closed(
            session,
            target_day,
        ):
            complete_run(
                run,
                "SKIPPED",
                "Previous day already closed.",
            )

            session.commit()
            return

        # Do not fabricate misses for a day when the
        # scheduler itself never prepared the Life RPG day.
        generated = get_run(
            session,
            "generate_today",
            target_day.isoformat(),
        )

        if (
            generated is None
            or generated.status
            != "SUCCESS"
        ):
            complete_run(
                run,
                "SKIPPED",
                (
                    "SYSTEM_DOWNTIME: "
                    "day was not prepared."
                ),
            )

            session.commit()

            log.warning(
                "Skipped automatic close for %s "
                "because generate_today was absent.",
                target_day,
            )
            return

        result = close_day(
            session=session,
            day=target_day,
            manual=False,
        )

        complete_run(
            run,
            "SUCCESS",
            (
                "Previous day closed. "
                f"Focus={result.focus_state}; "
                f"Nutrition={result.nutrition_state}"
            ),
        )

        session.commit()

        log.info(
            "Closed previous day %s",
            target_day,
        )

    except Exception as exc:
        session.rollback()
        log.exception(
            "close_previous_day failed"
        )
        raise exc


async def process_jobs(
    bot: Bot,
):
    with SessionLocal() as session:
        jobs = session.scalars(
            select(ScheduledJob).where(
                ScheduledJob.enabled
                .is_(True)
            )
        ).all()

        for job in jobs:
            local_now = now_local(
                job.timezone
            )

            today = local_now.date()

            due = (
                local_now
                >= scheduled_time(
                    today,
                    job,
                )
            )

            if not due:
                continue

            if job.code == "generate_today":
                await execute_generate_today(
                    session,
                    job,
                    today,
                )

            elif job.code == "daily_checkin":
                await execute_checkin(
                    session,
                    bot,
                    job,
                    today,
                )

            elif (
                job.code
                == "close_previous_day"
            ):
                await execute_close_previous(
                    session,
                    job,
                    today,
                )


async def main():
    bot = Bot(
        token=TOKEN,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML,
        ),
    )

    log.info(
        "Life RPG scheduler online"
    )

    try:
        while True:
            try:
                await process_jobs(
                    bot
                )

            except Exception:
                log.exception(
                    "Scheduler cycle failed"
                )

            await asyncio.sleep(
                POLL_SECONDS
            )

    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
