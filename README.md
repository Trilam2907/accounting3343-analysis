# CampusLoop

A simple, mobile-friendly Streamlit prototype for discovering campus events. Students choose at least three hashtag interests before signing up, browse one event at a time, skip or save events, explore recommendations, and review their saved calendar.

## Run locally

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

## Deploy to Streamlit Community Cloud

1. Push this repository to GitHub.
2. In Streamlit Community Cloud, create an app from the repository.
3. Set the main file to `app.py` and deploy.

The app currently uses sample events and Streamlit session state. Account creation is a front-end demo only; data resets when the session ends. The school SSO button is a placeholder.

## Screens and components

| Screen | Layout and main components |
| --- | --- |
| Onboarding | Welcome, multi-select hashtag interests, minimum-three selection count, Continue button |
| Sign-up | Student email form with basic validation, school SSO placeholder, back link |
| Discovery feed | One event card at a time with title, date/time, location, 1–2 sentence description and hashtags; Skip and Add to calendar actions |
| Event detail | Select an event to inspect its details; skip/save actions |
| Calendar | Saved event cards sorted by date |
| Recommendations | Ranked unseen event cards with match hints and save actions |

Streamlit does not provide native swipe gestures; the feed uses clear Skip and Add to calendar buttons as left/right swipe equivalents.

## Data model

- **User:** `id`, `email`, `school_id`, `interests: Hashtag[]`, `created_at`
- **Event:** `id`, `title`, `starts_at`, `location`, `description`, `hashtags: Hashtag[]`, `school_id`
- **Hashtag:** `id`, `label`
- **Like/Dislike:** `user_id`, `event_id`, `reaction` (`like` or `dislike`), `created_at`
- **CalendarEntry:** `user_id`, `event_id`, `saved_at`; created when a user likes an event

## MVP technical plan

- **Working prototype:** Streamlit frontend with sample in-memory events and session-state interactions, deployable to Streamlit Community Cloud.
- **Production mobile app:** React Native frontend; Firebase Authentication for email and campus identity sign-in; Firestore for users, events, reactions, and calendar entries. Enforce school-level access with Firebase security rules. Add a Node.js service only when integrations or more advanced ranking need it.
- **Recommendations:** Exclude liked, disliked, and already-seen events. Rank remaining events by tag overlap: each selected interest match adds one point; each tag shared with liked events adds two points.
- **Next production steps:** Connect authentication and durable storage, replace sample data with school event feeds, and add real calendar sync and native swipe gestures.
