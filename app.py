from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any

import streamlit as st


st.set_page_config(
    page_title="CampusLoop | Find your next thing",
    page_icon="🎟️",
    layout="centered",
    initial_sidebar_state="collapsed",
)

INTERESTS = [
    "Sports",
    "Arts",
    "Tech",
    "Academics",
    "Clubs",
    "Volunteering",
    "Music",
    "Career",
]


def build_events() -> list[dict[str, Any]]:
    today = date.today()
    samples = [
        ("Courtside: Hawks vs. Bears", 2, "6:30 PM", "North Gym", "Bring your loudest cheer. Student section doors open 30 minutes early.", ["sports", "clubs"]),
        ("Open Mic on the Quad", 3, "7:00 PM", "Main Quad", "A relaxed night of live music, poetry, and stand-up from students across campus.", ["music", "arts", "clubs"]),
        ("Build Night: Tiny Games", 4, "5:00 PM", "Innovation Lab", "Team up, learn a new tool, and make a tiny game. Beginners are very welcome.", ["tech", "clubs"]),
        ("Internship Prep: Make Your Move", 6, "12:00 PM", "Career Center, Room 204", "Get practical resume feedback and meet recruiters from local organizations.", ["career", "academics"]),
        ("Paint, Plant & Give Back", 8, "10:00 AM", "Student Garden", "Help refresh the campus garden, then make a mini planter to take home.", ["volunteering", "arts"]),
        ("Study Jam: Finals Edition", 9, "4:00 PM", "Learning Commons", "Find a study buddy, grab a snack, and get focused with peer tutors on hand.", ["academics", "clubs"]),
        ("Spring Arts Showcase", 11, "6:00 PM", "Cedar Hall", "See student photography, design, and performance in one lively evening.", ["arts", "music"]),
        ("Club Fair After Hours", 13, "3:30 PM", "Union Ballroom", "Meet campus groups, find your people, and try a quick activity at every table.", ["clubs", "sports", "tech"]),
    ]
    events = []
    for index, (title, offset, event_time, location, description, tags) in enumerate(samples, start=1):
        events.append(
            {
                "id": f"event-{index}",
                "title": title,
                "date": today + timedelta(days=offset),
                "time": event_time,
                "location": location,
                "description": description,
                "hashtags": tags,
            }
        )
    return events


EVENTS = build_events()
EVENT_BY_ID = {event["id"]: event for event in EVENTS}


