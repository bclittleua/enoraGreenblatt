from __future__ import annotations
from typing import Dict, List, Optional, Tuple
from FASEcfg import *
from FASEclass import *

class CombatMixin:

    def _action_registry(self):
        world = self.world
        tick = int(getattr(world, "tick", 0))
        if int(getattr(world, "_action_registry_tick", -999999)) != tick:
            world._action_registry_tick = tick
            world._action_registry = set()
        registry = getattr(world, "_action_registry", None)
        if registry is None:
            registry = set()
            world._action_registry = registry
        return registry

    def _action_key(self, kind: str, ident) -> tuple:
        return (str(kind), ident)

    def _actor_action_key(self, actor: Optional[Actor]):
        return None if actor is None else self._action_key("actor", getattr(actor, "id", None))

    def _party_action_key(self, party):
        return None if party is None else self._action_key("party", getattr(party, "id", None))

    def _monster_action_key(self, monster):
        return None if monster is None else self._action_key("monster", getattr(monster, "id", None))

    def _military_action_key(self, party):
        if party is None or getattr(party, "goal", "") != "military":
            return None
        return self._action_key("military", (getattr(party, "parent_polity_id", None), getattr(party, "formation_index", getattr(party, "id", None))))

    def _action_used(self, key) -> bool:
        if key is None:
            return False
        return key in self._action_registry()

    def _mark_action_used(self, key) -> None:
        if key is not None:
            self._action_registry().add(key)

    def _party_or_actor_has_acted(self, actor: Optional[Actor]) -> bool:
        if actor is None:
            return False
        if self._action_used(self._actor_action_key(actor)):
            return True
        party = self.world.get_party(actor)
        return self._action_used(self._party_action_key(party)) or self._action_used(self._military_action_key(party))

    def _mark_actor_action(self, actor: Optional[Actor]) -> None:
        if actor is None:
            return
        self._mark_action_used(self._actor_action_key(actor))
        party = self.world.get_party(actor)
        self._mark_action_used(self._party_action_key(party))
        self._mark_action_used(self._military_action_key(party))

    def _side_has_acted(self, side: List[Actor]) -> bool:
        for actor in side or []:
            if self._party_or_actor_has_acted(actor):
                return True
        return False

    def _mark_side_action(self, side: List[Actor]) -> None:
        for actor in side or []:
            self._mark_actor_action(actor)

    def _unique_living_side(self, side: List[Actor]) -> List[Actor]:
        unique: List[Actor] = []
        seen = set()
        for actor in side or []:
            if actor is None or not getattr(actor, "alive", False) or getattr(actor, "withdrawn", False):
                continue
            if actor.id in seen:
                continue
            seen.add(actor.id)
            unique.append(actor)
        return unique

    def _side_id_set(self, side: List[Actor]) -> set[int]:
        return {actor.id for actor in self._unique_living_side(side)}

    def _combat_sides_overlap(self, a_side: List[Actor], b_side: List[Actor]) -> bool:
        return bool(self._side_id_set(a_side).intersection(self._side_id_set(b_side)))

    def _actor_state_id(self, actor: Optional[Actor]) -> Optional[int]:
        if actor is None:
            return None
        enlisted = getattr(actor, "enlisted_polity_id", None)
        if enlisted is not None:
            return enlisted
        return getattr(actor, "polity_id", None)

    def _party_state_id(self, actor: Optional[Actor]) -> Optional[int]:
        if actor is None:
            return None
        party = self.world.get_party(actor)
        if party is None:
            return None
        if getattr(party, "goal", "") == "military":
            return getattr(party, "parent_polity_id", None)
        return None

    def _shared_state_id(self, a: Optional[Actor], b: Optional[Actor]) -> Optional[int]:
        if a is None or b is None:
            return None
        a_ids = {x for x in (self._actor_state_id(a), self._party_state_id(a)) if x is not None}
        b_ids = {x for x in (self._actor_state_id(b), self._party_state_id(b)) if x is not None}
        shared = a_ids.intersection(b_ids)
        if not shared:
            return None
        return next(iter(shared))

    def _state_loyalty_blocks_internal_fight(self, attacker: Actor, defender: Actor) -> bool:
        if self._shared_state_id(attacker, defender) is None:
            return False
        threshold = int(globals().get("INTERNAL_STATE_LOYALTY_BLOCK_THRESHOLD", 55))
        return (
            int(getattr(attacker, "state_loyalty", 50) or 50) >= threshold
            and int(getattr(defender, "state_loyalty", 50) or 50) >= threshold
        )

    def _internal_state_duel_allowed(self, attacker: Actor, defender: Actor) -> bool:
        if self._shared_state_id(attacker, defender) is None:
            return False
        if self._state_loyalty_blocks_internal_fight(attacker, defender):
            return False
        threshold = int(globals().get("INTERNAL_STATE_LOYALTY_DUEL_THRESHOLD", 55))
        return (
            int(getattr(attacker, "state_loyalty", 50) or 50) < threshold
            or int(getattr(defender, "state_loyalty", 50) or 50) < threshold
        )

    def _military_same_state_collision(self, attacker: Actor, defender: Actor) -> bool:
        shared = self._shared_state_id(attacker, defender)
        if shared is None:
            return False
        a_party = self.world.get_party(attacker)
        b_party = self.world.get_party(defender)
        return (
            a_party is not None
            and b_party is not None
            and getattr(a_party, "goal", "") == "military"
            and getattr(b_party, "goal", "") == "military"
            and getattr(a_party, "parent_polity_id", None) == shared
            and getattr(b_party, "parent_polity_id", None) == shared
        )

    def _valid_combat_pair(self, attacker: Optional[Actor], defender: Optional[Actor]) -> bool:
        if attacker is None or defender is None:
            return False
        if not getattr(attacker, "alive", False) or not getattr(defender, "alive", False):
            return False
        if getattr(attacker, "id", None) == getattr(defender, "id", None):
            return False
        if self._party_or_actor_has_acted(attacker) or self._party_or_actor_has_acted(defender):
            return False
        if self._state_loyalty_blocks_internal_fight(attacker, defender):
            return False
        if self._shared_state_id(attacker, defender) is not None:
            return self._internal_state_duel_allowed(attacker, defender)
        return not self._combat_sides_overlap(self.world.side_members(attacker), self.world.side_members(defender))

    def _representative_opponent(self, side: List[Actor], fallback: Actor) -> Actor:
        living = self._unique_living_side(side)
        if not living:
            return fallback
        return max(living, key=lambda a: (getattr(a, "reputation", 0), getattr(a, "level", 1), a.power_rating()))

    def _bard_is_protected(self, actor: Actor, side: List[Actor]) -> bool:
        if actor.role != Role.BARD or not actor.alive:
            return False
        return any(
            other.alive and other.id != actor.id and other.role in (Role.FIGHTER, Role.WARDEN, Role.WIZARD)
            for other in side
        )

    def _find_enemy_target(self, actor: Actor) -> Optional[Actor]:
        world = self.world
        actor_side = world.side_members(actor)

        def valid_target(other: Optional[Actor]) -> bool:
            if other is None or not getattr(other, "alive", False):
                return False
            if other.id == actor.id or getattr(other, "region_id", None) != actor.region_id:
                return False
            if getattr(other, "combat_cooldown", 0) > 0:
                return False
            if self._party_or_actor_has_acted(actor) or self._party_or_actor_has_acted(other):
                return False
            if self._combat_sides_overlap(actor_side, world.side_members(other)):
                return False
            return True

        local = [other for other in world.actors_in_region(actor.region_id) if valid_target(other)]
        enemies = [
            other for other in local
            if actor.attitude_toward(other) == "oppose"
            and not self._state_loyalty_blocks_internal_fight(actor, other)
        ]
        if hasattr(self, "_stolen_created_relic_holder_target"):
            stolen_holder = self._stolen_created_relic_holder_target(actor)
            if valid_target(stolen_holder):
                return stolen_holder
        if not enemies:
            return None
        unprotected = []
        for other in enemies:
            side = world.side_members(other)
            if not self._bard_is_protected(other, side):
                unprotected.append(other)
        if unprotected:
            enemies = unprotected
        solo_or_party_enemies = []
        seen = set()
        for enemy in enemies:
            party = world.get_party(enemy)
            key = (party.id if party else -enemy.id)
            if key not in seen:
                seen.add(key)
                solo_or_party_enemies.append(enemy)
        return self.rng.choice(solo_or_party_enemies) if solo_or_party_enemies else None


    def _should_attack(self, actor: Actor, target: Actor) -> bool:
        if not self._valid_combat_pair(actor, target):
            return False
        world = self.world
        if self._shared_state_id(actor, target) is not None:
            own_power = actor.power_rating()
            enemy_power = target.power_rating()
            own_mind = actor.mind_score()
        else:
            own_power = world.side_power(actor)
            enemy_power = world.side_power(target)
            own_mind = world.side_mind(actor)
        if enemy_power <= 0:
            return False
        if own_power >= enemy_power:
            return True
        desperate_ratio = own_power / enemy_power
        if own_mind < 14 and desperate_ratio >= 0.75:
            return True
        if own_mind < 10 and desperate_ratio >= 0.55:
            return True
        if own_mind < 8:
            return True
        return False


    def _should_retreat(self, actor: Actor, target: Actor) -> bool:
        if not self._valid_combat_pair(actor, target):
            return False
        world = self.world
        if self._shared_state_id(actor, target) is not None:
            own_power = actor.power_rating()
            enemy_power = target.power_rating()
            own_mind = actor.mind_score()
        else:
            own_power = world.side_power(actor)
            enemy_power = world.side_power(target)
            own_mind = world.side_mind(actor)
        if enemy_power <= own_power:
            return False
        if own_mind < 8:
            return False
        return own_power / enemy_power < 0.85


    def _grant_title(self, actor: Actor, title: str) -> None:
        current = getattr(actor, "title", None)
        if current is None or str(current).startswith("First in Class of "):
            actor.title = title



    def _award_actor_battle_xp(self, winner: Actor, representative_victim: Actor, casualties: int) -> None:
        if casualties <= 0 or winner is None or representative_victim is None:
            return
        base = 50 * casualties
        try:
            scale = representative_victim.power_rating() / max(1, winner.power_rating())
        except Exception:
            scale = 1.0
        xp_gain = max(10 * casualties, int(base * max(0.5, min(2.5, scale))))
        if hasattr(winner, "gain_experience"):
            winner.gain_experience(xp_gain)
        else:
            winner.experience = getattr(winner, "experience", 0) + xp_gain
        try:
            self._change_actor_rep(winner, xp_gain // XP_TO_REP_DIVISOR)
        except Exception:
            winner.reputation += xp_gain // XP_TO_REP_DIVISOR

    def _spend_action(self, actor: Actor) -> None:
        self._mark_actor_action(actor)
        actor.actions_remaining = max(0, getattr(actor, "actions_remaining", ACTIONS_PER_TICK) - 1)
        self._apply_fatigue(actor, self._fatigue_cost_for_actor(actor))


    def _apply_combat_cooldown(self, side: List[Actor], ticks: Optional[int] = None) -> None:
        if ticks is None:
            ticks = COMBAT_COOLDOWN_TICKS
        for actor in side:
            if not actor.alive:
                continue
            actor.combat_cooldown = max(getattr(actor, "combat_cooldown", 0), ticks)
            actor.actions_remaining = 0


    def _side_levy_bonus(self, side: List[Actor]) -> int:
        if not side:
            return 0
        world = self.world
        party_ids = {getattr(actor, "party_id", None) for actor in side if getattr(actor, "party_id", None) is not None}
        bonus = 0
        divisor = max(1, int(globals().get("MILITARY_LEVY_POWER_DIVISOR", 40)))
        for pid in party_ids:
            party = world.parties.get(pid)
            if party is None or getattr(party, "goal", "") != "military":
                continue
            bonus += max(0, int(getattr(party, "levy_strength", 0) or 0)) // divisor
        return bonus


    def _apply_levy_battle_losses(self, side: List[Actor], won: bool) -> None:
        if not side:
            return
        world = self.world
        party_ids = {getattr(actor, "party_id", None) for actor in side if getattr(actor, "party_id", None) is not None}
        rate = float(globals().get("MILITARY_LEVY_LOSS_RATE_WIN", 0.03)) if won else float(globals().get("MILITARY_LEVY_LOSS_RATE_LOSS", 0.08))
        for pid in party_ids:
            party = world.parties.get(pid)
            if party is None or getattr(party, "goal", "") != "military":
                continue
            levy = max(0, int(getattr(party, "levy_strength", 0) or 0))
            if levy <= 0:
                continue
            loss = min(levy, max(0, int(levy * rate)))
            party.levy_strength = levy - loss
            pol = world.polities.get(getattr(party, "parent_polity_id", None))
            if pol is not None:
                pol.levy_strength = max(0, int(getattr(pol, "levy_strength", 0) or 0) - loss)
                pol.levy_mobilized = max(0, int(getattr(pol, "levy_mobilized", 0) or 0) - loss)


    def _record_military_battle_result(self, winners: List[Actor], losers: List[Actor]) -> None:
        world = self.world
        win_polities = {getattr(a, "polity_id", None) for a in winners if getattr(a, "polity_id", None) is not None}
        lose_polities = {getattr(a, "polity_id", None) for a in losers if getattr(a, "polity_id", None) is not None}
        for actor in winners:
            if getattr(actor, "enlisted_polity_id", None) in win_polities or getattr(actor, "military_rank", None):
                actor.military_successes = int(getattr(actor, "military_successes", 0) or 0) + 1
                actor.state_loyalty = min(100, int(getattr(actor, "state_loyalty", 50) or 50) + int(globals().get("MILITARY_SERVICE_LOYALTY_GAIN_ON_VICTORY", 2)))
                actor.polity_favor = min(100, int(getattr(actor, "polity_favor", 50) or 50) + int(globals().get("MILITARY_SERVICE_FAVOR_GAIN_ON_VICTORY", 2)))
        for actor in losers:
            if getattr(actor, "enlisted_polity_id", None) in lose_polities or getattr(actor, "military_rank", None):
                actor.military_failures = int(getattr(actor, "military_failures", 0) or 0) + 1
                actor.state_loyalty = max(-100, int(getattr(actor, "state_loyalty", 50) or 50) - int(globals().get("MILITARY_SERVICE_LOYALTY_LOSS_ON_DEFEAT", 2)))
                actor.polity_favor = max(-100, int(getattr(actor, "polity_favor", 50) or 50) - int(globals().get("MILITARY_SERVICE_FAVOR_LOSS_ON_DEFEAT", 2)))
                if int(getattr(actor, "military_failures", 0) or 0) >= int(globals().get("MILITARY_RONIN_DEFEAT_THRESHOLD", 3)) and int(getattr(actor, "military_failures", 0) or 0) > int(getattr(actor, "military_successes", 0) or 0):
                    actor.ronin_veteran = True
                if hasattr(self, "_maybe_withdraw_from_active_life"):
                    self._maybe_withdraw_from_active_life(actor, reason="war-weariness")


    def _resolve_battle(self, attacker: Actor, defender: Actor) -> None:
        world = self.world
        if attacker is None or defender is None or attacker.id == defender.id:
            return
        if self._state_loyalty_blocks_internal_fight(attacker, defender):
            return
        internal_duel = self._internal_state_duel_allowed(attacker, defender)
        if internal_duel:
            attackers = self._unique_living_side([attacker])
            defenders = self._unique_living_side([defender])
        else:
            attackers = self._unique_living_side(world.side_members(attacker))
            defenders = self._unique_living_side(world.side_members(defender))
        if not attackers or not defenders:
            return
        if self._side_has_acted(attackers) or self._side_has_acted(defenders):
            return
        if not internal_duel and self._combat_sides_overlap(attackers, defenders):
            # Party membership can become stale after coups, routs, dissolves,
            # or long-running save migrations. Normalize once and retry; if
            # the sides still overlap, it is not a valid battle.
            world.cleanup_parties()
            attackers = self._unique_living_side(world.side_members(attacker))
            defenders = self._unique_living_side(world.side_members(defender))
            if not attackers or not defenders or self._combat_sides_overlap(attackers, defenders):
                return
            if self._side_has_acted(attackers) or self._side_has_acted(defenders):
                return
        self._mark_side_action(attackers)
        self._mark_side_action(defenders)
        attacker_rep = self._representative_opponent(attackers, attacker)
        defender_rep = self._representative_opponent(defenders, defender)
        self._polity_side_penalty(attackers)
        self._polity_side_penalty(defenders)
        attack_power = sum(member.power_rating() for member in attackers) + (0 if internal_duel else self._side_levy_bonus(attackers))
        defend_power = sum(member.power_rating() for member in defenders) + (0 if internal_duel else self._side_levy_bonus(defenders))
        attack_roll = attack_power + self.rng.randint(1, 8) + max(0, attacker_rep.luck - 10) // 3
        defend_roll = defend_power + self.rng.randint(1, 8) + max(0, defender_rep.luck - 10) // 3
        attack_roll += self._bard_side_bonus(attackers)
        defend_roll += self._bard_side_bonus(defenders)
        if any(member.role == Role.FIGHTER for member in attackers):
            attack_roll += 1
        if any(member.role == Role.FIGHTER for member in defenders):
            defend_roll += 1
        if attacker_rep.role == Role.WIZARD:
            attack_roll += 2
        if defender_rep.role == Role.WIZARD:
            defend_roll += 2
        if internal_duel:
            atk_names = attacker.short_name()
            def_names = defender.short_name()
        else:
            atk_names = self._format_side_names(attackers)
            def_names = self._format_side_names(defenders)
        region_name = world.region_name(attacker.region_id)
        if attack_roll >= defend_roll:
            casualties = self._apply_losses(defenders, severity=0.22, killer_id=attacker_rep.id, cause=f"slain in battle against {attacker_rep.short_name()}")
            routed = self._apply_rout(defenders)
            self._apply_wounds(attackers, severity=0.10)
            for winner in attackers:
                winner.kills += casualties
                if casualties:
                    self._award_actor_battle_xp(winner, defender_rep, casualties)
                if casualties and hasattr(winner, 'kill_log'):
                    winner.kill_log.append(f"{casualties} battle casualty{'ies' if casualties != 1 else ''}")
                winner.reputation += 1
            self._apply_combat_cooldown(attackers)
            self._apply_combat_cooldown(defenders)
            for member in attackers:
                self._apply_fatigue(member, 3)
            for member in defenders:
                if member.alive:
                    self._apply_fatigue(member, 4)
            self._post_battle_rest(attackers, routed=False, legendary=False)
            self._post_battle_rest(defenders, routed=True, legendary=False)
            world.log(f"In {region_name}, {atk_names} defeated {def_names}, leaving {casualties} dead and {routed} routed.", importance=3, category="battle")
            self._log_champion_battle_credit(attackers, defenders, casualties, routed, region_name, repelled=False)
            if not internal_duel:
                self._record_military_battle_result(attackers, defenders)
                self._apply_levy_battle_losses(attackers, won=True)
                self._apply_levy_battle_losses(defenders, won=False)
            if not internal_duel:
                control_shift = 2 if any(a.is_good() for a in attackers) else -2 if any(a.is_evil() for a in attackers) else 0
                world.adjust_region_state(attacker.region_id, control_delta=control_shift, order_delta=-1)
        else:
            casualties = self._apply_losses(attackers, severity=0.22, killer_id=defender_rep.id, cause=f"slain in battle against {defender_rep.short_name()}")
            routed = self._apply_rout(attackers)
            self._apply_wounds(defenders, severity=0.10)
            for winner in defenders:
                winner.kills += casualties
                if casualties:
                    self._award_actor_battle_xp(winner, attacker_rep, casualties)
                if casualties and hasattr(winner, 'kill_log'):
                    winner.kill_log.append(f"{casualties} battle casualty{'ies' if casualties != 1 else ''}")
                winner.reputation += 1
            self._apply_combat_cooldown(attackers)
            self._apply_combat_cooldown(defenders)
            for member in attackers:
                if member.alive:
                    self._apply_fatigue(member, 4)
            for member in defenders:
                self._apply_fatigue(member, 3)
            self._post_battle_rest(attackers, routed=True, legendary=False)
            self._post_battle_rest(defenders, routed=False, legendary=False)
            world.log(f"In {region_name}, {atk_names} attacked {def_names} and were repelled, losing {casualties} dead and {routed} routed.", importance=3, category="battle")
            self._log_champion_battle_credit(defenders, attackers, casualties, routed, region_name, repelled=True)
            if not internal_duel:
                self._record_military_battle_result(defenders, attackers)
                self._apply_levy_battle_losses(defenders, won=True)
                self._apply_levy_battle_losses(attackers, won=False)
            if not internal_duel:
                control_shift = 2 if any(d.is_good() for d in defenders) else -2 if any(d.is_evil() for d in defenders) else 0
                world.adjust_region_state(attacker.region_id, control_delta=control_shift, order_delta=-1)
        self._update_post_battle_relationships(attackers, defenders)
        world.cleanup_parties()


    def _apply_losses(self, side: List[Actor], severity: float, killer_id: Optional[int] = None, cause: str = "battle wounds") -> int:
        deaths = 0
        for actor in side:
            if not actor.alive:
                continue
            if self._bard_is_protected(actor, side):
                continue
            lethal_chance = severity
            if actor.role == Role.FIGHTER:
                lethal_chance -= 0.05
            elif actor.role == Role.WIZARD:
                lethal_chance += 0.02
            elif actor.role == Role.COMMONER:
                lethal_chance += 0.08
            lethal_chance -= max(0, actor.luck - 10) * 0.005
            lethal_chance = max(0.03, min(0.50, lethal_chance))
            if self.rng.random() < lethal_chance:
                if killer_id == actor.id:
                    actor.death_killer_id = None
                    self._mark_actor_dead(actor, "battle wounds")
                else:
                    actor.death_killer_id = killer_id
                    self._mark_actor_dead(actor, cause)
                deaths += 1
                continue
            actor.hp = max(1, actor.hp - self.rng.randint(1, max(2, actor.max_hp // 3)))
            actor.recovering = max(actor.recovering, self.rng.randint(2, 5))
        return deaths


    def _apply_rout(self, side: List[Actor]) -> int:
        routed = 0
        bard_bonus = self._bard_side_support(side)
        for actor in side:
            if not actor.alive:
                continue
            actor.recovering = max(actor.recovering, self.rng.randint(2, 5))
            if actor.party_id is not None and self.rng.random() < max(0.10, 0.45 - bard_bonus):
                self.world.remove_from_party(actor)
            if self.rng.random() < max(0.20, 0.70 - bard_bonus):
                region = self.world.regions[actor.region_id]
                if region.neighbors:
                    self.world.move_actor(actor, self.rng.choice(region.neighbors)) if hasattr(self.world, "move_actor") else setattr(actor, "region_id", self.rng.choice(region.neighbors))
                    routed += 1
        return routed


    def _apply_wounds(self, side: List[Actor], severity: float) -> None:
        for actor in side:
            if not actor.alive:
                continue
            if self._bard_is_protected(actor, side):
                continue
            if self.rng.random() < severity:
                actor.hp = max(1, actor.hp - self.rng.randint(1, max(2, actor.max_hp // 4)))
                actor.recovering = max(actor.recovering, self.rng.randint(1, 3))


    def _rest_or_retreat(self, actor: Actor) -> None:
        if actor.recovering > 2:
            self._take_long_rest(actor)
            return
        if actor.recovering > 0:
            self._take_short_rest(actor)
            if self.rng.random() < 0.40:
                self._retreat(actor, reason="they need time to recover")


    def _retreat(self, actor: Actor, reason: str) -> None:
        world = self.world
        party = world.get_party(actor)
        region = world.regions[actor.region_id]
        if not region.neighbors:
            return
        target_region_id = None
        if actor.polity_id is not None and actor.polity_id in world.polities:
            polity = world.polities[actor.polity_id]
            border = [rid for rid in region.neighbors if rid in polity.region_ids]
            enemy = [rid for rid in region.neighbors if world.regions[rid].polity_id not in (None, polity.id)]
            unclaimed = [rid for rid in region.neighbors if world.regions[rid].polity_id is None]
            if actor.is_good() and enemy:
                target_region_id = self.rng.choice(enemy)
            elif actor.is_evil() and (enemy or unclaimed):
                target_region_id = self.rng.choice(enemy or unclaimed)
            elif border:
                target_region_id = self.rng.choice(border)
        if target_region_id is None and actor.relic_id is None:
            relic_neighbors = [rid for rid in region.neighbors if self._local_unclaimed_relics(rid)]
            if relic_neighbors:
                target_region_id = self.rng.choice(relic_neighbors)
        if target_region_id is None:
            target_region_id = self.rng.choice(region.neighbors)
        if party is not None:
            for member_id in party.member_ids:
                member = world.actors[member_id]
                if member.alive:
                    world.move_actor(member, target_region_id) if hasattr(world, "move_actor") else setattr(member, "region_id", target_region_id)
                    member.recovering = max(member.recovering, 1)
            self._spend_action(actor)
            if self.rng.random() < 0.30:
                world.log(f"{self._format_side_names([world.actors[mid] for mid in party.member_ids if mid in world.actors and world.actors[mid].alive])} withdraw to {world.region_name(target_region_id)} because {reason}.", importance=2, category="retreat")
        else:
            world.move_actor(actor, target_region_id) if hasattr(world, "move_actor") else setattr(actor, "region_id", target_region_id)
            actor.recovering = max(actor.recovering, 1)
            self._spend_action(actor)
            if self.rng.random() < 0.15:
                world.log(f"{actor.short_name()} retreats to {world.region_name(target_region_id)} because {reason}.", importance=1, category="retreat")


    def _protect_commoners(self, actor: Actor) -> bool:
        world = self.world
        local = world.actors_in_region(actor.region_id)
        villains = [other for other in local if other.alive and other.is_adventurer() and other.is_evil()]
        commoners = [other for other in local if other.alive and other.role == Role.COMMONER]
        if not villains or not commoners:
            return False
        target = self.rng.choice(villains)
        if self._should_attack(actor, target):
            world.log(f"{actor.short_name()} moves to defend the common folk of {world.region_name(actor.region_id)}.", importance=2, category="defense")
            self._spend_action(actor)
            world.adjust_region_state(actor.region_id, control_delta=3 if actor.role == Role.FIGHTER else 2, order_delta=2 if actor.role == Role.FIGHTER else 1)
            actor.protects_region = actor.region_id
            actor.regions_defended += 2 if actor.role == Role.FIGHTER else 1
            self._grant_title(actor, f"Defender of {world.region_name(actor.region_id)}")
            self._resolve_battle(actor, target)
            return True
        if self._should_retreat(actor, target):
            self._retreat(actor, reason="the local villains are too strong to face openly")
            return True
        return False


    def _oppress_commoners(self, actor: Actor) -> bool:
        world = self.world
        local = world.actors_in_region(actor.region_id)
        commoners = [other for other in local if other.alive and other.role == Role.COMMONER]
        protectors = [other for other in local if other.alive and other.is_adventurer() and other.is_good()]
        if protectors:
            target = self.rng.choice(protectors)
            if self._should_attack(actor, target):
                world.log(f"{actor.short_name()} tries to break resistance in {world.region_name(actor.region_id)}.", importance=2, category="oppression")
                self._spend_action(actor)
                world.adjust_region_state(actor.region_id, control_delta=-2, order_delta=-1)
                actor.regions_oppressed += 1
                self._resolve_battle(actor, target)
                return True
            if self._should_retreat(actor, target):
                self._retreat(actor, reason="local defenders are stronger than expected")
                return True
            return False
        if commoners and self.rng.random() < 0.35:
            victims = self.rng.sample(commoners, k=min(len(commoners), self.rng.randint(1, 3)))
            deaths = 0
            for victim in victims:
                if self.rng.random() < 0.06:
                    self._mark_actor_dead(victim, f"oppression by {actor.short_name()}")
                    deaths += 1
                else:
                    victim.recovering = max(victim.recovering, self.rng.randint(1, 3))
            actor.reputation += 1
            actor.regions_oppressed += 1
            if deaths > 0:
                world.log(f"{actor.short_name()} terrorizes commoners in {world.region_name(actor.region_id)}, leaving {deaths} dead.", importance=2, category="oppression")
            else:
                world.log(f"{actor.short_name()} cowes the commoners of {world.region_name(actor.region_id)} into fearful obedience.", importance=2, category="oppression")
            world.adjust_region_state(actor.region_id, control_delta=-4, order_delta=-2)
            self._spend_action(actor)
            return True
        return False


    def _quest_move(self, actor: Actor) -> None:
        world = self.world
        party = world.get_party(actor)
        if party is not None and party.leader_id is not None and party.leader_id != actor.id:
            leader = world.actors[party.leader_id]
            world.move_actor(actor, leader.region_id) if hasattr(world, "move_actor") else setattr(actor, "region_id", leader.region_id)
            return
        region = world.regions[actor.region_id]
        if not region.neighbors:
            return
        target_region_id = None
        if actor.polity_id is not None and actor.polity_id in world.polities:
            polity = world.polities[actor.polity_id]
            border = [rid for rid in region.neighbors if rid in polity.region_ids]
            enemy = [rid for rid in region.neighbors if world.regions[rid].polity_id not in (None, polity.id)]
            unclaimed = [rid for rid in region.neighbors if world.regions[rid].polity_id is None]
            if actor.is_good() and enemy:
                target_region_id = self.rng.choice(enemy)
            elif actor.is_evil() and (enemy or unclaimed):
                target_region_id = self.rng.choice(enemy or unclaimed)
            elif border:
                target_region_id = self.rng.choice(border)
        if target_region_id is None:
            target_region_id = self.rng.choice(region.neighbors)
        if party is not None:
            for member_id in list(party.member_ids):
                member = world.actors.get(member_id)
                if member is not None and member.alive:
                    world.move_actor(member, target_region_id) if hasattr(world, "move_actor") else setattr(member, "region_id", target_region_id)
            self._spend_action(actor)
            if self.rng.random() < 0.25:
                world.log(f"{self._format_side_names([world.actors[mid] for mid in party.member_ids if mid in world.actors and world.actors[mid].alive])} set out for {world.region_name(target_region_id)}.", importance=1, category="travel")
        else:
            world.move_actor(actor, target_region_id) if hasattr(world, "move_actor") else setattr(actor, "region_id", target_region_id)
            self._spend_action(actor)
            if self.rng.random() < 0.15:
                world.log(f"{actor.short_name()} wanders into {world.region_name(target_region_id)}.", importance=1, category="travel")


    def _format_side_names(self, side: List[Actor]) -> str:
        if not side:
            return "nobody"
        party = self.world.get_party(side[0]) if side[0].alive else None
        if party and party.name and all(member.party_id == party.id for member in side if member.alive):
            return party.name
        living = [actor.short_name() for actor in side if actor.alive]
        if not living:
            return "nobody"
        if len(living) == 1:
            return living[0]
        if len(living) == 2:
            return f"{living[0]} and {living[1]}"
        return ", ".join(living[:-1]) + f", and {living[-1]}"


    def _deity_log_name(self, deity) -> str:
        if deity is None:
            return "None"
        return getattr(deity, "value", str(deity))


    def _champion_log_name(self, actor: Actor) -> str:
        if actor is None:
            return "Unknown"
        god = getattr(actor, "champion_of", None)
        if god is None:
            return actor.short_name()
        return f"{actor.short_name()} [Champion of {self._deity_log_name(god)}]"


    def _active_boon_labels_for_actor(self, actor: Actor) -> List[str]:
        world = self.world
        labels = []
        for boon in getattr(world, "active_boons", {}).values():
            if getattr(boon, "target_actor_id", None) == actor.id and getattr(boon, "expires_tick", 0) > world.tick:
                labels.append(getattr(boon, "label", getattr(boon, "boon_type", "boon")))
        return labels


    def _best_champion_on_side(self, side: List[Actor]) -> Optional[Actor]:
        champions = [a for a in side if a.alive and getattr(a, "champion_of", None) is not None]
        if not champions:
            return None
        return max(champions, key=lambda a: (len(self._active_boon_labels_for_actor(a)), getattr(a, "reputation", 0), getattr(a, "level", 1), a.power_rating()))


    def _log_champion_battle_credit(self, winners: List[Actor], losers: List[Actor], casualties: int, routed: int, region_name: str, repelled: bool = False) -> None:
        champion = self._best_champion_on_side(winners)
        if champion is None:
            return
        champion.champion_battle_victories = getattr(champion, "champion_battle_victories", 0) + 1
        champion.champion_battle_casualties = getattr(champion, "champion_battle_casualties", 0) + max(0, casualties)
        champion.champion_battle_routs = getattr(champion, "champion_battle_routs", 0) + max(0, routed)
        champion.reputation += 1
        boon_labels = self._active_boon_labels_for_actor(champion)
        boon_text = f" under {', '.join(boon_labels)}" if boon_labels else ""
        verb = "breaks the assault" if repelled else "turns the battle"
        result = []
        if casualties > 0:
            result.append(f"{casualties} dead")
        if routed > 0:
            result.append(f"{routed} routed")
        result_text = ", ".join(result) if result else "no enemy losses"
        self.world.log(
            f"{self._champion_log_name(champion)} {verb} in {region_name}{boon_text}; later accounts credit them with {result_text}.",
            importance=2,
            category="champion_impact",
        )


    def _steward_region(self, actor: Actor) -> bool:
        world = self.world
        if not actor.is_good():
            return False
        if not hasattr(world, 'commoners_by_region'):
            return False
        if world.commoners_by_region.get(actor.region_id, 0) <= 0:
            return False
        local_monsters = world.monsters_in_region(actor.region_id)
        if any(m.alive and m.kind in (MonsterKind.GIANT, MonsterKind.DRAGON, MonsterKind.ANCIENT_HORROR) for m in local_monsters):
            return False
        local_enemies = [other for other in world.actors_in_region(actor.region_id) if other.alive and other.is_adventurer() and other.is_evil()]
        if local_enemies:
            return False
        region = world.regions[actor.region_id]
        if region.order >= 95 and region.control >= 50:
            return False
        world.adjust_region_state(actor.region_id, control_delta=1, order_delta=2)
        actor.protects_region = actor.region_id
        if self.rng.random() < 0.35:
            actor.reputation += 1
        if self.rng.random() < 0.20:
            world.log(
                f"{actor.short_name()} helps restore order in {world.region_name(actor.region_id)}.",
                importance=1,
                category="stewardship",
            )
        self._spend_action(actor)
        return True


    def _rally_defenders(self, actor: Actor) -> bool:
        world = self.world
        if actor.reputation < 8 or actor.charisma < 12:
            return False
        goblin_threats = [monster for monster in world.monsters_in_region(actor.region_id) if monster.kind == MonsterKind.GOBLIN and monster.alive and monster.horde_size >= 8]
        if not goblin_threats:
            return False
        commoners = [person for person in world.actors_in_region(actor.region_id) if person.role == Role.COMMONER and person.alive]
        allied_heroes = [person for person in world.actors_in_region(actor.region_id) if person.is_adventurer() and person.alive and person.id != actor.id and not person.is_evil()]
        if len(commoners) + len(allied_heroes) < 6:
            return False
        chance = 0.40
        if actor.role == Role.FIGHTER:
            chance += 0.15
        if actor.role == Role.BARD:
            chance += 0.10
        if self.rng.random() < min(0.85, chance):
            threat = max(goblin_threats, key=lambda g: g.horde_size)
            army_power = actor.power_rating() + len(commoners) // 4 + sum(hero.power_rating() for hero in allied_heroes[:3])
            if actor.role == Role.FIGHTER:
                army_power += 6
            if actor.role == Role.BARD:
                army_power += 4
            if army_power >= threat.effective_power() or actor.mind_score() < 10:
                threat.horde_size = max(1, threat.horde_size - self.rng.randint(2, 5))
                actor.reputation += 2
                actor.regions_defended += 1
                world.adjust_region_state(actor.region_id, control_delta=2, order_delta=2)
                self._grant_title(actor, f"Defender of {world.region_name(actor.region_id)}")
                world.log(f"{actor.short_name()} rallies the people of {world.region_name(actor.region_id)} against a goblin horde.", importance=3, category="defense")
                self._spend_action(actor)
                if threat.horde_size <= 2:
                    threat.alive = False
                    world.kill_monster_cache_update(threat) if hasattr(world, "kill_monster_cache_update") else None
                    actor.kills += 1
                    actor.monster_kills += 1
                    if hasattr(actor, 'kill_log'):
                        actor.kill_log.append('goblin horde')
                    world.log(f"The goblin threat in {world.region_name(actor.region_id)} is broken.", importance=3, category="defense")
                return True
        return False


    def _recruit_goblins(self, actor: Actor) -> bool:
        world = self.world
        goblins = [monster for monster in world.monsters_in_region(actor.region_id) if monster.kind == MonsterKind.GOBLIN and monster.alive and monster.patron_actor_id is None]
        if not goblins:
            return False
        if actor.reputation < 8 or actor.charisma < 12:
            return False
        if self.rng.random() < 0.35:
            goblin = max(goblins, key=lambda g: g.horde_size)
            goblin.patron_actor_id = actor.id
            goblin.reputation += 2
            actor.reputation += 1
            actor.regions_oppressed += 1
            self._grant_title(actor, f"Boss of {world.region_name(actor.region_id)}")
            world.log(f"{actor.short_name()} wins the loyalty of {goblin.name} in {world.region_name(actor.region_id)}.", importance=2, category="goblin_loyalty")
            self._spend_action(actor)
            return True
        return False


    def _set_rest_timer(self, actor: Actor, min_ticks: int, max_ticks: int) -> None:
        if not actor.alive:
            return
        duration = self.rng.randint(min_ticks, max_ticks)
        actor.resting_until_tick = max(getattr(actor, 'resting_until_tick', -1), self.world.tick + duration)


    def _set_rest_for_side(self, side: List[Actor], min_ticks: int, max_ticks: int) -> None:
        for actor in side:
            self._set_rest_timer(actor, min_ticks, max_ticks)


    def _is_shift_active(self, actor: Actor) -> bool:
        shift = getattr(actor, 'duty_shift', 0) % ADVENTURER_SHIFT_COUNT
        return shift == (self.world.tick % ADVENTURER_SHIFT_COUNT)


    def _is_actor_hot(self, actor: Actor) -> bool:
        world = self.world
        if getattr(actor, 'recovering', 0) > 0:
            return True
        if getattr(actor, 'combat_cooldown', 0) > 0:
            return True
        if actor.polity_id is not None and actor.polity_id in world.polities:
            polity = world.polities[actor.polity_id]
            if polity.ruler_id == actor.id:
                return True
        if actor.party_id is not None:
            party = world.parties.get(actor.party_id)
            if party is not None and party.leader_id == actor.id:
                return True
        if any(m.alive for m in world.monsters_in_region(actor.region_id)):
            return True
        local = world.actors_in_region(actor.region_id)
        if any(other.alive and other.id != actor.id and actor.attitude_toward(other) == 'oppose' for other in local):
            return True
        region = world.regions[actor.region_id]
        if region.contested_by is not None:
            return True
        return False


    def _fatigue_cost_for_actor(self, actor: Actor) -> int:
        if actor.role == Role.WIZARD:
            return 2
        if actor.role == Role.FIGHTER:
            return 1
        if actor.role == Role.WARDEN:
            return 1
        return 1


    def _long_rest_window(self, actor: Actor) -> tuple[int, int]:
        world = self.world
        if actor.polity_id is not None and actor.polity_id in world.polities:
            polity = world.polities[actor.polity_id]
            if polity.ruler_id == actor.id:
                return (LEADER_LONG_REST_MIN, LEADER_LONG_REST_MAX)
        if actor.party_id is not None:
            party = world.parties.get(actor.party_id)
            if party is not None and party.leader_id == actor.id:
                return (LEADER_LONG_REST_MIN, LEADER_LONG_REST_MAX)
        return (LONG_REST_MIN, LONG_REST_MAX)


    def _take_short_rest(self, actor: Actor, min_ticks: Optional[int] = None, max_ticks: Optional[int] = None) -> None:
        if min_ticks is None:
            min_ticks = SHORT_REST_MIN
        if max_ticks is None:
            max_ticks = SHORT_REST_MAX
        if not actor.alive:
            return
        self._set_rest_timer(actor, min_ticks, max_ticks)
        actor.short_rests_since_long = getattr(actor, 'short_rests_since_long', 0) + 1
        actor.fatigue_actions = 0
        if actor.hp < actor.max_hp:
            actor.hp = min(actor.max_hp, actor.hp + 1)


    def _take_long_rest(self, actor: Actor, min_ticks: int | None = None, max_ticks: int | None = None) -> None:
        if not actor.alive:
            return
        if min_ticks is None or max_ticks is None:
            min_ticks, max_ticks = self._long_rest_window(actor)
        self._set_rest_timer(actor, min_ticks, max_ticks)
        actor.short_rests_since_long = 0
        actor.fatigue_actions = 0
        heal = max(2, actor.max_hp // 4)
        actor.hp = min(actor.max_hp, actor.hp + heal)
        actor.recovering = max(0, actor.recovering - 1)


    def _apply_fatigue(self, actor: Actor, amount: int = 1) -> None:
        if not actor.alive:
            return
        actor.fatigue_actions = getattr(actor, 'fatigue_actions', 0) + max(1, amount)


    def _resolve_fatigue_rest(self, actor: Actor) -> bool:
        if not actor.alive:
            return False
        fatigue = getattr(actor, 'fatigue_actions', 0)
        short_rests = getattr(actor, 'short_rests_since_long', 0)
        if fatigue >= LONG_REST_FATIGUE_THRESHOLD or short_rests >= SHORT_RESTS_BEFORE_LONG:
            self._take_long_rest(actor)
            return True
        if fatigue >= SHORT_REST_FATIGUE_THRESHOLD:
            self._take_short_rest(actor)
            return True
        return False


    def _post_battle_rest(self, side: List[Actor], routed: bool = False, legendary: bool = False) -> None:
        bard_support = self._bard_side_support(side)
        for actor in side:
            if not actor.alive:
                continue
            if legendary:
                self._take_long_rest(actor, POST_LEGENDARY_REST_MIN, POST_LEGENDARY_REST_MAX)
                continue
            if routed:
                self._take_long_rest(actor)
            else:
                if bard_support > 0:
                    self._take_short_rest(actor, max(1, SHORT_REST_MIN - 2), max(2, SHORT_REST_MAX - 4))
                else:
                    self._take_short_rest(actor)
            if bard_support > 0:
                actor.recovering = max(0, actor.recovering - 1)
                if self.rng.random() < min(0.50, bard_support):
                    actor.actions_remaining = max(actor.actions_remaining, 1)


    def _bard_side_support(self, side: List[Actor]) -> float:
        living_bards = [a for a in side if a.alive and a.role == Role.BARD]
        if not living_bards:
            return 0.0
        best = max(living_bards, key=lambda a: (a.charisma, a.wisdom, a.luck))
        return min(0.25, 0.08 + max(0, best.charisma - 10) * 0.01 + max(0, best.wisdom - 10) * 0.005)

    def _bard_side_bonus(self, side: List[Actor]) -> int:
        living_bards = [a for a in side if a.alive and a.role == Role.BARD]
        if not living_bards:
            return 0
        best = max(living_bards, key=lambda a: (a.charisma, a.wisdom, a.luck))
        return max(1, min(3, 1 + max(0, best.charisma - 12) // 3))

    def _bard_song(self, bard: Actor) -> bool:
        world = self.world
        if getattr(bard, 'bard_last_song_tick', -999999) + 60 > world.tick:
            return False
        local_allies = [a for a in world.actors_in_region(bard.region_id) if a.alive and a.is_adventurer() and a.id != bard.id and not a.is_ideological_enemy(bard)]
        if not local_allies:
            return False
        target = max(local_allies, key=lambda a: (a.reputation, a.kills, a.power_rating(), self.rng.random()))
        rep = 1
        if target.is_good():
            world.adjust_region_state(bard.region_id, control_delta=1, order_delta=1)
        elif target.is_evil():
            world.adjust_region_state(bard.region_id, control_delta=-1, order_delta=0)
        faith = getattr(world, 'commoner_faith_by_region', {}).get(bard.region_id)
        if faith is not None and sum(faith.values()) > 0:
            moved = max(1, min(10, world.commoners_by_region.get(bard.region_id, 0) // 5000 + 1))
            dominant = max([d for d in Deity if d != bard.deity], key=lambda d: faith.get(d, 0), default=None)
            if dominant is not None and faith.get(dominant, 0) > 0:
                shift = min(moved, faith.get(dominant, 0))
                faith[dominant] -= shift
                faith[bard.deity] = faith.get(bard.deity, 0) + shift
        target.reputation += rep
        bard.reputation += 1
        bard.bard_last_song_tick = world.tick
        if self.rng.random() < 0.20:
            world.log(f"A bard in {world.region_name(bard.region_id)} swears {self._champion_log_name(target)} could slay a dragon with a stern look and a borrowed spoon.", importance=1, category="bard_song")
        else:
            world.log(f"A bard in {world.region_name(bard.region_id)} sings of {self._champion_log_name(target)} and the turning favor of {self._deity_log_name(bard.deity)}.", importance=1, category="bard_song")
        self._spend_action(bard)
        return True

    def _warden_disrupt_capture(self, actor: Actor) -> bool:
        if actor.role != Role.WARDEN:
            return False
        world = self.world
        region = world.regions[actor.region_id]
        if region.under_siege_by is None or region.under_siege_by == region.polity_id:
            return False
        region.siege_progress = max(0, region.siege_progress - (10 + max(0, actor.wisdom - 10) + max(0, actor.dexterity - 10)))
        world.adjust_region_state(actor.region_id, control_delta=1 if actor.is_good() else 0, order_delta=1)

        # This action can be repeated tactically, but identical event text from
        # the same warden/region was drowning the roll. Keep the behavior;
        # throttle only the narration.
        log_window = max(1, int(globals().get("WARDEN_SABOTAGE_LOG_COOLDOWN_TICKS", globals().get("TICKS_PER_SEASON", 180))))
        log_key = actor.region_id
        recent = getattr(actor, "warden_sabotage_log_tick_by_region", None)
        if not isinstance(recent, dict):
            recent = {}
            actor.warden_sabotage_log_tick_by_region = recent
        last = int(recent.get(log_key, -999999))
        if world.tick - last >= log_window and self.rng.random() < 0.35:
            recent[log_key] = world.tick
            world.log(f"{actor.short_name()} scatters scouts and sabotages the subjugation of {world.region_name(actor.region_id)}.", importance=2, category="warden")
        self._spend_action(actor)
        return True

    def _wizard_ward_region(self, actor: Actor) -> bool:
        if actor.role != Role.WIZARD:
            return False
        world = self.world
        region = world.regions[actor.region_id]
        local_monsters = world.monsters_in_region(actor.region_id)
        if not any(m.alive and m.kind in (MonsterKind.DRAGON, MonsterKind.ANCIENT_HORROR) for m in local_monsters) and region.order >= 90:
            return False
        world.adjust_region_state(actor.region_id, control_delta=1, order_delta=2)
        faith = getattr(world, 'commoner_faith_by_region', {}).get(actor.region_id)
        if faith is not None and sum(faith.values()) > 0:
            moved = max(1, min(8, actor.wisdom // 3))
            dominant = max([d for d in Deity if d != actor.deity], key=lambda d: faith.get(d, 0), default=None)
            if dominant is not None and faith.get(dominant, 0) > 0:
                shift = min(moved, faith.get(dominant, 0))
                faith[dominant] -= shift
                faith[actor.deity] = faith.get(actor.deity, 0) + shift
        if self.rng.random() < 0.30:
            world.log(f"{actor.short_name()} raises wards over {world.region_name(actor.region_id)} against darker things.", importance=2, category="wizard")
        self._spend_action(actor)
        return True

    def _retired_turn(self, actor: Actor) -> None:
        world = self.world
        if actor.actions_remaining <= 0:
            return
        if actor.role == Role.FIGHTER:
            world.adjust_region_state(actor.region_id, control_delta=1 if actor.is_good() else 0, order_delta=2 if not actor.is_evil() else 0)
            if actor.polity_id is not None and actor.polity_id in world.polities:
                polity = world.polities[actor.polity_id]
                polity.legitimacy = min(100, polity.legitimacy + 1)
            if self.rng.random() < 0.20:
                world.log(f"{actor.short_name()} drills the local levy and keeps hard order in {world.region_name(actor.region_id)}.", importance=1, category="retirement")
        elif actor.role == Role.WARDEN:
            region = world.regions[actor.region_id]
            if region.under_siege_by is not None and region.under_siege_by != region.polity_id:
                region.siege_progress = max(0, region.siege_progress - (8 + max(0, actor.wisdom - 10)))
            world.adjust_region_state(actor.region_id, control_delta=1, order_delta=1)
            if self.rng.random() < 0.20:
                world.log(f"{actor.short_name()} keeps the roads and borders of {world.region_name(actor.region_id)} under watch.", importance=1, category="retirement")
        elif actor.role == Role.WIZARD:
            self._wizard_ward_region(actor)
            return
        elif actor.role == Role.BARD:
            if actor.polity_id is not None and actor.polity_id in world.polities:
                polity = world.polities[actor.polity_id]
                polity.legitimacy = min(100, polity.legitimacy + 1)
                polity.stability = min(100, polity.stability + 1)
            world.adjust_region_state(actor.region_id, control_delta=0, order_delta=1)
            if self.rng.random() < 0.30:
                self._bard_song(actor)
                return
        self._spend_action(actor)

    def _record_champion_conversions(self, actor: Actor, moved: int) -> None:
        if moved <= 0:
            return
        actor.converted_followers = getattr(actor, 'converted_followers', 0) + moved
        rep_steps = actor.converted_followers // 100
        new_steps = rep_steps - getattr(actor, 'champion_rep_steps', 0)
        if new_steps > 0:
            actor.reputation += new_steps
            actor.champion_rep_steps = rep_steps
            try:
                self.world.log(
                    f"{self._champion_log_name(actor)} is credited with winning {actor.converted_followers} faithful to {self._deity_log_name(getattr(actor, 'champion_of', getattr(actor, 'deity', None)))}.",
                    importance=2,
                    category="champion_impact",
                )
            except Exception:
                pass


    def _champion_convert_region(self, actor: Actor) -> bool:
        if getattr(actor, 'champion_of', None) is None:
            return False
        world = self.world
        region_id = actor.region_id
        total_commoners = world.commoners_by_region.get(region_id, 0)
        if total_commoners <= 0:
            return False
        faith = world.commoner_faith_by_region.setdefault(region_id, {deity: 0 for deity in Deity})
        pool = sum(faith.get(d, 0) for d in Deity if d != actor.deity)
        if pool <= 0:
            return False
        moved = min(pool, min(CHAMPION_ACTIVE_CONVERSION_MAX, max(CHAMPION_ACTIVE_CONVERSION_MIN, int(total_commoners * CHAMPION_ACTIVE_CONVERSION_RATE))))
        if moved <= 0:
            return False
        sources = [d for d in Deity if d != actor.deity]
        assigned = 0
        for i, deity in enumerate(sources):
            available = faith.get(deity, 0)
            if i == len(sources) - 1:
                loss = min(available, moved - assigned)
            else:
                loss = min(available, int(moved * (available / max(1, pool))))
                assigned += loss
            faith[deity] = max(0, available - loss)
        faith[actor.deity] = faith.get(actor.deity, 0) + moved
        self._record_champion_conversions(actor, moved)
        self._spend_action(actor)
        actor.deity_conviction = min(100, actor.deity_conviction + 1)
        if self.rng.random() < 0.20:
            world.log(f"{self._champion_log_name(actor)} spreads the cause of {self._deity_log_name(actor.deity)} in {world.region_name(region_id)}, winning {moved} new converts.", importance=2, category='conversion')
        return True


    def _champion_move_for_conversion(self, actor: Actor) -> bool:
        if getattr(actor, 'champion_of', None) is None:
            return False
        world = self.world
        region = world.regions[actor.region_id]
        if not region.neighbors:
            return False

        def score_region(rid: int) -> int:
            faith = world.commoner_faith_by_region.setdefault(rid, {deity: 0 for deity in Deity})
            total = world.commoners_by_region.get(rid, 0)
            opposing = sum(faith.get(d, 0) for d in Deity if d != actor.deity)
            favored = 1 if self._region_favored_deity(rid) == actor.deity else 0
            r = world.regions[rid]
            contested_bonus = 200 if -19 <= r.control <= 19 else 0
            weak_bonus = max(0, 40 - r.order) * 5
            return total + opposing + contested_bonus + weak_bonus - favored * 500

        current_score = score_region(actor.region_id)
        target_region_id = max(region.neighbors, key=score_region)
        if score_region(target_region_id) <= current_score:
            return False

        party = world.get_party(actor)
        if party is not None:
            for member_id in party.member_ids:
                member = world.actors[member_id]
                if member.alive:
                    world.move_actor(member, target_region_id) if hasattr(world, "move_actor") else setattr(member, "region_id", target_region_id)
            if self.rng.random() < 0.25:
                world.log(f"{self._champion_log_name(actor)} leads {self._format_side_names([world.actors[mid] for mid in party.member_ids if mid in world.actors and world.actors[mid].alive])} to {world.region_name(target_region_id)} to spread the cause of {self._deity_log_name(actor.deity)}.", importance=1, category='travel')
        else:
            world.move_actor(actor, target_region_id) if hasattr(world, "move_actor") else setattr(actor, "region_id", target_region_id)
            if self.rng.random() < 0.20:
                world.log(f"{self._champion_log_name(actor)} journeys to {world.region_name(target_region_id)} to spread the cause of {self._deity_log_name(actor.deity)}.", importance=1, category='travel')
        self._spend_action(actor)
        return True


    def _adventurer_turn(self, actor: Actor) -> None:
        world = self.world
        if not hasattr(actor, "combat_cooldown"):
            actor.combat_cooldown = 0
        if not hasattr(actor, "actions_remaining"):
            actor.actions_remaining = ACTIONS_PER_TICK
        if self._party_or_actor_has_acted(actor):
            return
        if getattr(actor, 'resting_until_tick', -1) > world.tick:
            return
        party = world.get_party(actor)
        if party is not None and party.leader_id is not None and party.leader_id != actor.id:
            return
        if actor.actions_remaining <= 0:
            return
        if actor.combat_cooldown > 0:
            actor.recovering = max(actor.recovering, 1)
            return
        age = self._calculate_age(actor)
        if actor.is_declining_with_age(age) and self.rng.random() < 0.20:
            actor.recovering = max(actor.recovering, 1)
        if getattr(actor, 'retired', False):
            self._retired_turn(actor)
            return
        if self._resolve_fatigue_rest(actor):
            return
        if actor.needs_rest():
            self._rest_or_retreat(actor)
            return
        if actor.party_id is None and actor.role != Role.BARD:
            self._try_form_party(actor)
        is_champion = getattr(actor, 'champion_of', None) is not None
        if is_champion:
            if hasattr(self, "_champion_created_relic_compulsion") and self._champion_created_relic_compulsion(actor):
                return
            if self._champion_convert_region(actor):
                return
            if self._champion_move_for_conversion(actor):
                return
        if actor.role == Role.BARD:
            if actor.party_id is None:
                self._try_form_party(actor)
            if self._bard_song(actor):
                return
        if actor.role == Role.WARDEN:
            if self._warden_disrupt_capture(actor):
                return
        if actor.role == Role.WIZARD:
            if self._wizard_ward_region(actor):
                return
        if actor.is_good():
            if self._rally_defenders(actor):
                return
            if self._protect_commoners(actor):
                return
            if self._steward_region(actor):
                return
        elif actor.is_evil():
            if self._recruit_goblins(actor):
                return
            if self._oppress_commoners(actor):
                return
        if self._seek_relic(actor):
            return
        if self._hunt_monsters(actor):
            return
        target = self._find_enemy_target(actor)
        if target is not None:
            if is_champion and getattr(target, 'champion_of', None) != getattr(actor, 'champion_of', None):
                if getattr(target, 'champion_of', None) is None:
                    if self._champion_move_for_conversion(actor):
                        return
                    if self._should_retreat(actor, target):
                        self._retreat(actor, reason="their divine mission takes precedence over open war")
                        return
                if self._should_attack(actor, target):
                    self._resolve_battle(actor, target)
                    return
            else:
                if self._should_attack(actor, target):
                    self._resolve_battle(actor, target)
                    return
                if self._should_retreat(actor, target):
                    self._retreat(actor, reason="an opposing force proves too strong")
                    return
        move_chance = 0.45 + max(0, actor.luck - 10) * 0.005
        _, _, _, tod, season = world.current_calendar()
        if tod == "Night":
            move_chance -= 0.10
        if season == "Winter":
            move_chance -= 0.10
        if actor.role == Role.WARDEN:
            move_chance += 0.12
        if actor.role == Role.BARD:
            move_chance += 0.05
        if actor.is_declining_with_age(age):
            move_chance -= 0.15
        if self.rng.random() < max(0.10, move_chance):
            self._quest_move(actor)


    def _region_safety_score(self, region_id: int) -> int:
        world = self.world
        region = world.regions[region_id]
        local_monsters = world.monsters_in_region(region_id)
        major_monsters = sum(
            1 for m in local_monsters
            if m.alive and m.kind in (MonsterKind.GOBLIN, MonsterKind.GIANT, MonsterKind.DRAGON, MonsterKind.ANCIENT_HORROR)
        )
        return region.order + region.control - (region.danger * 5) - (major_monsters * 10)


