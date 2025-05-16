"""Scripts for handling the reward vibration strength and buzzes."""

import time


class VibrationHandler:
    """Handles the reward vibration strength and buzzes."""

    def __init__(self, logger, rcon, config: dict):
        self.logger = logger
        self.rcon = rcon
        self.uber_strength = 0  # uber active strength
        # Timed buzzes are a list of tuples of (strength, time_end)
        self.timed_buzzes: list[tuple[float, float]] = []  # list of timed vibration activations
        self._curr_strength = 0  # current strength priv variable
        self.last_strength = 0
        self.killstreak = 0  # killstreak tracking
        self.uberstreak = 0

        # Set config args
        self.activate_command: str = config["activate_command"]
        self.deactivate_command: str = config["deactivate_command"]
        self.base_vibe: float = config["base_vibe"]
        # Kills
        self.kill_strength: float = config["kill_strength"]
        self.kill_time: float = config["kill_time"]
        self.kill_crit_strength_multiplier: float = config["kill_crit_strength_multiplier"]
        self.kill_crit_time_multiplier: float = config["kill_crit_time_multiplier"]

        # Killstreaks
        self.killstreak_strength_multiplier: float = config["killstreak_strength_multiplier"]
        self.killstreak_time_multiplier: float = config["killstreak_time_multiplier"]
        self.killstreak_max: int = config["killstreak_max"]

        # Death
        self.death_strength: float = config["death_strength"]
        self.death_time: float = config["death_time"]

        # Uber
        self.uber_active_strength: float = config["uber_active_strength"]
        self.uber_streak_multiplier: float = config["uber_streak_multiplier"]
        self.uber_milestones: list[int] = config["uber_milestones"]
        self.uber_milestone_strength: float = config["uber_milestone_strength"]
        self.uber_milestone_time: float = config["uber_milestone_time"]
        self.uber_milestone_strength_multiplier: float = config["uber_milestone_strength_multiplier"]
        self.uber_milestone_time_multiplier: float = config["uber_milestone_time_multiplier"]

    @property
    def current_strength(self):
        """Getter for the current strength."""
        return self._curr_strength

    @current_strength.setter
    def current_strength(self, new_strength):
        if new_strength > self._curr_strength:
            self._curr_strength = new_strength

    def timed_buzz(self, strength, time_end):
        """Add a timed buzz to the queue."""
        self.timed_buzzes.append((strength, time.time() + time_end))

    def death(self):
        """On death, trigger a reward ;3 based on the current streak."""
        self.killstreak = 0
        self.end_uber_death()
        self.timed_buzz(self.death_strength, self.death_time)

    def kill(self, crit=False):
        """On kill, trigger reward based on current streak."""
        self.killstreak += 1
        # [0, 1]
        killstreak_coeff = min(self.killstreak, self.killstreak_max) / (self.killstreak_max)

        strength = (
            self.kill_strength
            * (killstreak_coeff * (self.killstreak_strength_multiplier - 1.0) + 1.0)
            * (self.kill_crit_strength_multiplier if crit else 1.0)
        )
        kill_time = (
            self.kill_time
            * (killstreak_coeff * (self.killstreak_time_multiplier - 1.0) + 1.0)
            * (self.kill_crit_time_multiplier if crit else 1.0)
        )

        self.timed_buzz(strength, kill_time)

    def uber_milestone(self, uber_percent, last_uber_percent):
        """Check if we hit an uber milestone and reward accordingly."""
        for i, x in enumerate(self.uber_milestones):
            if uber_percent > x >= last_uber_percent:
                self.logger.info(f"Hit Uber milestone {x}")
                uber_milestone_coeff = i / len(self.uber_milestones) - 1
                self.timed_buzz(
                    self.uber_milestone_strength
                    * (uber_milestone_coeff * (self.uber_milestone_strength_multiplier - 1.0) + 1.0),
                    self.uber_milestone_time
                    * (uber_milestone_coeff * (self.uber_milestone_time_multiplier - 1.0) + 1.0),
                )

    def start_uber(self):
        """On start of uber, set strength based on the current streak."""
        self.uber_strength = self.uber_active_strength * (self.uber_streak_multiplier**self.uberstreak)

    def end_uber(self):
        """On end of uber, reset the strength and increment the streak."""
        self.uber_strength = 0
        self.uberstreak += 1

    def end_uber_death(self):
        """On death, reset the uber strength and streak."""
        self.uber_strength = 0
        self.uberstreak = 0

    def update(self):
        """Update the current strength based on the timed buzzes and the base vibe."""
        self.last_strength = self.current_strength
        self._curr_strength = self.base_vibe

        now = time.time()

        for timer in self.timed_buzzes:
            if now <= timer[1]:
                self.current_strength = timer[0]

        self.current_strength = self.uber_strength

        self.timed_buzzes = list(filter(lambda x: x[1] > now, self.timed_buzzes))

        # Check if we need to run the activate/deactivate command
        if self.current_strength > self.base_vibe >= self.last_strength:
            if self.activate_command != "":
                self.logger.info("Running activate command")
                self.rcon.execute(self.activate_command)
        if self.current_strength <= self.base_vibe < self.last_strength:
            if self.deactivate_command != "":
                self.logger.info("Running deactivate command")
                self.rcon.execute(self.deactivate_command)

        return self.current_strength

    # Takes a list of devices and activates devices based on vibration handling
    async def run_buzz(self, devices):
        """Update the vibration strength and run the command on all devices."""
        vibe_strength = self.update()

        # activate all actuators
        for device in devices.values():
            for actuator in device.actuators:
                await actuator.command(vibe_strength)
        #
        # could also do this
        # await devices[0].actuators[0].command(vibe_strength)
        # await devices[0].actuators[1].command(vibe_strength * 0.5)
        # etc.
