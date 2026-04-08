# MillionWays Swarm -- Product Overview

## What It Is

MillionWays Swarm is a multi-agent simulation engine that predicts how real executives would behave in hypothetical strategic scenarios. Each executive is powered by a **Thorsten 4 psychological profile** -- a deep behavioral model covering motives, cognition, affect, stress response, and interpersonal style -- combined with an LLM that embodies the person's public voice and decision-making patterns.

The result: an analyst can type a scenario ("Regulators launch antitrust probes into AI labs while a cheap open-source model drops"), select executives (e.g. Sam Altman, Sundar Pichai, Alex Karp, Dario Amodei), and watch a multi-round simulation unfold in real time -- complete with world events sourced from the live web, market reactions, and a final strategic assessment with predictions.

---

## How It Works

```
Scenario + Executives
        |
        v
  +-----------+       +-------------------+
  | SimAgents |<------| Thorsten 4 Profile |
  | (one per  |       | + Wikipedia/public |
  | executive)|       | record context     |
  +-----------+       +-------------------+
        |
        v
  [Round 1: Each agent responds to the scenario]
        |
        v
  +------------------+
  | Narrator (GPT-5.4|    <-- web search grounded
  | + web search)    |    <-- reasoning model
  +------------------+
        |
        v
  [World response: market moves, press, policy,
   new developments with citations]
        |
        v
  [Rounds 2-N: Agents respond to narrator's world
   update + other executives' prior actions]
        |
        v
  +------------------+
  | Final Analysis   |    <-- same narrator model
  +------------------+
        |
        v
  [Per-executive assessment, predictions at
   1 week / 1 month / 3 months, strategic
   winner/loser, overall narrative]
        |
        v
  Markdown Report saved to disk
```

### Key steps in detail:

1. **Profile Loading** -- Thorsten 4 profiles (motives like Power/Achievement/Contact, cognitive style, stress regulation, interpersonal tendencies) are loaded for each selected executive.

2. **Agent Construction** -- Each executive gets a system prompt that tells the LLM to speak as that person, using the Thorsten 4 profile as the psychological reality behind their voice and decisions. Wikipedia context and any prior knowledge are injected.

3. **Round Execution** -- Each agent responds to the current situation. The LLM (GPT-5.4-mini) generates their actions, statements, and strategic moves.

4. **Narrator / World Simulation** -- A more powerful reasoning model (GPT-5.4 with medium reasoning effort) acts as the world simulator. It uses web search to find real, current news and data, then generates: what the world would realistically do in response, new developments with source citations, time gaps between rounds, and per-executive relevance tags.

5. **Final Analysis** -- After all rounds, the narrator produces a structured assessment: how well each executive matched their psychological profile, their strongest move, their exposed weakness, trajectory predictions at 1-week / 1-month / 3-month horizons, and an overall strategic narrative.

---

## The Role of Thorsten 4

Thorsten 4 is our proprietary behavioral analysis model. For each executive, it produces:

- **Core Motives** -- Power, Achievement, and Contact drive percentages (e.g. Alex Karp: 99% Power, 1% Achievement, 0% Contact)
- **Emotional Style** -- Approach vs. Avoidance dominance (e.g. Dario Amodei: 63% Avoidance)
- **Cognitive Preferences** -- Analytical vs. Holistic, Internal vs. External processing, Detail vs. Big-picture, Path vs. Goal orientation
- **Stress Response** -- Self-regulation, stress resilience, action orientation after failure
- **Interpersonal Style** -- Personality style (agreeable, independent, assertive), dominant cognitive system
- **Behavioral Descriptions** -- Rich narrative text explaining how each dimension manifests in the person's actual behavior

These profiles are not suggestions to the LLM -- they are the psychological ground truth that shapes how each executive thinks, decides, and communicates in the simulation.

---

## What the User Sees

The app has a browser-based console (dark theme, real-time streaming):

1. **Setup** -- Pick executives from a grid (toggle cards), write or paste a scenario, set number of rounds (1-10)
2. **Live Simulation** -- Watch each agent "think" and act in real time via server-sent events. See narrator world updates between rounds with cited sources.
3. **Final Report** -- Per-executive analysis, predictions, strategic assessment. Downloadable as a Markdown report.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python, FastAPI, Uvicorn |
| Agent LLM | OpenAI GPT-5.4-mini (chat completions) |
| Narrator LLM | OpenAI GPT-5.4 with reasoning + web search |
| Behavioral Profiles | Thorsten 4 API (api.millionways.ai) |
| Frontend | Vanilla HTML/CSS/JS, server-sent events |
| Streaming | SSE (Server-Sent Events) for live updates |

---

## Current Executives Available

| Name | Company | Key Profile Trait |
|------|---------|------------------|
| Sam Altman | OpenAI | Power-driven (55%), agreeable style, balanced approach/avoidance |
| Sundar Pichai | Google / Alphabet | Extreme achievement (98%), very low power (1%) |
| Elon Musk | Tesla / SpaceX | High power (84%), strong approach orientation (70%) |
| Dario Amodei | Anthropic | Power-driven (63%), strong avoidance (63%), analytical, independent |
| Alex Karp | Palantir | Near-total power drive (99%), zero contact orientation |
| Theodore Sarandos | Netflix | Power + Achievement blend (60/39%), approach-dominant |

---

## Example Output (Summary)

From a simulation of the antitrust/open-source scenario with Pichai, Karp, Amodei, and Altman:

- **Winner:** Alex Karp -- repositioned Palantir as the model-neutral governance layer exactly when buyers demanded diversification and fallback
- **Most Vulnerable:** Dario Amodei -- Anthropic's trust brand became both its greatest asset and its most exposed flank under safety-policy scrutiny
- **Key Turning Point:** When enterprise buyers converted abstract anxiety into procurement demands for auditable guarantees
- **1-week Prediction (high confidence):** Enterprise procurement teams intensify written-guarantee requests; Palantir benefits from neutral-layer positioning
- **3-month Prediction (medium confidence):** Market bifurcates into cheap open-source for internal workloads and premium governed stacks for regulated deployments

---

## What Makes This Different

1. **Psychologically grounded** -- Not generic LLM roleplay. Each agent is driven by a validated behavioral profile that shapes HOW they think and decide, not just what they know.

2. **Web-grounded narrator** -- The world simulation pulls real, current news and data to make predictions realistic and timely.

3. **Competitive advantage is Thorsten 4** -- The behavioral profiles are our proprietary moat. The LLM provides the voice; Thorsten provides the behavioral truth.

4. **Streaming real-time experience** -- Users watch the simulation unfold live, seeing each executive deliberate and the world respond.

---

## What Would Make It More Valuable

- **Ensemble runs** -- Run the same scenario multiple times and report consensus vs. variance
- **Backtesting** -- Compare past predictions to actual outcomes for calibration
- **Structured quantitative outputs** -- Probabilities, share-shift estimates, confidence intervals alongside narrative
- **Custom executive profiles** -- Upload transcripts or interview data to generate Thorsten 4 profiles for any person
- **Decision linkage** -- Explicit investment implications (long/short, catalysts, falsifiers)