def initialize_state() -> None:
    defaults = {
        "screen": "onboarding",
        "interests": [],
        "email": "",
        "likes": [],
        "dislikes": [],
        "active_event": EVENTS[0]["id"],
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def tags_markup(tags: list[str]) -> str:
    return " ".join(f'<span class="tag">#{tag}</span>' for tag in tags)


def event_card(event: dict[str, Any], compact: bool = False) -> None:
    st.markdown(
        f"""
        <div class="event-card {'compact' if compact else ''}">
          <div class="event-eyebrow">📅 &nbsp;{event['date'].strftime('%A, %b %-d')} &nbsp;·&nbsp; {event['time']}</div>
          <h2>{event['title']}</h2>
          <div class="event-location">📍 &nbsp;{event['location']}</div>
          <p>{event['description']}</p>
          <div class="tags">{tags_markup(event['hashtags'])}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def next_event() -> dict[str, Any] | None:
    seen = set(st.session_state.likes) | set(st.session_state.dislikes)
    return next((event for event in EVENTS if event["id"] not in seen), None)


def record_reaction(event_id: str, liked: bool) -> None:
    target = st.session_state.likes if liked else st.session_state.dislikes
    other = st.session_state.dislikes if liked else st.session_state.likes
    if event_id not in target:
        target.append(event_id)
    if event_id in other:
        other.remove(event_id)
    st.session_state.active_event = event_id


def recommendation_score(event: dict[str, Any]) -> int:
    liked_tags = {
        tag
        for event_id in st.session_state.likes
        for tag in EVENT_BY_ID[event_id]["hashtags"]
    }
    preferred_tags = {tag.lower() for tag in st.session_state.interests}
    return len(set(event["hashtags"]) & liked_tags) * 2 + len(
        set(event["hashtags"]) & preferred_tags
    )


def render_onboarding() -> None:
    st.markdown('<div class="eyebrow">YOUR CAMPUS, YOUR WAY</div>', unsafe_allow_html=True)
    st.title("Find your next thing.")
    st.write("Pick at least 3 interests. We’ll use them to shape your event feed.")
    st.caption(f"{len(st.session_state.interests)} selected · choose 3 or more")
    st.multiselect(
        "What are you into?",
        INTERESTS,
        key="interests",
        format_func=lambda value: f"#{value.lower()}",
        placeholder="Choose your interests",
        label_visibility="collapsed",
    )
    if len(st.session_state.interests) < 3:
        st.button(
            f"Choose {3 - len(st.session_state.interests)} more to continue",
            disabled=True,
            use_container_width=True,
        )
    elif st.button("Continue to sign up →", type="primary", use_container_width=True):
        st.session_state.screen = "signup"
        st.rerun()
    st.markdown(
        '<div class="privacy-note">No account needed to choose your interests.</div>',
        unsafe_allow_html=True,
    )


def render_signup() -> None:
    st.markdown('<div class="eyebrow">STEP 2 OF 2 · YOUR ACCOUNT</div>', unsafe_allow_html=True)
    st.title("Make it yours.")
    st.write("Your interests are saved. Create a student profile to keep your plans together.")
    with st.form("signup_form"):
        email = st.text_input("Student email", value=st.session_state.email, placeholder="you@school.edu")
        submitted = st.form_submit_button("Create my account →", type="primary", use_container_width=True)
        if submitted:
            if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
                st.error("Enter a valid email address to continue.")
            else:
                st.session_state.email = email.strip()
                st.session_state.screen = "app"
                st.rerun()
    if st.button("Continue with school SSO", use_container_width=True):
        st.info("School SSO is a demo button. Connect your campus identity provider for production.")
    if st.button("← Back to interests"):
        st.session_state.screen = "onboarding"
        st.rerun()


def render_feed() -> None:
    event = next_event()
    st.markdown('<div class="eyebrow">YOUR DISCOVERY FEED</div>', unsafe_allow_html=True)
    st.title("Coming up on campus")
    st.caption("A little swipe-inspired: skip or save each event to tune your feed.")
    if event is None:
        st.success("You’re all caught up! Check Recommendations for more ideas.")
        return
    event_card(event)
    left, right = st.columns(2)
    with left:
        if st.button("✕  Not for me", use_container_width=True):
            record_reaction(event["id"], False)
            st.toast("Skipped — we’ll tune your suggestions.")
            st.rerun()
    with right:
        if st.button("♥  Add to calendar", type="primary", use_container_width=True):
            record_reaction(event["id"], True)
            st.toast("Saved to your calendar!")
            st.rerun()
    with st.expander("Event details"):
        st.write(event["description"])
        st.caption(f"📍 {event['location']} · {event['date'].strftime('%B %-d')} at {event['time']}")


def render_event_detail() -> None:
    st.markdown('<div class="eyebrow">EVENT DETAILS</div>', unsafe_allow_html=True)
    st.title("Take a closer look")
    event_id = st.selectbox(
        "Choose an event",
        list(EVENT_BY_ID),
        format_func=lambda event_key: EVENT_BY_ID[event_key]["title"],
        key="detail_event",
    )
    event = EVENT_BY_ID[event_id]
    event_card(event)
    first, second = st.columns(2)
    with first:
        if st.button("Skip this event", use_container_width=True):
            record_reaction(event_id, False)
            st.toast("Skipped — we’ll tune your suggestions.")
            st.rerun()
    with second:
        if st.button("♥  Add to calendar", type="primary", use_container_width=True):
            record_reaction(event_id, True)
            st.toast("Saved to your calendar!")
            st.rerun()


def render_calendar() -> None:
    st.markdown('<div class="eyebrow">YOUR PLANS</div>', unsafe_allow_html=True)
    st.title("My calendar")
    saved = sorted(
        (EVENT_BY_ID[event_id] for event_id in st.session_state.likes),
        key=lambda event: (event["date"], event["time"]),
    )
    if not saved:
        st.info("Your calendar is ready when you are. Like an event to save it here.")
        return
    st.caption(f"{len(saved)} event{'s' if len(saved) != 1 else ''} saved")
    for event in saved:
        event_card(event, compact=True)


def render_recommendations() -> None:
    st.markdown('<div class="eyebrow">PICKED FOR YOU</div>', unsafe_allow_html=True)
    st.title("Recommendations")
    st.caption("Based on your interests and the events you’ve liked.")
    seen = set(st.session_state.likes) | set(st.session_state.dislikes)
    candidates = sorted(
        (event for event in EVENTS if event["id"] not in seen),
        key=lambda event: (-recommendation_score(event), event["date"]),
    )
    if not candidates:
        st.info("You’ve seen every event in this demo. Check back for new campus events.")
        return
    for event in candidates:
        score = recommendation_score(event)
        if score:
            st.caption(f"✨ {score} shared interest{'s' if score != 1 else ''}")
        event_card(event, compact=True)
        if st.button("♥  Add to calendar", key=f"recommend-{event['id']}", type="primary"):
            record_reaction(event["id"], True)
            st.toast("Saved to your calendar!")
            st.rerun()


def render_blueprint() -> None:
    with st.expander("MVP blueprint · screens, data & build plan"):
        st.markdown(
            """
### Screen-by-screen layout
- **Onboarding:** Welcome, multi-select interest chips (minimum 3), selection count, Continue. Components: heading, hashtag picker, progress hint, primary button.
- **Sign-up:** Student email form or school SSO entry, with a back link. Account creation is only available after interests are selected. Components: email input, validation, SSO button.
- **Discovery feed:** One upcoming swipe-style event card at a time; Skip acts like a left swipe, Add to calendar acts like a right swipe. Components: date/time, title, location, description, hashtags, reaction buttons, details expander.
- **Event detail:** Full event information and direct skip/save actions. Components: event selector, detail card, location/time, actions.
- **Calendar:** Saved events in date order. Components: agenda cards, date/time, location, empty state.
- **Recommendations:** Remaining events ordered by shared tags from selected interests and liked events. Components: ranked cards, match hint, save action.

### Main data model
- **User:** `id`, `email`, `school_id`, `interests: Hashtag[]`, `created_at`
- **Event:** `id`, `title`, `starts_at`, `location`, `description`, `hashtags: Hashtag[]`, `school_id`
- **Hashtag:** `id`, `label`
- **Like/Dislike:** `user_id`, `event_id`, `reaction` (`like` or `dislike`), `created_at`
- **CalendarEntry:** `user_id`, `event_id`, `saved_at` (created from a like; removable later)

### MVP implementation plan
- **This prototype:** Streamlit UI with in-memory sample events and session-state interactions, deployable to Streamlit Community Cloud.
- **Production mobile app:** React Native frontend; Firebase Authentication (email + campus SSO), Firestore for users/events/reactions/calendar, and Firebase security rules scoped by school. Use a Node.js service only if campus integrations or more advanced ranking require it.
- **Recommendation logic:** Rank unseen events by tag overlap: selected interests count once and each liked-event tag overlap counts twice; exclude skipped and already saved events. This transparent baseline can later be replaced with behavioral ranking.
- **Prototype limitation:** Session state and sample events reset when the app session ends; authentication, durable storage, real swipe gestures, and school SSO require backend integration.
"""
        )


def render_app() -> None:
    st.markdown(
        f'<div class="topbar"><span class="brand">🎟️ CampusLoop</span>'
        f'<span class="profile">{st.session_state.email}</span></div>',
        unsafe_allow_html=True,
    )
    pages = {
        "Discover": render_feed,
        "Event detail": render_event_detail,
        "Calendar": render_calendar,
        "For you": render_recommendations,
    }
    page = st.radio(
        "Navigate",
        list(pages),
        horizontal=True,
        label_visibility="collapsed",
    )
    pages[page]()
    render_blueprint()


st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@600;700;800&display=swap');
    :root { --ink:#17231f; --muted:#6c7973; --green:#176b4d; --mint:#eaf5ee; --line:#e7ece8; }
    .stApp { background: #f7f9f7; color: var(--ink); font-family: 'DM Sans', sans-serif; }
    .main .block-container { max-width: 720px; padding-top: 1.5rem; padding-bottom: 4rem; }
    h1,h2,h3 { font-family: 'Manrope', sans-serif !important; color: var(--ink) !important; letter-spacing:-.035em; }
    h1 { font-size: clamp(2rem, 6vw, 2.8rem) !important; margin: .25rem 0 .4rem !important; }
    .eyebrow { color:var(--green); font-size:.72rem; font-weight:700; letter-spacing:.13em; margin:1.6rem 0 .5rem; }
    .topbar { display:flex; justify-content:space-between; align-items:center; padding:0 0 1rem; border-bottom:1px solid var(--line); }
    .brand { font-family:'Manrope',sans-serif; font-weight:800; font-size:1.08rem; }
    .profile { color:var(--muted); font-size:.78rem; }
    .event-card { background:#fff; border:1px solid var(--line); border-radius:20px; padding:1.45rem; margin:.6rem 0 1rem; box-shadow:0 8px 26px rgba(20,54,38,.045); }
    .event-card h2 { font-size:1.45rem; line-height:1.22; margin:.65rem 0 .5rem; }
    .event-card p { color:#46544d; line-height:1.6; margin:.85rem 0 1rem; }
    .event-eyebrow,.event-location { color:var(--muted); font-size:.86rem; }
    .event-location { margin-top:.45rem; }
    .event-card.compact { padding:1.15rem; }
    .event-card.compact h2 { font-size:1.18rem; }
    .tags { display:flex; flex-wrap:wrap; gap:.45rem; }
    .tag { display:inline-block; color:#176b4d; background:var(--mint); border-radius:99px; padding:.32rem .62rem; font-size:.75rem; font-weight:600; }
    .privacy-note { color:var(--muted); text-align:center; font-size:.8rem; padding:1rem; }
    div[data-testid="stRadio"] div[role="radiogroup"] { gap:.4rem; }
    div[data-testid="stRadio"] label { background:#fff; border:1px solid var(--line); border-radius:99px; padding:.45rem .8rem; }
    .stButton button, .stFormSubmitButton button { border-radius:12px; min-height:2.8rem; font-weight:600; }
    [data-testid="stExpander"] { border-color:var(--line); border-radius:14px; }
    @media (max-width: 600px) {
      .main .block-container { padding:1rem 1rem 3rem; }
      .event-card { padding:1.2rem; }
      .topbar { margin-bottom:.4rem; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

initialize_state()
if st.session_state.screen == "onboarding":
    render_onboarding()
elif st.session_state.screen == "signup":
    render_signup()
else:
    render_app()
