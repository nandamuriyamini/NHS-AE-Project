# NHS Gold Layer — Business Value Summary

This document explains why the redesigned Gold layer (8 tables, rebuilt to address the feedback
that the previous version lacked real aggregation) provides genuine business value — what
question each table answers, and why that question matters operationally or strategically.

---

## 1. `national_monthly_trend`
**What it does:** Adds up every hospital trust's monthly attendance and admission figures into a
single national total per month.

**Business value:** This is the headline monthly snapshot — "how is the whole NHS A&E system doing
this month?" Useful for spotting seasonal patterns (e.g. winter pressure) and tracking whether
national interventions are having any visible effect month to month.

## 2. `national_yearly_trend`
**What it does:** Rolls the monthly data up further into one row per year, and calculates a real
percentage — `pct_over4hrs` — the share of all national attendances that breached the 4-hour target
that year.

**Business value:** This is the number a board or senior leadership actually tracks year over year
against the NHS's 95% target. It turns "lots of monthly numbers" into a single comparable trend
line — the basis for a "are we improving or not" conversation at the highest level.

## 3. `trust_performance_ranking`
**What it does:** For every trust, every period, calculates (a) a **rank** against every other
trust for that same period, based on 4-hour performance, and (b) how much that trust's performance
**changed** compared to its own previous period.

**Business value:** This is the most actionable table in the set. It directly answers two questions
leadership actually asks: "who is performing best/worst right now," and "is a given trust getting
better or worse over time." This is what supports identifying a trust worth studying (a genuine
best-practice case) versus one that needs urgent intervention — rather than just listing numbers
with no comparison.

## 4. `regional_summary`
**What it does:** Groups every trust up by NHS region, totals their attendance figures, averages
their 4-hour performance, and counts how many trusts are in each region.

**Business value:** Answers "which part of the country is under the most pressure" — a resourcing
and policy question that can't be answered by looking at individual trusts one at a time. Useful
for regional leadership and for deciding where additional funding or staffing support is most
needed.

## 5. `nel_ytd_growth_rates`
**What it does:** Cleaned-up version of NHS's own pre-calculated year-to-date non-elective
admission growth figures, with one addition: `region_avg_growth`, the average growth rate across
all trusts in that trust's region.

**Business value:** Non-elective (emergency) admission growth is a key capacity-planning signal —
if it's growing faster than a trust's region average, that trust may be facing disproportionate
pressure worth investigating ahead of a capacity crunch.

## 6. `ecds_demographic_summary`
**What it does:** Consolidates five previously separate tables (age, gender, ethnicity, chief
complaint, frailty) into one, summing and averaging each category's values across all periods and
report types.

**Business value:** Answers "who is actually coming to A&E, and how is that mix changing over time"
— directly relevant to staffing mix, triage design, and where public health messaging should be
targeted (e.g. the earlier finding that working-age adults, not the elderly, dominate demand).

## 7. `ecds_org_summary`
**What it does:** For every organisation, sums and averages every metric across all available
reporting periods, and counts how many periods of data exist for that organisation.

**Business value:** Gives a "lifetime" view per organisation rather than a single snapshot — useful
for spotting which organisations are consistently high-activity versus which only spike
occasionally, which matters for longer-term resourcing decisions.

## 8. `ecds_performance`
**What it does:** For every metric and period, calculates the average, minimum, and maximum value
across all organisations reporting it, plus how many organisations reported.

**Business value:** Shows the spread, not just an average — "most hospitals were around X, but the
worst was Y and the best was Z." This is what surfaces outliers worth investigating, in either
direction (a strong performer worth learning from, or a struggling one needing support).

---

## Why this addresses the original feedback

The previous 11-table version mostly copied or relabelled columns from Silver without calculating
anything new. Every one of these 8 tables now does genuine aggregation — `SUM`, `AVG`, `RANK`, or a
period-over-period comparison via `LAG` — which is the actual point of a Gold layer: turning raw,
cleaned data into numbers a business audience can act on directly, rather than just a tidier copy of
the same rows.
