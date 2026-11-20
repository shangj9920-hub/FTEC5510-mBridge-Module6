# Presentation material (Module 6)

Three slides, about 2.5 of the five presentation minutes. Numbers here are the
ones in `docs/RESULTS.md`; nothing is rounded by hand.

---

## Slide 1 — How we measure "better liquidity management"

**Body copy**

- 7 scenarios × 30 formal seeds × 5 strategies = **1,050 simulations**
- same event path per seed → any difference is the policy, not the data
- five metric families: completion, delay, breach, liquidity hours, FX cost
- breach counts payments **overdue at the observation endpoint**, including
  outstanding ones; delay is computed on **settled** payments only

**Footnote**

Every number traces to a `run_id`, a seed and a frozen `config.json`.

**Speaker note (~40 s)**

> We did not stop at "the queue is shorter". We fixed seven scenarios and thirty
> seeds, ran all five strategies on the same event path, and measured five families
> of metrics. Two conventions matter: breach rate counts payments that are already
> due and still unpaid, and delay is only measured on payments that actually
> settled — otherwise "not finishing" would look like "finishing fast".

---

## Slide 2 — Dynamic scheduling wins on time (figure `fig1_benefit.png`)

**Body copy**

- urgent mean delay: S2 lower in **7/7** scenarios, all significant
- `payment_surge` −386 s, `large_payments` −737 s
- urgent completion `payment_surge` 0.670 → 0.908, `large_payments` 0.565 → 0.839
- waiting (S3/S4) cuts FX trades 20–30 % but adds 190–883 s of delay

**Speaker note (~60 s)**

> Every green bar is below the S1 baseline: dynamic scheduling shortens urgent
> settlement everywhere, and the effect explodes exactly where liquidity binds.
> The orange and red bars in the lower panel show what waiting buys: 20 to 30
> percent fewer FX trades. But the upper panel shows the price — with HKD 15
> million available and FX completing in two minutes, waiting costs far more time
> than the top-up it avoids.

---

## Slide 3 — The gain is a reallocation (figure `fig2_fairness.png`)

**Body copy**

- urgent completion **+23.8 pp** (surge) and **+27.4 pp** (large)
- ordinary completion **−4.55 pp** and **−6.21 pp** in those same scenarios
- ordinary overdue **+3.05 pp** / **+5.75 pp**
- total completion still rises (+2.26 / +1.69 pp) — which is why reporting only
  the total would hide the cost

**Speaker note (~50 s)**

> This is the part we want to be judged on. Dynamic scheduling does not create
> service, it moves it: urgent payments gain 24 to 27 percentage points of
> completion, ordinary payments lose 4.5 to 6.2 in exactly the two scenarios where
> liquidity binds. The proposal already warned that better urgent service is not
> protection for everyone, and the data confirms it. That is why our next step is
> the funding-demand weight and a scenario where FX really is unavailable.

---

## If asked: one-line answers

| Question | Answer |
|---|---|
| Why 30 seeds? | proposal §4.5 asks for at least 30 formal seeds paired by seed; the fixture set ships exactly that |
| Why is S1 the baseline? | it differs from S0 only by "skipping allowed", so S0 vs S1 isolates head-of-line blocking |
| Is a completion rate of 0.998 the good news? | it means liquidity does not bind there; the interesting scenarios are the two where it does |
| Why does S3 look worse than the proposal expects? | parameters: HKD 15 m and 120 s FX means waiting rarely pays; `per_trade` capacity means FX is never unavailable |
| Are these real mBridge numbers? | no — synthetic fixtures and teaching assumptions, as the proposal states in §5.3 |
| Where do the 2–5 s differences from Module 4 come from? | Module 5's reviewed engine patch; re-running the unpatched engine reproduces Module 4's numbers exactly |
