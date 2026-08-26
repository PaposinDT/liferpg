import {
  useEffect,
  useState,
} from "react";

type View =
  | "overview"
  | "character"
  | "achievements"
  | "skills"
  | "quests"
  | "timeline"
  | "reports";

const views: View[] = [
  "overview",
  "character",
  "achievements",
  "skills",
  "quests",
  "timeline",
  "reports",
];

const labels: Record<View, string> = {
  overview: "Command",
  character: "Character",
  achievements: "Achievements",
  skills: "Skills",
  quests: "Quests",
  timeline: "Timeline",
  reports: "Reports",
};

async function load(path: string) {
  const response = await fetch(
    `/api/dashboard/${path}`
  );

  if (!response.ok) {
    throw new Error(
      `HTTP ${response.status}`
    );
  }

  return response.json();
}

function Meter({
  value,
  max,
}: {
  value: number;
  max: number;
}) {
  const pct = max > 0
    ? Math.min(100, value / max * 100)
    : 0;

  return (
    <div className="meter">
      <div
        className="meterFill"
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

function State({
  value,
}: {
  value?: string | null;
}) {
  return (
    <span className={
      `state state-${(
        value || "pending"
      ).toLowerCase()}`
    }>
      {value || "PENDING"}
    </span>
  );
}

function Overview({ data }: { data: any }) {
  const c = data?.character ?? {};
  const priorityOperations = Array.isArray(data?.priority_operations) ? data.priority_operations : [];
  const habits = Array.isArray(data?.habits) ? data.habits : [];

  return (
    <>
      <section className="hero">
        <div>
          <div className="eyebrow">
            OPERATOR PROFILE
          </div>
          <h1>{c?.name}</h1>
          <div className="subtitle">
            {c?.title}
          </div>
        </div>

        <div className="levelBox">
          <span>LVL</span>
          <strong>{c?.level}</strong>
          <small>{c?.xp} CXP</small>
        </div>
      </section>

      <div className="sectionTitle">
        PRIORITY OPERATIONS
      </div>

      <div className="grid">
        {priorityOperations.map(
          (op: any) => (
            <article
              className="card"
              key={op.quest_code}
            >
              <div className="cardTag">
                {op.title}
              </div>

              <h2>{op.skill}</h2>

              <div className="bigMetric">
                {op.current}
                <span> / {op.minimum}</span>
              </div>

              <Meter
                value={op.current}
                max={op.minimum}
              />

              <p>
                Stretch target {op.stretch}
              </p>
            </article>
          )
        )}
      </div>

      <div className="sectionTitle">
        DAILY SYSTEMS
      </div>

      <div className="grid">
        {habits.map(
          (habit: any) => (
            <article
              className="card compact"
              key={habit.code}
            >
              <div>
                <h3>{habit.name}</h3>
                {habit.minimum_minutes && (
                  <p>
                    Target · {
                      habit.minimum_minutes
                    } min
                  </p>
                )}
              </div>

              <State value={habit.state} />
            </article>
          )
        )}

        {data.nutrition && (
          <article className="card compact">
            <div>
              <h3>Nutrition</h3>
              <p>
                Target · {data.nutrition.adjusted_target_kcal ?? data.nutrition.base_target_kcal ?? "—"} kcal
              </p>
            </div>
            <State
              value={
                data.nutrition.target_reached === true
                  ? "DONE"
                  : data.nutrition.target_reached === false
                  ? "MISSED"
                  : "PENDING"
              }
            />
          </article>
        )}

        <article className="card compact">
          <div>
            <h3>Discipline</h3>
            <p>
              {data.day?.disc_ranked
                ? `Score ${data.day.disc_score}`
                : "Calibration"}
            </p>
          </div>
          <State
            value={
              data.day?.status || "OPEN"
            }
          />
        </article>
      </div>
    </>
  );
}

function Character({
  data,
}: {
  data: any;
}) {
  const c = data?.character ?? {};
  const a = data?.achievements ?? {};
  const unlocked = Number(a?.unlocked ?? 0);
  const total = Number(a?.total ?? 0);
  const pct = total > 0
    ? Math.round(unlocked / total * 100)
    : 0;

  return (
    <>
      <div className="pageHeader">
        <div>
          <div className="eyebrow">OPERATOR RECORD</div>
          <h1>Character</h1>
        </div>
      </div>

      <section className="hero">
        <div>
          <div className="eyebrow">CALLSIGN</div>
          <h1>{c?.name || "UNKNOWN"}</h1>
          <div className="subtitle">{c?.title || "Unranked Operator"}</div>
        </div>
        <div className="levelBox">
          <span>LVL</span>
          <strong>{c?.level ?? 0}</strong>
          <small>{c?.xp ?? 0} CXP</small>
        </div>
      </section>

      <div className="sectionTitle">ACHIEVEMENT RECORD</div>
      <article className="card">
        <div className="cardTag">UNLOCK PROGRESS</div>
        <div className="bigMetric">
          {unlocked}<span> / {total}</span>
        </div>
        <Meter value={unlocked} max={total} />
        <p>{pct}% of current achievement definitions unlocked.</p>
      </article>
    </>
  );
}

function Achievements({
  data,
}: {
  data: any;
}) {
  const items = Array.isArray(data)
    ? data
    : [];

  const unlocked = items.filter(
    (item: any) => item?.unlocked === true
  ).length;

  return (
    <>
      <div className="pageHeader">
        <div>
          <div className="eyebrow">
            OPERATOR RECORD
          </div>
          <h1>Achievement Hall</h1>
        </div>

        <strong>
          {unlocked}/{items.length}
        </strong>
      </div>

      {items.length === 0 ? (
        <div className="empty">
          No achievement data available.
        </div>
      ) : (
        <div className="achievementGrid">
          {items.map((item: any) => (
            <article
              key={String(item.code)}
              className={
                item.unlocked
                  ? "achievement achievementUnlocked"
                  : "achievement achievementLocked"
              }
            >
              <div className="achievementTop">
                <span className="cardTag">
                  {item.category || "GENERAL"}
                </span>

                <span className="rarity">
                  {item.rarity || "UNKNOWN"}
                </span>
              </div>

              <div className="achievementIcon">
                {item.unlocked ? "◆" : "◇"}
              </div>

              <h3>
                {item.name || "Unnamed Achievement"}
              </h3>

              <p>
                {item.description || ""}
              </p>

              <small>
                {item.unlocked
                  ? "UNLOCKED"
                  : item.secret
                  ? "CLASSIFIED"
                  : "LOCKED"}
              </small>
            </article>
          ))}
        </div>
      )}
    </>
  );
}


function Skills({
  data,
}: {
  data: any;
}) {
  const items = Array.isArray(data) ? data : [];

  return (
    <>
      <div className="pageHeader">
        <div>
          <div className="eyebrow">
            OPERATOR CAPABILITIES
          </div>
          <h1>Skills</h1>
        </div>

        <strong>{items.length}</strong>
      </div>

      <div className="skillGrid">
        {items.map((skill) => {
          const progress =
            skill.level_progress || {};

          const checkpoint =
            skill.checkpoint;

          return (
            <article
              className="skillCard"
              key={skill.code}
            >
              <div className="skillHeader">
                <div>
                  <span className="category">
                    {skill.category}
                  </span>

                  <h2>{skill.name}</h2>

                  <small>
                    {skill.priority} · {skill.status}
                  </small>
                </div>

                <div className="skillLevel">
                  <span>LVL</span>
                  <strong>{skill.level}</strong>
                </div>
              </div>

              <div className="skillXP">
                <div>
                  <span>{skill.xp} total XP</span>
                  <span>
                    {progress.next_threshold
                      ? `${progress.percent}%`
                      : "MAX"}
                  </span>
                </div>

                <Meter
                  value={
                    progress.xp_into_level || 0
                  }
                  max={
                    progress.xp_required || 1
                  }
                />
              </div>

              {progress.next_threshold && (
                <div className="skillNext">
                  Next level · {
                    progress.xp_into_level
                  } / {
                    progress.xp_required
                  } XP
                </div>
              )}

              {skill.banked_xp > 0 && (
                <div className="banked">
                  BANKED XP · +{skill.banked_xp}
                </div>
              )}

              {checkpoint && (
                <div className={
                  checkpoint.reached
                    ? "checkpoint checkpointReached"
                    : "checkpoint"
                }>
                  <span>
                    CHECKPOINT · LVL {
                      checkpoint.level
                    }
                  </span>

                  <b>{checkpoint.name}</b>

                  <small>
                    {checkpoint.reached
                      ? "GATE REACHED"
                      : checkpoint.status}
                  </small>
                </div>
              )}
            </article>
          );
        })}
      </div>
    </>
  );
}


function Quests({
  data,
}: {
  data: any;
}) {
  const items = Array.isArray(data) ? data : [];
  function formatGoal(
    value: number,
    unit?: string,
  ) {
    const normalized = (
      unit || ""
    ).toUpperCase();

    if (
      normalized === "G"
      || normalized === "GRAM"
      || normalized === "GRAMS"
      || normalized === "WEIGHT_G"
    ) {
      return `${(value / 1000).toFixed(1)} kg`;
    }

    if (
      normalized === "LVL"
      || normalized === "LEVEL"
      || normalized === "SKILL_LEVEL"
    ) {
      return `LVL ${Math.round(value)}`;
    }

    return `${value} ${unit || ""}`.trim();
  }

  return (
    <>
      <div className="pageHeader">
        <div>
          <div className="eyebrow">
            ACTIVE OBJECTIVES
          </div>
          <h1>Quests</h1>
        </div>

        <strong>
          {items.filter(
            (q) => q.status === "ACTIVE"
          ).length} ACTIVE
        </strong>
      </div>

      <div className="questGrid">
        {items.map((quest) => {
          const weekly =
            quest.weekly_progress;

          const goal =
            quest.goal_progress;

          return (
            <article
              className="questCard"
              key={quest.code}
            >
              <div className="questHeader">
                <div>
                  <span className="cardTag">
                    {quest.type}
                  </span>

                  <h2>
                    {quest.title}
                  </h2>
                </div>

                <State
                  value={quest.status}
                />
              </div>

              {quest.description && (
                <p className="questDescription">
                  {quest.description}
                </p>
              )}

              {quest.skill && (
                <div className="questSkill">
                  LINKED SKILL ·
                  <b> {quest.skill}</b>
                </div>
              )}

              {weekly && (
                <div className="questProgress">
                  <div className="questProgressHead">
                    <span>
                      WEEKLY MINIMUM
                    </span>

                    <strong>
                      {weekly.current}
                      /{weekly.minimum}
                    </strong>
                  </div>

                  <Meter
                    value={weekly.current}
                    max={weekly.minimum}
                  />

                  <small>
                    Stretch · {
                      weekly.stretch
                    } sessions
                  </small>
                </div>
              )}

              {goal && (
                <div className="questProgress">
                  <div className="questProgressHead">
                    <span>
                      MAIN OBJECTIVE
                    </span>

                    <strong>
                      {goal.percent}%
                    </strong>
                  </div>

                  <Meter
                    value={goal.current}
                    max={goal.target}
                  />

                  <small>
                    {formatGoal(
                      goal.current,
                      goal.unit,
                    )}
                    {" → "}
                    {formatGoal(
                      goal.target,
                      goal.unit,
                    )}
                  </small>
                </div>
              )}

              {quest.target_date && (
                <div className="questDeadline">
                  TARGET DATE · {
                    quest.target_date
                  }
                </div>
              )}
            </article>
          );
        })}
      </div>
    </>
  );
}


function Timeline({
  data,
}: {
  data: any;
}) {
  const items = Array.isArray(data) ? data : [];
  function formatTime(value: string) {
    const d = new Date(value);

    return d.toLocaleString(
      undefined,
      {
        year: "numeric",
        month: "short",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      }
    );
  }

  return (
    <>
      <div className="pageHeader">
        <div>
          <div className="eyebrow">
            OPERATIONAL HISTORY
          </div>
          <h1>Timeline</h1>
        </div>

        <strong>
          {items.length} EVENTS
        </strong>
      </div>

      {items.length === 0 ? (
        <div className="empty">
          No timeline events recorded.
        </div>
      ) : (
        <div className="timeline">
          {items.map((event, index) => (
            <div
              className="timelineItem"
              key={`${event.occurred_at}-${index}`}
            >
              <div className="timelineDot" />

              <div className="timelineBody">
                <div className="timelineMeta">
                  <span>{event.type}</span>

                  <span>
                    SIGNIFICANCE · {
                      event.significance ?? 0
                    }
                  </span>
                </div>

                <h3>{event.title}</h3>

                <p>{event.description}</p>

                <small>
                  {formatTime(event.occurred_at)}
                </small>
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}


function Reports({
  data,
}: {
  data: any;
}) {
  const items = Array.isArray(data) ? data : [];
  return (
    <>
      <div className="pageHeader">
        <div>
          <div className="eyebrow">
            INTELLIGENCE ARCHIVE
          </div>
          <h1>Reports</h1>
        </div>

        <strong>
          {items.length}
        </strong>
      </div>

      {items.length === 0 ? (
        <div className="empty">
          <b>NO FROZEN REPORTS</b>
          <p>
            Weekly and monthly reports will
            appear here after generation.
          </p>
        </div>
      ) : (
        <div className="reportGrid">
          {items.map((report) => (
            <article
              className="report"
              key={report.id}
            >
              <div className="reportHeader">
                <div>
                  <span className="cardTag">
                    {report.type}
                  </span>

                  <h3>
                    {report.period_start}
                    {" → "}
                    {report.period_end}
                  </h3>
                </div>

                <span className="reportVersion">
                  V{report.version}
                </span>
              </div>

              <div className="reportStatus">
                {report.status}
              </div>

              <pre>
                {report.content}
              </pre>

              <small>
                Generated · {
                  new Date(
                    report.generated_at
                  ).toLocaleString()
                }
              </small>
            </article>
          ))}
        </div>
      )}
    </>
  );
}


export default function App() {
  const [view, setView] =
    useState<View>("overview");

  const [data, setData] =
    useState<any>(null);

  const [error, setError] =
    useState("");

  useEffect(() => {
    setData(null);
    setError("");

    load(view)
      .then(setData)
      .catch((err) => {
        setError(String(err));
      });
  }, [view]);

  let content;

  if (error) {
    content = (
      <div className="empty">
        API unavailable · {error}
      </div>
    );
  } else if (!data) {
    content = (
      <div className="loading">
        LOADING OPERATION STATE...
      </div>
    );
  } else if (view === "overview") {
    content = <Overview data={data} />;
  } else if (view === "character") {
    content = <Character data={data} />;
  } else if (view === "achievements") {
    content = <Achievements data={data} />;
  } else if (view === "skills") {
    content = <Skills data={data} />;
  } else if (view === "quests") {
    content = <Quests data={data} />;
  } else if (view === "timeline") {
    content = <Timeline data={data} />;
  } else {
    content = <Reports data={data} />;
  }

  return (
    <div className="app">
      <aside>
        <div className="brand">
          <div className="brandMark">LR</div>
          <div>
            <b>LIFE RPG</b>
            <small>NIGHT OPS</small>
          </div>
        </div>

        <nav>
          {views.map((item) => (
            <button
              key={item}
              className={
                view === item
                  ? "active"
                  : ""
              }
              onClick={() => setView(item)}
            >
              {labels[item]}
            </button>
          ))}
        </nav>

        <div className="readOnly">
          READ ONLY
          <span>LIVE SYSTEM</span>
        </div>
      </aside>

      <main>
        <header>
          <span>
            LIFE RPG // COMMAND SYSTEM
          </span>
          <span className="online">
            ● ONLINE
          </span>
        </header>

        <div className="content">
          {content}
        </div>
      </main>
    </div>
  );
}
