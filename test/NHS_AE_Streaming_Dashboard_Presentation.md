# NHS A&E Streaming Dashboard — Presentation Script

## Opening — lead with the difference, not the dashboard

*(Pause before starting. Don't open by pointing at the screen.)*

"The batch dashboard I showed earlier answers one question well: what happened over the last three years? This dashboard answers a different question — what is happening right now, in this exact minute?"

*(Pause.)*

"Three years of historical trend data can't tell you that a specific hospital is having a bad afternoon today. This can. I'm going to show you three things this gives you that the batch report can't, and then talk about what it would take to run this against real hospital systems instead of a simulated feed."

## Finding 1 — Proof of a genuinely live feed, not a static snapshot

"This card here — 'Latest Event Time' — is the most important number on the page. It's not a report generated once a month; every time I refresh this dashboard, that timestamp moves forward, because it's querying live data straight from the source system, not a copy sitting in a spreadsheet."

**So what:** *"this is the difference between finding out about a problem next month, and finding out about it while it's still happening."*

## Finding 2 — A real-time safety signal, not a retrospective one

"Look at the disposition breakdown — I've deliberately colour-coded 'Left before treatment' in red. In a live operational setting, if that number starts climbing during a shift, that's an early warning that patients are giving up on waiting — a genuine safety signal that's far more useful to catch in the moment than to discover in a monthly report after the fact."

**So what:** *"this turns a lagging indicator into a live one. The same metric, but caught while there's still time to act on it."*

## Finding 3 — Operational drill-down, by hospital, in real time

"The slicers here let an operations team narrow straight down to one hospital, or one outcome type, during a live incident — without waiting for a data analyst to pull a custom report. If a specific trust is having a difficult afternoon, someone in a control-room type role could isolate that trust's live feed in two clicks."

**So what:** *"this is built for the person managing today, not the person reviewing last quarter."*

## Recommendation

"Three things I'd suggest, in order:"

1. **"Pilot this against a real event-level feed."** Right now this runs on simulated data to prove the architecture works end-to-end — Event Hub, streaming ingestion, live Gold table, live dashboard. The next step is connecting it to an actual hospital system feed, even on a single trust, to validate it against real operational noise.
2. **"Define real thresholds for the safety signals."** 'Left before treatment climbing' is a useful signal, but someone clinical needs to define what level should trigger an actual alert versus normal daily variation.
3. **"Decide who owns watching this."** A live dashboard only has value if someone is actually looking at it during the hours that matter — this needs an operational owner, not just a report that exists.

## The ask

*(End with a concrete ask, not a trailing-off summary.)*

"What I'd like from this group is agreement to identify one real-time data source — even from a single pilot trust — that we could connect this architecture to, so the next version of this isn't running on simulated events."

## If asked: limitations

"To be transparent: the underlying event stream here is synthetic data I generated to prove out the pipeline, not live hospital data — there's no real-time NHS feed connected yet. I'd also flag that the ingestion path uses a polling-based workaround rather than a fully native streaming connector, due to a permissions constraint on the training environment, which I'd resolve differently in a production setting."
