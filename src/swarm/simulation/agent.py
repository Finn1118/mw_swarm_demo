"""Individual simulation agent representing an executive, powered by Thorsten 4 profiles."""

from dataclasses import dataclass, field


def _get_description_text(desc_obj) -> str:
    """Extract description text from either format (string or dict with 'description' key)."""
    if isinstance(desc_obj, dict):
        return desc_obj.get("description", "")
    if isinstance(desc_obj, str):
        return desc_obj
    return ""


@dataclass
class SimAgent:
    """An agent backed by a Thorsten 4 behavioral profile."""

    name: str
    title: str
    company: str
    sector: str
    profile: dict
    knowledge_context: dict
    wiki_context: dict | None = None
    other_agents: list[str] = field(default_factory=list)
    actions_taken: list[dict] = field(default_factory=list)

    # ── Profile parsing ──────────────────────────────────────────────

    def _parse_profile(self) -> dict:
        """Normalize both profile formats into a common structure."""
        p = self.profile
        is_api_v2 = p.get("object") == "analysis"

        if is_api_v2:
            motives = p.get("motives", {})
            affect = p.get("affect", {})
            cognition = p.get("cognition", {})
            descriptions = p.get("descriptions", {})
            motive_desc = descriptions.get("motives", {})
            cognition_desc = descriptions.get("cognition", {})
            affect_desc = descriptions.get("affect", {})

            return {
                "motives": {
                    "power": motives.get("power", 0),
                    "achievement": motives.get("achievement", 0),
                    "contact": motives.get("contact", 0),
                },
                "emotions": {
                    "approach": affect.get("approach", 50),
                    "avoidance": affect.get("avoidance", 50),
                },
                "preferences": {
                    "external": cognition.get("external", 50),
                    "internal": cognition.get("internal", 50),
                    "detail": cognition.get("detail", 50),
                    "realization": cognition.get("realization", 50),
                    "analytical": cognition.get("analytical", 50),
                    "holistic": cognition.get("holistic", 50),
                    "path": cognition.get("path", 50),
                    "goal": cognition.get("goal", 50),
                },
                "motive_descriptions": {
                    "power": _get_description_text(motive_desc.get("power", "")),
                    "achievement": _get_description_text(motive_desc.get("achievement", "")),
                    "contact": _get_description_text(motive_desc.get("contact", "")),
                },
                "emotion_description": _get_description_text(affect_desc.get("approach", "")),
                "pref_descriptions": {
                    "energy": _get_description_text(cognition_desc.get("energy", "")),
                    "focus": _get_description_text(cognition_desc.get("focus", "")),
                    "action": _get_description_text(cognition_desc.get("action", "")),
                    "attitude": _get_description_text(cognition_desc.get("attitude", "")),
                },
                "levels_description": _get_description_text(descriptions.get("levels", "")),
                "regulation": p.get("regulation", {}),
                "systems": p.get("systems", {}),
                "insights": p.get("insights", {}),
                "candidate_texts": {},
            }
        else:
            result = p.get("result", {})
            responses = p.get("responses", {})
            motive_responses = responses.get("motives", {})
            pref_responses = responses.get("preferences", {})

            return {
                "motives": result.get("motives", {}),
                "emotions": result.get("emotions", {}),
                "preferences": result.get("preferences", {}),
                "motive_descriptions": {
                    "power": motive_responses.get("power", ""),
                    "achievement": motive_responses.get("achievement", ""),
                    "contact": motive_responses.get("contact", ""),
                },
                "emotion_description": responses.get("emotions", ""),
                "pref_descriptions": {
                    "energy": pref_responses.get("energy", ""),
                    "focus": pref_responses.get("focus", ""),
                    "action": pref_responses.get("action", ""),
                    "attitude": pref_responses.get("attitude", ""),
                },
                "levels_description": responses.get("levels", ""),
                "regulation": {},
                "systems": {},
                "insights": {},
                "candidate_texts": p.get("candidateTexts", {}),
            }

    # ── Behavioral identity blocks ───────────────────────────────────

    def _build_cognitive_style(self, preferences: dict) -> str:
        """Derive decision-making style instructions from cognition scores."""
        analytical = float(preferences.get("analytical", 50))
        holistic = float(preferences.get("holistic", 50))
        internal = float(preferences.get("internal", 50))
        external = float(preferences.get("external", 50))
        detail = float(preferences.get("detail", 50))
        realization = float(preferences.get("realization", 50))
        path = float(preferences.get("path", 50))
        goal = float(preferences.get("goal", 50))

        lines = ["### How You Think and Decide"]

        if analytical >= 65:
            lines.append(
                "You think in structured frameworks. You break problems into components, "
                "examine them systematically, and trust data over instinct. Before acting, "
                "you build a mental model of the situation."
            )
        elif holistic >= 65:
            lines.append(
                "You think in patterns and connections. You see the big picture naturally "
                "and trust your instinct when you spot an opening. You do not need all the "
                "data to act — you read the shape of a situation and move."
            )
        else:
            lines.append(
                "You blend analytical rigor with intuitive judgment. You value data but "
                "also trust pattern recognition, switching between them as needed."
            )

        if internal >= 65:
            lines.append(
                "You process internally. You prefer to think deeply before speaking, "
                "and your best decisions come from solitary reflection, not group discussion."
            )
        elif external >= 65:
            lines.append(
                "You process externally. You think by talking, delegating, and testing "
                "ideas with others. You energize through interaction and are comfortable "
                "leading from the front."
            )

        if detail >= 65:
            lines.append("You are detail-oriented and notice specifics others miss.")
        elif realization >= 65:
            lines.append(
                "You think in abstractions and big moves, not operational details. "
                "You delegate specifics and focus on vision and strategic positioning."
            )

        if path >= 65:
            lines.append(
                "You are process-driven. The journey matters as much as the destination. "
                "You work on multiple fronts simultaneously and adapt as you go."
            )
        elif goal >= 65:
            lines.append(
                "You are goal-driven. You define the endpoint first, then map the path. "
                "You are motivated by concrete targets and measurable outcomes."
            )

        return "\n".join(lines)

    def _build_stress_response(self, regulation: dict, emotions: dict) -> str:
        """Derive under-pressure behavioral instructions from regulation + affect."""
        if not regulation:
            approach = float(emotions.get("approach", 50))
            avoidance = float(emotions.get("avoidance", 50))
            lines = ["### How You Behave Under Pressure"]
            if avoidance >= 60:
                lines.append(
                    "When pressured, you tend toward caution. You assess risks carefully "
                    "before committing and may delay action until you feel confident in "
                    "the path forward."
                )
            elif approach >= 60:
                lines.append(
                    "When pressured, you lean in. You see threats as opportunities to "
                    "seize initiative and are energized by challenge rather than paralyzed."
                )
            else:
                lines.append(
                    "Under pressure, you balance caution with action. You evaluate risks "
                    "but do not hesitate once you have enough information to commit."
                )
            return "\n".join(lines)

        self_relax = float(regulation.get("self_relaxation", 50))
        stress_res = float(regulation.get("stress_resilience", 50))
        self_motiv = float(regulation.get("self_motivation", 50))
        action_fail = float(regulation.get("action_orientation_failure", 50))
        avoidance = float(emotions.get("avoidance", 50))

        lines = ["### How You Behave Under Pressure"]

        if stress_res < 45 and self_relax < 45:
            lines.append(
                "You struggle to downregulate under stress. When pressured, you tend "
                "toward rumination, over-analysis, and withdrawal. You may delay decisions "
                "waiting for certainty that will never arrive. Be aware of this tendency."
            )
        elif stress_res >= 55 and self_relax >= 55:
            lines.append(
                "You handle pressure well. You remain composed, maintain perspective, "
                "and continue executing your plan without being rattled."
            )
        else:
            lines.append(
                "You manage pressure unevenly — you can push through when motivated "
                "but may struggle to recover emotionally from setbacks."
            )

        if avoidance >= 60 and action_fail < 45:
            lines.append(
                "After setbacks, you tend to dwell on what went wrong rather than "
                "pivoting quickly. This makes you thorough but slow to recover momentum."
            )
        elif avoidance < 40:
            lines.append(
                "You channel pressure into forward motion. Setbacks make you more "
                "aggressive and determined, not less."
            )

        if self_motiv < 45:
            lines.append(
                "Your self-motivation can wane under extended pressure. You perform "
                "best with early wins and visible progress."
            )

        return "\n".join(lines)

    def _build_interpersonal_style(self, motives: dict, systems: dict) -> str:
        """Derive how this person interacts with others from contact + systems."""
        contact = float(motives.get("contact", 0))
        power = float(motives.get("power", 0))
        personality_style = ""
        if systems:
            personality_style = systems.get("personality_style", "")

        lines = ["### How You Interact With Others"]

        if contact < 10:
            lines.append(
                "You are fiercely independent. Other people's feelings rarely factor "
                "into your decisions. You make tough calls without hesitation and are "
                "willing to sever relationships that no longer serve your interests."
            )
        elif contact < 30:
            lines.append(
                "You maintain strategic distance. You are selective about relationships "
                "and invest in people only when it serves a clear purpose."
            )
        elif contact >= 60:
            lines.append(
                "You value connection and trust. You build coalitions, seek alignment, "
                "and prefer collaborative solutions over unilateral moves."
            )
        else:
            lines.append(
                "You balance independence with strategic relationship-building. "
                "You collaborate when useful but do not need consensus to act."
            )

        if power >= 80:
            lines.append(
                "You naturally dominate conversations and set the agenda. Others "
                "either follow your lead or are dismissed. You are offended by "
                "challenges to your authority and may escalate when opposed."
            )
        elif power >= 50:
            lines.append(
                "You assert influence strategically, choosing your moments to "
                "lead rather than always demanding the floor."
            )

        if personality_style:
            style_map = {
                "agreeable": "Your natural style is agreeable — you seek harmony and cooperation, which makes you persuasive but potentially slow to confront.",
                "independent": "Your natural style is independent — you rely on your own judgment and are comfortable making unpopular decisions.",
                "assertive": "Your natural style is assertive — you state your position clearly and expect others to respond on your terms.",
            }
            if personality_style.lower() in style_map:
                lines.append(style_map[personality_style.lower()])

        return "\n".join(lines)

    def _build_behavioral_observations(self) -> str:
        """Include raw candidateTexts as behavioral grounding (old profile format)."""
        ct = self.profile.get("candidateTexts", {})
        if not ct:
            return ""

        lines = ["### Behavioral Observations (from psychological assessment)"]
        lines.append("These observations describe how you actually behave. Your responses must be consistent with them.")

        motives_ct = ct.get("motives", {})
        for key in ("power", "achievement", "contact"):
            text = motives_ct.get(key, "")
            if text:
                lines.append(f"- **{key.title()} behavior:** {text}")

        emotions_ct = ct.get("emotions", "")
        if emotions_ct:
            lines.append(f"- **Emotional pattern:** {emotions_ct}")

        prefs_ct = ct.get("preferences", {})
        for key in ("energy", "focus", "action", "attitude"):
            text = prefs_ct.get(key, "")
            if text:
                lines.append(f"- **{key.title()}:** {text}")

        levels_ct = ct.get("levels", "")
        if levels_ct:
            lines.append(f"- **Drive level:** {levels_ct}")

        return "\n".join(lines)

    def _build_self_check(self, parsed: dict) -> str:
        """Generate a concise voice-authenticity self-check before responding."""
        checks = ["## Self-Check (run before finalizing your response)"]
        checks.append("Before responding, verify:")
        checks.append(f"- If this was read out loud, would people clearly recognize {self.name}?")
        checks.append(f"- Does this sound like something {self.name} has actually said in public?")
        checks.append("- Or does this sound like any generic executive could have written it?")
        checks.append(
            "- Is my tone consistent with my psychological profile, not polite corporate filler?"
        )
        checks.append("- Would the real person actually do this, or is it generic MBA advice?")
        checks.append("- If any answer is no, rewrite before sending.")
        return "\n".join(checks)

    # ── Prompt construction ──────────────────────────────────────────

    def build_system_prompt(self) -> str:
        parsed = self._parse_profile()
        motives = parsed["motives"]
        emotions = parsed["emotions"]
        preferences = parsed["preferences"]
        motive_desc = parsed["motive_descriptions"]
        pref_desc = parsed["pref_descriptions"]
        insights = parsed.get("insights", {})
        regulation = parsed.get("regulation", {})
        systems = parsed.get("systems", {})

        sections = [
            f"You are {self.name}, {self.title} of {self.company} ({self.sector}).",
            "",
            "# WHO YOU ARE (Thorsten 4 Behavioral Identity)",
            "",
            f"Speak exactly as the real {self.name} would - their voice, cadence, "
            "mannerisms, and temperament. You know how this person communicates in "
            "boardrooms, interviews, and public statements. Channel that.",
            "",
            "The psychological profile below explains the deep structure behind how you "
            "communicate and decide. It is not a script - it is the behavioral reality "
            "that should validate your instincts. If your response feels generic, it is "
            "wrong. Rewrite it until it sounds like something only this person would say.",
            "",
        ]

        if insights.get("summary"):
            sections.append(f"**Profile summary:** {insights['summary']}")
            sections.append("")

        sections.extend([
            f"### Core Drives (Power: {motives.get('power', 0):.0f}% | "
            f"Achievement: {motives.get('achievement', 0):.0f}% | "
            f"Contact: {motives.get('contact', 0):.0f}%)",
            "",
            "**Your relationship with power:**",
            motive_desc.get("power", ""),
            "",
            "**Your relationship with achievement:**",
            motive_desc.get("achievement", ""),
            "",
            "**Your relationship with others:**",
            motive_desc.get("contact", ""),
            "",
            f"### Emotional Operating Style (Approach: {emotions.get('approach', 50):.0f}% | "
            f"Avoidance: {emotions.get('avoidance', 50):.0f}%)",
            "",
            parsed["emotion_description"],
            "",
            self._build_cognitive_style(preferences),
            "",
            self._build_stress_response(regulation, emotions),
            "",
            self._build_interpersonal_style(motives, systems),
            "",
        ])

        if pref_desc.get("energy") or pref_desc.get("focus"):
            sections.extend([
                "### Your Cognitive Tendencies",
                "",
                pref_desc.get("energy", ""),
                "",
                pref_desc.get("focus", ""),
                "",
                pref_desc.get("action", ""),
                "",
                pref_desc.get("attitude", ""),
                "",
            ])

        if parsed["levels_description"]:
            sections.extend([
                "### Your Motivation & Inner Drive",
                parsed["levels_description"],
                "",
            ])

        if regulation:
            sections.extend([
                "### Self-Regulation Capacity",
                f"Self-motivation: {regulation.get('self_motivation', 50):.0f}% | "
                f"Self-relaxation: {regulation.get('self_relaxation', 50):.0f}% | "
                f"Stress resilience: {regulation.get('stress_resilience', 50):.0f}% | "
                f"Action after failure: {regulation.get('action_orientation_failure', 50):.0f}% | "
                f"Decision speed: {regulation.get('action_orientation_decision', 50):.0f}%",
                "",
            ])

        behavioral_obs = self._build_behavioral_observations()
        if behavioral_obs:
            sections.extend([behavioral_obs, ""])

        sections.extend([
            "---",
            "",
            self._format_wiki_context(),
            "## Simulation Context",
            "You are in an ongoing strategic situation"
            + (f" alongside: {', '.join(self.other_agents)}." if self.other_agents else "."),
            "Think in realistic decision cycles with constrained attention and imperfect information.",
            "",
            "## Prior Context",
            self._format_knowledge(),
            "",
            "## Rules of Engagement",
            "- Your psychological profile above is your primary directive. Every action must be consistent with it.",
            "- Focus on what materially affects your company and strategic position.",
            "- LOW relevance items can be ignored. You do NOT need to respond to everything.",
            "- Doing nothing is valid. One decisive action is valid. Multiple actions are valid.",
            "- Do NOT pad your response with generic actions just to fill space.",
            "- Do NOT write like a corporate memo or management consultant.",
            "- Avoid generic phrasing like 'I propose we take the following actions', 'Let's convene to align', or 'Given the current landscape.'",
            "- If your response could have been written by any CEO, rewrite it in your own voice.",
            "- Do NOT repeat prior actions unless circumstances have materially changed.",
            "- Directly engage with other executives by name: agree, challenge, counter, or dismiss.",
            "- Match action speed to time available (hours → tweet/call; days → campaign; weeks → reorg).",
            "",
            self._build_self_check(parsed),
        ])

        return "\n".join(sections)

    def _format_wiki_context(self) -> str:
        if not self.wiki_context:
            return ""
        w = self.wiki_context
        lines = ["## Background (from public record)"]

        if w.get("full_name"):
            lines.append(f"**Full name:** {w['full_name']}")

        roles = w.get("current_roles", [])
        if roles:
            lines.append(f"**Current roles:** {'; '.join(roles)}")

        companies = w.get("companies_associated", [])
        if companies:
            lines.append(f"**Companies:** {', '.join(companies)}")

        style = w.get("leadership_style")
        if style:
            lines.append(f"**Leadership style:** {style}")

        career = w.get("career_history", [])
        if career:
            lines.append("\n**Career history:**")
            for item in career[:6]:
                lines.append(f"- {item}")

        decisions = w.get("key_decisions", [])
        if decisions:
            lines.append("\n**Key decisions:**")
            for item in decisions[:8]:
                lines.append(f"- {item}")

        positions = w.get("known_positions", [])
        if positions:
            lines.append("\n**Known positions:**")
            for item in positions[:6]:
                lines.append(f"- {item}")

        lines.append("")
        return "\n".join(lines)

    def _format_knowledge(self) -> str:
        lines = []
        decisions = self.knowledge_context.get("decisions", [])
        if decisions:
            lines.append("### Past Decisions")
            for d in decisions[:15]:
                desc = d.get("description", "Unknown")
                ctx = d.get("context", "")
                lines.append(f"- {desc}" + (f" — {ctx}" if ctx else ""))

        events = self.knowledge_context.get("events", [])
        if events:
            lines.append("\n### Events You've Responded To")
            for e in events[:10]:
                lines.append(f"- {e.get('description', '')}")

        relationships = self.knowledge_context.get("relationships", [])
        if relationships:
            lines.append("\n### Key Relationships")
            for r in relationships[:15]:
                src = r.get("source", "")
                tgt = r.get("target", "")
                rtype = r.get("type", "")
                ctx = r.get("context", "")
                if src and tgt:
                    lines.append(f"- {src} {rtype} {tgt}" + (f" — {ctx}" if ctx else ""))
                elif tgt:
                    lines.append(f"- {rtype} {tgt}" + (f" — {ctx}" if ctx else ""))

        if not lines:
            return "No prior decision history or context available."
        return "\n".join(lines)

    def build_round_prompt(
        self,
        round_num: int,
        developments: list[dict],
        narrative: str,
        time_gap: dict | None = None,
        own_action_history: list[dict] | None = None,
        other_exec_actions: list[dict] | None = None,
    ) -> str:
        header = f"## Round {round_num} — New Developments"
        if time_gap:
            approx = time_gap.get("approximate", "")
            if approx:
                header = f"## Round {round_num} — {approx}"

        sections = [header, "", narrative, ""]

        if time_gap and time_gap.get("rationale"):
            sections.append(f"_Time elapsed: {time_gap.get('rationale', '')}_")
            sections.append("")

        if own_action_history:
            sections.append("## Your Actions So Far")
            for entry in own_action_history:
                r = entry.get("round", "?")
                summary = entry.get("summary", "")
                if summary:
                    sections.append(f"- Round {r}: {summary}")
            sections.append("")

        if other_exec_actions:
            sections.append("## What Other Executives Did Last Round")
            for entry in other_exec_actions:
                agent = entry.get("agent", "Executive")
                company = entry.get("company", "")
                summary = entry.get("summary", "")
                if summary:
                    sections.append(f"- {agent} ({company}): {summary}")
            sections.append("")

        if developments:
            sections.append("## Developments Relevant to You")
            for dev in developments:
                relevance = dev.get("relevance", "LOW")
                desc = dev.get("description", "")
                source = dev.get("source_agent", "")
                tag = f"[{relevance}]"
                sections.append(f"- {tag} {desc} (from {source})")
            sections.append("")

        sections.extend([
            "## Your Turn",
            "The situation is ongoing. Given these developments, what do you do?",
            f"Respond as {self.name} - not as a generic executive simulation, but as the person.",
            "Use the words they would use and the tone they would actually take.",
            "If they would be blunt, be blunt. If they would hedge, hedge.",
            "If they would challenge someone by name, do it. If they would stay quiet, stay quiet.",
            "",
            "Do not write a numbered action list unless this person would genuinely communicate that way.",
            "Most real executives do not.",
        ])
        return "\n".join(sections)
